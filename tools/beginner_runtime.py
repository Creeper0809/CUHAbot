"""Real-engine novice runs. Only Discord transport, user input and wall waits are replaced.

An isolated SQLite DB holds real registrations, decks, loot and settlement. Every
run starts from a newly created account; no synthetic healing or equipment budget.
Never connects to the configured production database.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from contextlib import ExitStack, redirect_stdout
import io
import json
import logging
import os
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tortoise import Tortoise
from models import User, UserStatEnum
from models.repos import static_cache
from service.player.starter_recovery import ensure_account
from service.player.user_service import UserService
from service.session import DungeonSession, active_sessions
from service.dungeon import combat_executor as combat, roguelike_loop as loop
from service.dungeon.roguelike_routes import RouteOffer


class Transport:
    """Discard network delivery, but serialize every real Embed to detect errors."""
    id = 123456789
    display_name = "headless novice"
    mention = "<@123456789>"
    display_avatar = SimpleNamespace(url="https://example.com/avatar.png")
    avatar = display_avatar
    guild = None
    guild_id = None
    channel_id = None
    voice = None
    embeds = []

    def __init__(self):
        self.user = self.channel = self.client = self.followup = self.response = self
        self.payloads = []

    async def send(self, *args, **kwargs):
        return await self.edit(**kwargs)

    async def edit(self, **kwargs):
        if kwargs.get("embed"):
            self.payloads.append({"embeds": [kwargs["embed"].to_dict()],
                                  "components": kwargs["view"].to_components() if kwargs.get("view") else []})
        return self

    async def delete(self, *args, **kwargs):
        pass

    def get_channel(self, *args):
        return None

    async def fetch_user(self, *args):
        return self


async def noop(*args, **kwargs):
    return None


class RuntimeErrors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


async def seed_fixture():
    from scripts import seed_from_csv as seed
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["models"]})
    await Tortoise.generate_schemas()
    with redirect_stdout(io.StringIO()):
        for name in ("grades", "equip_pos", "item_grade_probability", "skills", "dungeons", "monsters",
                     "equipment_items", "consumable_items", "enhancement_items", "material_items",
                     "dungeon_spawns", "droptable", "sets", "raids"):
            await getattr(seed, "seed_" + name)()
    await static_cache.load_static_data()


class Harness:
    def __init__(self, strategy, capture_ui=False):
        self.strategy = strategy
        self.capture_ui = capture_ui
        self.encounters = []
        self.transport = Transport()

    async def choose(self, session, *args):
        offers = [RouteOffer.from_dict(value) for value in session.route_offers]
        elite = [offer for offer in offers if offer.kind.value == "elite"]
        pool = elite if self.strategy == "elite" and elite else offers
        return session.run_rng.choice(pool)

    async def combat(self, session, interaction, context):
        self.current = {"monster_id": context.monsters[0].id, "room": min(9, session.exploration_step + 1),
                        "entry_hp": session.user.now_hp, "player_actions": 0, "attack_actions": 0,
                        "maximum_action_damage": 0, "maximum_hp_loss": 0,
                        "initial_monster_hp": context.monsters[0].hp}
        self.current["logs"] = []
        self.previous_hp = session.user.now_hp
        result = await self.original_combat(session, interaction, context)
        if session.user.now_hp > 0 and not context.is_all_dead():
            raise AssertionError("Living enemies were incorrectly settled as a victory")
        self.current["end_hp"] = session.user.now_hp
        self.current["all_enemies_dead"] = context.is_all_dead()
        self.current["actions"] = context.action_count
        self.encounters.append(self.current)
        return result

    def action(self, session, user, actor, context):
        before_hp = user.now_hp
        monster_hp = sum(max(0, m.now_hp) for m in context.monsters)
        logs = self.original_action(session, user, actor, context)
        if len(self.current["logs"]) < 40:
            self.current["logs"].extend(logs)
        if isinstance(actor, User):
            self.current["player_actions"] += 1
            if sum(max(0, m.now_hp) for m in context.monsters) < monster_hp:
                self.current["attack_actions"] += 1
        else:
            self.current["maximum_action_damage"] = max(self.current["maximum_action_damage"], before_hp - user.now_hp)
        return logs

    async def update(self, session, message, user, context, logs):
        previous = getattr(self, "previous_hp", user.now_hp)
        self.current["maximum_hp_loss"] = max(self.current["maximum_hp_loss"], previous - user.now_hp)
        self.previous_hp = user.now_hp
        if self.capture_ui:
            await combat._ui_manager.update_all_combat_messages(session, message, user, context, logs)

    def patches(self):
        stack = ExitStack()
        # Input autopilot also skips event confirmation; it must NEVER modify
        # monsters. Actual route weights, skills, FSM and status ticks run intact.
        stack.enter_context(patch.dict(os.environ, {"E2E_UI_AUTOPILOT": "TRUE"}))
        self.original_combat = combat.execute_combat_context
        self.original_action = combat._execute_entity_action
        stack.enter_context(patch.object(combat, "execute_combat_context", self.combat))
        stack.enter_context(patch.object(combat, "_execute_entity_action", self.action))
        stack.enter_context(patch.object(combat, "_update_all_combat_messages", self.update))
        stack.enter_context(patch.object(loop, "wait_for_route_choice", self.choose))
        stack.enter_context(patch("asyncio.sleep", noop))
        ui_stubs = ["cleanup_combat_messages"]
        if not self.capture_ui:
            ui_stubs += ["send_initial_combat_ui", "send_final_combat_result"]
        for name in ui_stubs:
            stack.enter_context(patch.object(combat._ui_manager, name, noop))
        stack.enter_context(patch("service.notification.notification_service.NotificationService.send_tiered_combat_notifications", noop))
        return stack

    async def run(self, level, dungeon_id, seed, deck_mode="starter", gear="none"):
        conn = Tortoise.get_connection("default")
        if conn.capabilities.dialect != "sqlite" and not os.environ.get("DATABASE_TABLE", "").endswith("_beginner_check"):
            raise RuntimeError("Runtime fixtures require an isolated test database")
        self.encounters = []
        self.transport.payloads.clear()
        if await User.filter(discord_id=700000000 + seed).exists():
            raise RuntimeError("Refusing to modify an existing account as a test fixture")
        user = await ensure_account(700000000 + seed, "headless novice")
        base = UserService.calculate_base_stats(level)
        user.level = level
        for field, value in base.items():
            setattr(user, "defense" if field == "ad_defense" else field, value)
        user.now_hp = user.hp
        user.stat_points = (level - 1) * 3
        await user.save()
        if deck_mode != "starter":
            from models.user_skill_deck import UserSkillDeck
            from models.repos.users_repo import find_account_by_discordid
            await UserSkillDeck.filter(user=user).delete()
            if deck_mode == "basic":
                for slot in range(10):
                    await UserSkillDeck.create(user=user, slot_index=slot, skill_id=1001)
            user = await find_account_by_discordid(user.discord_id)
        else:
            from models.repos.users_repo import find_account_by_discordid
            user = await find_account_by_discordid(user.discord_id)
        equipment_ids = []
        if gear == "previous":
            from models.user_inventory import UserInventory
            from models.user_equipment import EquipmentSlot
            from service.item.equipment_service import EquipmentService
            # Ordinary Lv1/5 shop armor and cave iron sword; no affixes,
            # enhancement, assigned attributes or high-grade farming assumed.
            equipment_ids = [1002, 2002, 2102, 2202, 2302, 3001, 3102, 3102, 4002]
            for slot, item_id in zip(EquipmentSlot, equipment_ids):
                inventory = await UserInventory.create(user=user, item_id=item_id, instance_grade=1, enhancement_level=0)
                await EquipmentService.equip_item(user, inventory.id, slot)
            await EquipmentService.apply_equipment_stats(user)
            user.now_hp = user.get_stat()[UserStatEnum.HP]
        initial = {"level": level, "equipment_ids": equipment_ids, "equipment_grade": 1, "enhancement": 0,
                   "deck_ids": list(user.equipped_skill), "stats": {k.name: v for k, v in user.get_stat().items()}}
        session = DungeonSession(user_id=user.discord_id, user=user, dungeon=static_cache.dungeon_cache[dungeon_id])
        session.run_seed = seed
        session.run_rng = random.Random(seed)
        active_sessions[user.discord_id] = session
        random.seed(seed)
        errors = RuntimeErrors()
        logging.getLogger().addHandler(errors)
        try:
            with self.patches():
                passed = await loop.start_roguelike_dungeon(session, self.transport)
            assert not errors.messages, f"Runtime swallowed errors: {errors.messages}"
            persisted = await User.get(id=user.id)
            assert persisted.exp == user.exp and persisted.gold == user.gold
            cleared = bool(passed and session.exploration_step == 9 and user.now_hp > 0)
            outcome = "clear" if cleared else "death" if not passed else "return" if session.ended else "timeout"
            from models.user_inventory import UserInventory
            inventory = await UserInventory.filter(user=user).values("item_id", "quantity")
            return {"seed": seed, "passed": cleared, "outcome": outcome, "initial": initial,
                    "death_room": session.exploration_step if outcome == "death" else None,
                    "encounters": self.encounters, "exp": persisted.exp, "gold": persisted.gold,
                    "settled_exp": session.total_exp, "settled_gold": session.total_gold,
                    "inventory": inventory, "augments": session.skill_augments}
        finally:
            logging.getLogger().removeHandler(errors)
            active_sessions.pop(user.discord_id, None)
            await user.delete()  # isolated fixture only; cascading test data cleanup


async def main(args):
    logging.getLogger().setLevel(logging.ERROR)
    started = time.monotonic()
    await seed_fixture()
    harness = Harness(args.strategy)
    results = []
    try:
        for seed in range(args.seed, args.seed + args.runs):
            results.append(await harness.run(args.level, args.dungeon, seed, args.deck, args.gear))
            if len(results) % 100 == 0:
                print(f"{len(results)}/{args.runs} runs; {time.monotonic()-started:.1f}s", flush=True)
        by_monster = defaultdict(list)
        for run in results:
            for encounter in run["encounters"]:
                by_monster[encounter["monster_id"]].append(encounter)
        report = {"engine": "start_roguelike_dungeon/execute_combat_context + real SQLite persistence",
                  "args": vars(args), "seconds": time.monotonic() - started,
                  "clear_rate": sum(r["passed"] for r in results) / len(results),
                  "fixture": results[0]["initial"], "failure_seeds": [r["seed"] for r in results if not r["passed"]],
                  "death_rooms": dict(Counter(r["death_room"] for r in results if not r["passed"])),
                  "monsters": {key: {"count": len(rows),
                                     "mean_attack_actions": sum(r["attack_actions"] for r in rows)/len(rows),
                                     "max_action_damage": max(r["maximum_action_damage"] for r in rows),
                                     "minimum_entry_hp": min(r["entry_hp"] for r in rows)} for key, rows in by_monster.items()},
                  "samples": results[:3]}
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"clear_rate": report["clear_rate"], "seconds": report["seconds"], "report": str(path)}))
        from config.beginner_balance import AREA_TARGETS
        minimum = .95 if args.deck != "starter" else AREA_TARGETS.get(args.dungeon, {}).get(args.strategy, .90)
        if report["clear_rate"] < minimum:
            raise SystemExit(f"Clear-rate gate failed: {report['clear_rate']:.4%} < {minimum:.2%}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--dungeon", type=int, default=1)
    parser.add_argument("--strategy", choices=["random", "elite"], default="random")
    parser.add_argument("--deck", choices=["starter", "basic", "empty"], default="starter")
    parser.add_argument("--gear", choices=["none", "previous"], default="none")
    parser.add_argument("--output", default="reports/beginner-runtime.json")
    asyncio.run(main(parser.parse_args()))
