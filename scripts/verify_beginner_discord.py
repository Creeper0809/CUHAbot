"""Real Discord payload round trip + real run on the restored isolated DB.

Does not manufacture Discord interactions or claim a human slash/button click.
Credentials are read only from the server environment, never included in reports.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiohttp
from tortoise import Tortoise
from scripts.migrate_roguelike_reward_system import init_db
from models import User
from models.repos import static_cache
from models.user_inventory import UserInventory
from models.user_owned_skill import UserOwnedSkill
from resources.item_emoji import ItemType
from service.player.starter_recovery import ensure_account
from service.player.user_service import UserService
from views.inventory.components import ItemSelectDropdown
from views.inventory.list_view import InventoryView
from views.inventory.select_view import InventorySelectView
from views.skill_deck.main import SkillDeckView
from tools.beginner_runtime import Harness


def assert_payload_subset(expected, actual):
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key == "default" and value is False and key not in actual:
                continue  # Discord omits false SelectOption defaults on GET.
            assert key in actual, f"Missing Discord field: {key}"
            assert_payload_subset(value, actual[key])
    elif isinstance(expected, list):
        assert len(expected) == len(actual)
        for first, second in zip(expected, actual):
            assert_payload_subset(first, second)
    else:
        assert expected == actual, f"Payload mismatch: {expected!r} != {actual!r}"


def executable_component_fields(component):
    result = {
        key: value
        for key, value in component.items()
        if key in {"type", "custom_id", "label", "style", "options"}
    }
    if "options" in result:
        result["options"] = [
            {
                key: value
                for key, value in option.items()
                if key in {"label", "value", "description", "emoji", "default"}
                and value is not None
            }
            for option in result["options"]
        ]
        for option in result["options"]:
            if isinstance(option.get("emoji"), dict):
                option["emoji"] = {
                    key: value for key, value in option["emoji"].items()
                    if value is not None
                }
    return result


async def main(args):
    if not os.environ.get("DATABASE_TABLE", "").endswith("_beginner_check"):
        raise RuntimeError("Only the restored isolated database is allowed")
    logging.getLogger().setLevel(logging.ERROR)
    snowflake = 890000000000000092
    await init_db()
    try:
        await static_cache.load_static_data()
        assert not await User.filter(discord_id=snowflake).exists()
        user = await ensure_account(snowflake, "초반 던전 검증용 계정")
        try:
            owned = {r.skill_id: r for r in await UserOwnedSkill.filter(user=user)}
            view = SkillDeckView(SimpleNamespace(id=snowflake), list(user.equipped_skill),
                                 [static_cache.skill_cache_by_id[s] for s in owned], user, owned)
            await view.initialize()
            deck = {"embeds": [view.create_embed().to_dict()], "components": view.to_components()}
            assert user.equipped_skill == UserService.DEFAULT_SKILL_DECK
            view.stop()

            potion = await UserInventory.create(user=user, item_id=8001, quantity=2)
            await UserInventory.create(user=user, item_id=1001, quantity=1, instance_grade=1)
            await UserInventory.create(user=user, item_id=7002, quantity=1)
            await potion.fetch_related("item")
            inventory_view = InventoryView(SimpleNamespace(id=snowflake), user, [potion])
            action_view = InventorySelectView(SimpleNamespace(id=snowflake), user, inventory_view)
            await action_view.refresh_items()
            category_dropdown = next(
                child for child in action_view.children if isinstance(child, ItemSelectDropdown)
            )
            assert {row.item.type for row in action_view.inventory} == {ItemType.CONSUME}
            assert [option.value for option in category_dropdown.options] == [str(potion.id)]
            category = {
                "embeds": [action_view.create_embed().to_dict()],
                "components": action_view.to_components(),
            }
            action_view.stop()
            inventory_view.stop()
        finally:
            await user.delete()
        harness = Harness("elite", capture_ui=True)
        run = await harness.run(1, 1, 99091)
        assert run["passed"] and run["exp"] > 0
        frames = [p for p in harness.transport.payloads if p["components"] and
                  any("combat" in c.get("custom_id", "") for row in p["components"] for c in row["components"])]
        if not frames:
            frames = [p for p in harness.transport.payloads if p["components"]]
        assert len(frames) >= 2, "Combat renderer did not produce an initial/final message"
        headers = {"Authorization": "Bot " + os.environ["DISCORD_TOKEN"]}
        async with aiohttp.ClientSession(headers=headers) as client:
            async def api(method, route, payload=None):
                async with client.request(method, "https://discord.com/api/v10" + route, json=payload) as response:
                    if response.status >= 400:
                        raise RuntimeError(f"Discord {method} {route}: HTTP {response.status}")
                    return await response.json()
            guild = os.environ["GUILD_ID"]
            me = await api("GET", "/users/@me")
            commands = await api("GET", f"/applications/{me['id']}/guilds/{guild}/commands")
            global_commands = await api("GET", f"/applications/{me['id']}/commands")
            names = {c["name"] for c in commands + global_commands}
            assert "던전입장" in names, "Dungeon slash command not registered"
            thread = await api("GET", f"/channels/{args.thread}") if args.thread else await api(
                "POST", f"/channels/{args.channel}/threads",
                {"name": "초반 던전 패치 검증 (격리 DB)", "type": 11, "auto_archive_duration": 60})
            channel = thread["id"]
            verified = []
            for payload in [deck, category, frames[0]]:
                payload["allowed_mentions"] = {"parse": []}
                message = await api("POST", f"/channels/{channel}/messages", payload)
                if payload is frames[0]:
                    payload = frames[-1]
                    payload["allowed_mentions"] = {"parse": []}
                    await api("PATCH", f"/channels/{channel}/messages/{message['id']}", payload)
                received = await api("GET", f"/channels/{channel}/messages/{message['id']}")
                for expected, actual in zip(payload["embeds"], received["embeds"], strict=True):
                    for key in ("title", "description", "color", "fields"):
                        assert actual.get(key) == expected.get(key), f"Embed mismatch: {key}"
                # Discord may add component numeric IDs; compare executable fields.
                expected_buttons = [executable_component_fields(c)
                                    for row in payload["components"] for c in row["components"]]
                actual_buttons = [executable_component_fields(c)
                                  for row in received["components"] for c in row["components"]]
                assert_payload_subset(expected_buttons, actual_buttons)
                verified.append(message["id"])
            await api("POST", f"/channels/{channel}/messages", {
                "content": f"격리 DB 신규 가입 → 기본 덱 → 실제 숲 전투 → 보상 저장 통과. EXP {run['exp']}, 골드 {run['gold']}. 실제 Discord Embed/버튼 데이터 재조회 일치. 사람의 슬래시 입력·클릭을 자동 실행한 검사는 아닙니다.",
                "allowed_mentions": {"parse": []}})
            result = {"passed": True, "guild_id": guild, "thread_id": channel, "message_ids": verified,
                      "registered_commands": sorted(names), "deck_ids": run["initial"]["deck_ids"],
                      "run": run, "scope": "REST payload round trip and isolated PostgreSQL runtime; no synthetic Discord interaction"}
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"passed": True, "thread_id": channel, "messages": verified}))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    parser.add_argument("--thread")
    parser.add_argument("--output", default="/tmp/beginner-discord.json")
    asyncio.run(main(parser.parse_args()))
