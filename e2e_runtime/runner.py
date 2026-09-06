from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Any

import discord

from models import User
from models.repos import find_account_by_discordid, static_cache
from service.session import DungeonSession, ContentType, end_session

from .manager import VISUAL_CASE_IDS
from .models import CheckResult, TestRun


logger = logging.getLogger(__name__)


class RunContext:
    """Small Context-compatible adapter that records messages in a run thread."""

    def __init__(self, bot, channel, author, guild) -> None:
        self.bot = bot
        self.channel = channel
        self.author = author
        self.guild = guild
        self.messages: list[discord.Message] = []

    async def send(self, content=None, **kwargs):
        for key in ("ephemeral", "wait", "thinking"):
            kwargs.pop(key, None)
        message = await self.channel.send(content=content, **kwargs)
        self.messages.append(message)
        return message


def _component_payload(component: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": int(component.type.value)}
    for name in ("custom_id", "label", "placeholder", "disabled", "min_values", "max_values", "url"):
        value = getattr(component, name, None)
        if value is not None:
            payload[name] = value
    style = getattr(component, "style", None)
    if style is not None:
        payload["style"] = int(style.value)
    options = getattr(component, "options", None)
    if options is not None:
        payload["options"] = [
            {
                "label": option.label,
                "value": option.value,
                "description": option.description,
                "default": option.default,
            }
            for option in options
        ]
    children = getattr(component, "children", None)
    if children is not None:
        payload["components"] = [_component_payload(child) for child in children]
    return payload


async def fetch_payload(message: discord.Message) -> tuple[discord.Message, dict[str, Any]]:
    fetched = await message.channel.fetch_message(message.id)
    return fetched, {
        "message_id": str(fetched.id),
        "jump_url": fetched.jump_url,
        "content": fetched.content,
        "author_id": str(fetched.author.id),
        "embeds": [embed.to_dict() for embed in fetched.embeds],
        "components": [_component_payload(row) for row in fetched.components],
    }


def _all_custom_ids(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []

    def visit(component: dict[str, Any]) -> None:
        if component.get("custom_id"):
            values.append(component["custom_id"])
        for child in component.get("components", []):
            visit(child)

    for row in payload["components"]:
        visit(row)
    return values


class ProbeButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="E2E 확인",
            style=discord.ButtonStyle.success,
            custom_id="e2e_probe_confirm",
        )

    async def callback(self, interaction) -> None:
        await interaction.response.edit_message(content="[E2E] component callback passed", view=self.view)


class ProbeSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="E2E option",
            custom_id="e2e_probe_select",
            options=[discord.SelectOption(label="Alpha", value="alpha")],
        )


class ProbeView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ProbeButton())
        self.add_item(ProbeSelect())


class DiscordSuiteRunner:
    def __init__(self, bot, guild_id: int, channel_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def execute(self, run: TestRun, trigger: discord.Message) -> None:
        run.trigger_message_id = trigger.id
        thread = await self._create_thread(trigger, run)
        run.thread_id = thread.id
        run.thread_jump_url = f"https://discord.com/channels/{trigger.guild.id}/{thread.id}"
        ctx = RunContext(self.bot, thread, trigger.author, trigger.guild)
        await ctx.send(f"[E2E:{run.run_id}] `{run.suite}` 실행을 시작합니다.")

        checks: list[CheckResult] = []
        suite_order = self._suite_order(run.suite)
        for suite in suite_order:
            method = getattr(self, f"_run_{suite}")
            try:
                checks.extend(await method(run, ctx))
            except Exception as exc:
                logger.exception("E2E suite %s failed", suite)
                checks.append(CheckResult(suite, "failed", f"{type(exc).__name__}: {exc}"))

        summary_ok = all(check.status != "failed" for check in checks)
        summary = discord.Embed(
            title=f"E2E {run.suite}: {'PASS' if summary_ok else 'FAIL'}",
            description="\n".join(
                f"{'✅' if item.status == 'passed' else '❌' if item.status == 'failed' else '⏭️'} {item.name}"
                for item in checks
            )[:4000],
            color=discord.Color.green() if summary_ok else discord.Color.red(),
        )
        await ctx.send(embed=summary)
        self.bot.e2e_runtime.manager.complete_functional(run, checks)

    @staticmethod
    def _suite_order(suite: str) -> tuple[str, ...]:
        if suite == "all":
            return (
                "gateway", "components", "gameflow", "commands", "dungeon",
                "semantics", "roguelike", "rewards", "balance",
                "farming", "buildcraft", "economy",
            )
        return (suite,)

    async def _create_thread(self, trigger: discord.Message, run: TestRun):
        name = f"e2e-{run.run_id[:8]}-{run.suite}"[:100]
        try:
            return await trigger.create_thread(name=name, auto_archive_duration=60)
        except discord.HTTPException:
            # A pre-existing thread or a channel without thread support should not
            # silently move the test to another guild/channel.
            if isinstance(trigger.channel, discord.Thread):
                return trigger.channel
            raise

    async def _run_gateway(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        view = ProbeView()
        message = await ctx.send(
            embed=discord.Embed(title="Gateway proof", color=discord.Color.blurple()),
            view=view,
        )
        fetched, payload = await fetch_payload(message)
        ok = (
            fetched.author.id == self.bot.user.id
            and fetched.guild.id == self.guild_id
            and fetched.channel.id == run.thread_id
            and payload["embeds"][0].get("title") == "Gateway proof"
            and "e2e_probe_confirm" in _all_custom_ids(payload)
        )
        return [CheckResult("gateway-message-roundtrip", "passed" if ok else "failed", evidence=payload)]

    async def _run_components(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        from cogs.e2e_gameflow import E2EGameFlow

        view = ProbeView()
        message = await ctx.send("[E2E] component callback pending", view=view)
        _, before = await fetch_payload(message)
        custom_ids = _all_custom_ids(before)
        button = next(child for child in view.children if child.custom_id == "e2e_probe_confirm")
        interaction = E2EGameFlow._FakeInteraction(ctx, message=message)
        await button.callback(interaction)
        _, after = await fetch_payload(message)
        ok = (
            custom_ids == ["e2e_probe_confirm", "e2e_probe_select"]
            and after["content"] == "[E2E] component callback passed"
        )
        return [CheckResult(
            "component-payload-and-callback",
            "passed" if ok else "failed",
            evidence={"before": before, "after": after},
        )]

    async def _run_gameflow(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        cog = self._e2e_cog()
        start = len(ctx.messages)
        await cog._run_e2e(ctx)
        sent = ctx.messages[start:]
        payloads = [(await fetch_payload(message))[1] for message in sent]
        final = payloads[-1]["content"] if payloads else ""
        ok = "완료 (성공)" in final and "일부 실패" not in final
        return [CheckResult("game-service-flow", "passed" if ok else "failed", evidence={"messages": payloads})]

    async def _run_commands(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        cog = self._e2e_cog()
        user = await self._ensure_user(ctx)
        results: list[str] = []
        errors: list[str] = []
        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"
        await cog._run_dungeon_command_ui(ctx, user, results, errors)
        await cog._run_user_commands_ui(ctx, user, results, errors)
        await cog._run_help_ui(ctx, results, errors)
        await cog._run_auction_ui(ctx, results, errors)
        evidence = []
        for message in ctx.messages[-32:]:
            try:
                evidence.append((await fetch_payload(message))[1])
            except discord.NotFound:
                continue
        return [CheckResult(
            "application-commands",
            "failed" if errors else "passed",
            details="; ".join(errors),
            evidence={"results": results, "messages": evidence},
        )]

    async def _run_dungeon(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        cog = self._e2e_cog()
        results: list[str] = []
        errors: list[str] = []
        user = await self._ensure_user(ctx)
        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"
        from service.game_settings import get_guild_settings, set_roguelike_override

        settings = await get_guild_settings(self.guild_id)
        previous_override = settings.roguelike_enabled if settings else None
        try:
            # The trigger author is a driver Bot and Discord forbids Bot-to-Bot
            # DMs. Keep this suite on the legacy flow; the dedicated roguelike
            # suite validates its real Embed/components and state contract.
            await set_roguelike_override(self.guild_id, False)
            await cog._run_dungeon_spawn_smoke(results, errors)
            await cog._run_tower_smoke(results, errors)
            await cog.e2e_dungeon_ui(ctx)
        finally:
            await end_session(ctx.author.id)
            await set_roguelike_override(self.guild_id, previous_override)
        return [CheckResult(
            "dungeon-and-tower-flow",
            "failed" if errors else "passed",
            details="; ".join(errors),
            evidence={"results": results, "user_id": str(user.discord_id)},
        )]

    async def _run_semantics(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        from .semantic_scenarios import run_semantic_scenarios

        return await run_semantic_scenarios(run)

    async def _run_roguelike(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        import random

        from config import ROGUELIKE
        from service.dungeon.roguelike_routes import generate_route_offers
        from service.session import DungeonSession
        from views.roguelike_dungeon import RouteChoiceView, create_route_embed

        user = await self._ensure_user(ctx)
        dungeon = next(iter(static_cache.dungeon_cache.values()))
        session = DungeonSession(user_id=user.discord_id, user=user, dungeon=dungeon)
        session.roguelike_enabled = True
        session.exploration_step = 0
        first = generate_route_offers(1, random.Random(20260813))
        second = generate_route_offers(1, random.Random(20260813))
        signature = lambda values: [
            (item.kind.value, item.risk, item.reward_grade, item.payload) for item in values
        ]
        view = RouteChoiceView(ctx.author.id, session, first)
        message = await ctx.send(embed=create_route_embed(session, first), view=view)
        _, payload = await fetch_payload(message)
        custom_ids = _all_custom_ids(payload)
        trace_rng = random.Random(20260814)
        room_trace = []
        for room in range(1, ROGUELIKE.ROUTE_ROOMS + 1):
            session.exploration_step = room - 1
            offers = generate_route_offers(room, trace_rng)
            trace_view = RouteChoiceView(ctx.author.id, session, offers)
            room_trace.append({
                "room": room,
                "offer_count": len(offers),
                "custom_ids": [child.custom_id for child in trace_view.children],
                "augment_after": room in ROGUELIKE.AUGMENT_ROOMS,
            })
        session.exploration_step = ROGUELIKE.ROUTE_ROOMS
        structure_ok = (
            ROGUELIKE.ROUTE_ROOMS == 8
            and ROGUELIKE.AUGMENT_ROOMS == (2, 4, 6)
            and len(first) == 3
            and signature(first) == signature(second)
            and len(custom_ids) == 3
            and all(value.startswith(f"rl:{session.run_nonce}:1:") for value in custom_ids)
            and [value["room"] for value in room_trace] == list(range(1, 9))
            and [value["room"] for value in room_trace if value["augment_after"]] == [2, 4, 6]
            and all(
                len(value["custom_ids"]) == 3
                and all(custom_id.startswith(f"rl:{session.run_nonce}:{value['room']}:") for custom_id in value["custom_ids"])
                for value in room_trace
            )
            and session.exploration_step + 1 == ROGUELIKE.BOSS_STAGE
        )
        return [CheckResult(
            "roguelike-route-state-and-discord-payload",
            "passed" if structure_ok else "failed",
            evidence={"payload": payload, "routes": signature(first), "room_trace": room_trace},
        )]

    async def _run_rewards(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        import asyncio
        from models.game_system import BoxOpenReceipt
        from models.user_inventory import UserInventory
        from service.item.box_open_service import BoxOpenService
        from views.box_reveal import (
            BoxResultView, BoxRevealView, create_final_embed, create_reveal_embed,
        )

        # A disposable DB user lets the E2E exercise the real transaction while
        # cascading every granted item/skill/receipt during cleanup.
        test_user = await User.create(
            discord_id=-(int(run.run_id.replace("-", "")[:15], 16) % 8_000_000_000_000_000_000 + 1),
            username=f"e2e-reward-{run.run_id[:8]}",
        )
        try:
            inventory = await UserInventory.create(
                user=test_user, item_id=5940, quantity=1, instance_grade=1,
            )
            concurrent = await asyncio.gather(
                BoxOpenService.open_boxes(test_user, inventory.id, 1, f"e2e:{run.run_id}"),
                BoxOpenService.open_boxes(test_user, inventory.id, 1, f"e2e:{run.run_id}"),
            )
            batch = next(value for value in concurrent if not value.replayed)
            concurrent_replay = next(value for value in concurrent if value.replayed)
            receipt = await BoxOpenReceipt.get_or_none(interaction_id=f"e2e:{run.run_id}")
            replay = await BoxOpenService.open_boxes(
                test_user, inventory.id, 1, f"e2e:{run.run_id}",
            )
            reveal_view = BoxRevealView(ctx.author.id)
            message = await ctx.send(
                embed=create_reveal_embed(batch, "closed"), view=reveal_view
            )
            stages = []
            for stage in ("closed", "shake", "type", "grade"):
                if stage != "closed":
                    await message.edit(embed=create_reveal_embed(batch, stage), view=reveal_view)
                stages.append((await fetch_payload(message))[1])
            await message.edit(
                embed=create_final_embed(batch),
                view=BoxResultView(ctx.author.id, batch),
            )
            _, payload = await fetch_payload(message)
            custom_ids = set(_all_custom_ids(payload))
            stage_titles = [value["embeds"][0].get("title", "") for value in stages]
            ok = (
                receipt is not None
                and len(batch.outcomes) == 1
                and concurrent_replay.outcomes[0].to_dict() == batch.outcomes[0].to_dict()
                and replay.replayed
                and replay.outcomes[0].to_dict() == batch.outcomes[0].to_dict()
                and await UserInventory.get_or_none(id=inventory.id) is None
                and len(set(stage_titles)) == 4
                and "box_reveal:skip" in _all_custom_ids(stages[0])
                and {"box_reveal:again", "box_reveal:inventory", "box_reveal:close"}.issubset(custom_ids)
            )
            return [CheckResult(
                "reward-transaction-idempotency-and-discord-payload",
                "passed" if ok else "failed",
                evidence={
                    "stages": stages,
                    "payload": payload,
                    "outcomes": [value.to_dict() for value in batch.outcomes],
                    "postgres_concurrent_replay": concurrent_replay.replayed,
                },
            )]
        finally:
            await test_user.delete()

    async def _run_balance(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        from config import BALANCE_V2
        from models import EquipmentItem, Monster, Skill_Model
        from tools.balance_v2 import audit
        from tools.headless_balance_runtime import RuntimeSimulator
        from tools.skill_ecosystem_v3 import audit as audit_skill_ecosystem
        from scripts.update_monster_skill_connectivity import verify as verify_monster_connectivity

        result = audit()
        skill_v3 = audit_skill_ecosystem()
        persisted_connectivity = await verify_monster_connectivity()
        database_counts = {
            "equipment": await EquipmentItem.all().count(),
            "skills": await Skill_Model.all().count(),
            "monsters": await Monster.all().count(),
        }
        formulas_ok = (
            BALANCE_V2.base_stats(1).attack == 15
            and BALANCE_V2.base_stats(100).hp == 2582
            and BALANCE_V2.action_rate(100) == 1.0
            and BALANCE_V2.action_rate(300) == 1.5
            and BALANCE_V2.hit_rate(95, 5) == 0.90
        )
        counts_ok = (
            database_counts["equipment"] == result["counts"]["equipment"]
            and database_counts["skills"] == result["counts"]["skills"]
            and database_counts["monsters"] == result["counts"]["monsters"]
        )
        simulator = RuntimeSimulator(int(run.run_id.replace("-", "")[:12], 16))
        encounter_actions = {
            kind: simulator.encounter(50, "balanced", kind)[2]
            for kind in ("CommonMob", "EliteMob", "BossMob")
        }
        # A 100-season sample can flip a level-band median on a single item.
        # Keep the Discord gate deterministic enough to test the economy
        # contract instead of sampling noise.
        economy = simulator.season_economy(2_000)
        runtime_ok = (
            1 <= encounter_actions["CommonMob"] <= 4
            and 3 <= encounter_actions["EliteMob"] <= 8
            and 6 <= encounter_actions["BossMob"] <= 15
            and economy["median_level_50_grade"] == "A"
            and economy["median_level_70_grade"] == "S"
            and economy["median_level_90_grade"] == "SS"
            and economy["level_100_ss_slots"] == 9
        )
        embed = discord.Embed(
            title="⚖️ Balance V2 · Skill V3 검증",
            description="런타임 공식, 스킬 계약, 몬스터 FSM과 시드 DB의 일치를 검사합니다.",
            color=discord.Color.green() if result["passed"] and skill_v3["passed"] and formulas_ok and counts_ok and runtime_ok else discord.Color.red(),
        )
        embed.add_field(name="프로필", value=BALANCE_V2.version, inline=True)
        embed.add_field(name="장비/스킬/몬스터", value=f"{database_counts['equipment']}/{database_counts['skills']}/{database_counts['monsters']}", inline=True)
        embed.add_field(
            name="몬스터 스킬 연결",
            value=f"{skill_v3['monster_skills_in_combat_decks']}/{skill_v3['monster_skill_contracts']}",
            inline=True,
        )
        embed.add_field(name="CP 최대 편차", value=f"{result['equipment_max_cp_deviation']:.2%}", inline=True)
        message = await ctx.send(embed=embed, view=ProbeView())
        _, payload = await fetch_payload(message)
        payload_ok = (
            payload["embeds"][0].get("title") == "⚖️ Balance V2 · Skill V3 검증"
            and "e2e_probe_confirm" in _all_custom_ids(payload)
        )
        ok = (
            result["passed"] and skill_v3["passed"] and formulas_ok and counts_ok
            and runtime_ok and payload_ok
            and persisted_connectivity["verified_assignments"] == 65
        )
        return [CheckResult(
            "balance-v2-data-runtime-and-discord-contract",
            "passed" if ok else "failed",
            evidence={
                "audit": result, "skill_v3": skill_v3, "database_counts": database_counts,
                "persisted_connectivity": persisted_connectivity,
                "encounter_actions": encounter_actions, "economy": economy,
                "payload": payload,
            },
        )]

    async def _run_farming(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        from models import UserCraftingWallet, UserFarmProgress
        from service.item.progression_service import complete_source

        test_user = await User.create(
            discord_id=-(int(run.run_id.replace("-", "")[:15], 16) % 8_000_000_000_000_000_000 + 101),
            username=f"e2e-farming-{run.run_id[:8]}",
        )
        try:
            results = [await complete_source(test_user, "normal", "E2E 지역") for _ in range(8)]
            wallet = await UserCraftingWallet.get(user=test_user)
            progress = await UserFarmProgress.get(user=test_user, source_type="normal", source_key="E2E 지역")
            embed = discord.Embed(title="🧭 Farming V4", description=f"진척 {progress.progress}/8 · 인장 {wallet.source_seals.get('E2E 지역', 0)}")
            message = await ctx.send(embed=embed)
            _, payload = await fetch_payload(message)
            ok = results[-1].seals_awarded == 1 and progress.progress == 0 and wallet.source_seals.get("E2E 지역") == 1
            return [CheckResult("farming-source-progress-and-discord-contract", "passed" if ok else "failed", evidence=payload)]
        finally:
            await test_user.delete()

    async def _run_buildcraft(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        from models import Skill_Model, UserBuildPresetItem, UserSkillDeck
        from service.buildcraft_service import analyze_build, apply_build, save_build

        test_user = await User.create(
            discord_id=-(int(run.run_id.replace("-", "")[:15], 16) % 8_000_000_000_000_000_000 + 201),
            username=f"e2e-build-{run.run_id[:8]}", level=100, stat_points=297,
        )
        try:
            skills = list(await Skill_Model.filter(player_obtainable=True).limit(10))
            for index, skill in enumerate(skills):
                await UserSkillDeck.create(user=test_user, slot_index=index, skill=skill)
            preset = await save_build(test_user, "E2E 빌드", note="통합 프리셋")
            applied = await apply_build(test_user, preset.id)
            analysis = await analyze_build(test_user)
            refs = await UserBuildPresetItem.filter(preset=preset).count()
            embed = discord.Embed(title="🧩 Buildcraft V4", description=f"{applied.name} · 연계 {len(analysis['links'])} · 장비 참조 {refs}")
            message = await ctx.send(embed=embed)
            _, payload = await fetch_payload(message)
            ok = applied.name == "E2E 빌드" and len(skills) == 10 and len(test_user.equipped_skill) == 10
            return [CheckResult("build-preset-analysis-and-discord-contract", "passed" if ok else "failed", evidence=payload)]
        finally:
            await test_user.delete()

    async def _run_economy(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        import random
        from models import EquipmentItem, UserCraftingWallet, UserEquipmentAffix
        from service.item.inventory_service import InventoryService
        from service.item.progression_service import reforge_affix, salvage_equipment

        test_user = await User.create(
            discord_id=-(int(run.run_id.replace("-", "")[:15], 16) % 8_000_000_000_000_000_000 + 301),
            username=f"e2e-economy-{run.run_id[:8]}", gold=10_000_000,
        )
        try:
            definition = await EquipmentItem.filter(equip_pos__not_isnull=True).first()
            first = await InventoryService.add_item(test_user, definition.item_id, instance_grade=5)
            second = await InventoryService.add_item(test_user, definition.item_id, instance_grade=5)
            before = list(await UserEquipmentAffix.filter(inventory_item=first).order_by("position"))
            wallet = await UserCraftingWallet.get(user=test_user)
            wallet.equipment_essence = 1000
            await wallet.save(update_fields=["equipment_essence"])
            reforge = await reforge_affix(test_user, first.id, 0, f"e2e-reforge:{run.run_id}", rng=random.Random(42))
            salvaged = await salvage_equipment(test_user, second.id, f"e2e-salvage:{run.run_id}", confirmed=True)
            replay = await salvage_equipment(test_user, second.id, f"e2e-salvage:{run.run_id}", confirmed=True)
            after = list(await UserEquipmentAffix.filter(inventory_item=first).order_by("position"))
            embed = discord.Embed(title="♻️ Economy V4", description=f"옵션 {len(after)} · 재련 {reforge['after']['id']} · 정수 +{salvaged['essence']}")
            message = await ctx.send(embed=embed)
            _, payload = await fetch_payload(message)
            ok = len(before) == 2 and len(after) == 2 and salvaged == replay
            return [CheckResult("equipment-reforge-salvage-idempotency", "passed" if ok else "failed", evidence=payload)]
        finally:
            await test_user.delete()

    async def _run_visual(self, run: TestRun, ctx: RunContext) -> list[CheckResult]:
        user = await self._ensure_user(ctx)
        os.environ["E2E_UI_AUTOPILOT"] = "FALSE"
        builders = {
            "dungeon-select": self._visual_dungeon_select,
            "combat": self._visual_combat,
            "inventory": self._visual_inventory,
            "skill-deck": self._visual_skill_deck,
            "auction": self._visual_auction,
            "tower": self._visual_tower,
            "raid-lobby": self._visual_raid_lobby,
            "user-info": self._visual_user_info,
        }
        failures: list[str] = []
        for case_id in VISUAL_CASE_IDS:
            try:
                message = await builders[case_id](ctx, user)
                _, payload = await fetch_payload(message)
                if not payload["embeds"]:
                    raise RuntimeError("visual message has no embed")
                run.visual_cases.append({
                    "case_id": case_id,
                    "message_id": str(message.id),
                    "jump_url": message.jump_url,
                    "payload": payload,
                    "viewport": {"width": 1440, "height": 1000, "zoom": 1.0},
                    "theme": "dark",
                    "locale": "ko",
                    "thresholds": {"dhash_distance": 8, "changed_pixel_ratio": 0.03},
                })
            except Exception as exc:
                logger.exception("Could not build visual case %s", case_id)
                failures.append(f"{case_id}: {type(exc).__name__}: {exc}")
        return [CheckResult(
            "visual-case-publication",
            "failed" if failures else "passed",
            details="; ".join(failures),
            evidence={"published": [item["case_id"] for item in run.visual_cases]},
        )]

    async def _visual_dungeon_select(self, ctx: RunContext, user: User):
        from models.repos.dungeon_repo import find_all_dungeon
        from views.dungeon_select_view import DungeonSelectView

        session = DungeonSession(user_id=user.discord_id, user=user)
        dungeons = find_all_dungeon()
        embed = discord.Embed(
            title="🎯 던전을 선택하세요",
            description="드롭다운에서 던전을 선택한 후 입장하거나 취소하세요.",
            color=discord.Color.blurple(),
        )
        return await ctx.send(embed=embed, view=DungeonSelectView(ctx.author, dungeons, session, timeout=None))

    async def _visual_combat(self, ctx: RunContext, user: User):
        from service.dungeon.combat_context import CombatContext
        from service.dungeon.dungeon_ui import create_battle_embed_multi
        from service.dungeon.encounter_processor import _spawn_monster_group
        from views.combat_control_view import CombatControlView

        dungeon = next(iter(static_cache.dungeon_cache.values()))
        monsters = _spawn_monster_group(dungeon.id, progress=0.15)
        context = CombatContext.from_group(monsters)
        context.user = user
        context.initialize_gauges(user)
        session = DungeonSession(user_id=user.discord_id, user=user)
        session.content_type = ContentType.NORMAL_DUNGEON
        session.in_combat = True
        session.combat_context = context
        session.participants = {}
        embed = create_battle_embed_multi(user, context, deque(["```전투가 시작되었습니다.```"]), {}, session)
        return await ctx.send(embed=embed, view=CombatControlView(session, user.discord_id, timeout=None))

    async def _invoke_command_visual(self, ctx: RunContext, cog_name: str, command_name: str):
        from cogs.e2e_gameflow import E2EGameFlow

        cog = self.bot.get_cog(cog_name)
        if not cog:
            raise RuntimeError(f"missing cog: {cog_name}")
        start = len(ctx.messages)
        interaction = E2EGameFlow._FakeInteraction(ctx)
        command = getattr(cog, command_name)
        await command.callback(cog, interaction)
        # Autopilot commands can publish an informational follow-up after the
        # actual View. Select the newest real embed produced by this command.
        message = next(
            (candidate for candidate in reversed(ctx.messages[start:]) if candidate.embeds),
            None,
        )
        if message is None:
            raise RuntimeError(f"{command_name} did not create an embed response")
        return message

    async def _visual_inventory(self, ctx: RunContext, user: User):
        from service.item.inventory_service import InventoryService
        from service.skill.skill_ownership_service import SkillOwnershipService
        from views.inventory import InventoryView

        inventory = await InventoryService.get_inventory(user)
        owned_skills = await SkillOwnershipService.get_all_owned_skills(user)
        view = InventoryView(
            user=ctx.author,
            db_user=user,
            inventory=list(inventory),
            owned_skills=owned_skills,
            timeout=None,
        )
        message = await ctx.send(embed=view.create_embed(), view=view)
        view.message = message
        return message

    async def _visual_skill_deck(self, ctx: RunContext, user: User):
        # The production command waits for user input. Autopilot stops that wait
        # after the initial real message is published, without removing its View.
        previous = os.environ.get("E2E_UI_AUTOPILOT")
        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"
        try:
            return await self._invoke_command_visual(ctx, "DungeonCommand", "skill_deck")
        finally:
            if previous is None:
                os.environ.pop("E2E_UI_AUTOPILOT", None)
            else:
                os.environ["E2E_UI_AUTOPILOT"] = previous

    async def _visual_auction(self, ctx: RunContext, user: User):
        from views.auction.main_view import AuctionMainView

        view = AuctionMainView(user=ctx.author, db_user=user, timeout=None)
        await view.initialize()
        message = await ctx.send(embed=view.create_embed(), view=view)
        view.message = message
        return message

    async def _visual_user_info(self, ctx: RunContext, user: User):
        from models.user_equipment import UserEquipment
        from service.item.equipment_service import EquipmentService
        from service.item.set_detection_service import SetDetectionService
        from service.player.healing_service import HealingService
        from service.skill.skill_deck_service import SkillDeckService
        from views.user_info_view import UserInfoView

        await HealingService.apply_natural_regen(user)
        equipment = await UserEquipment.filter(user=user).prefetch_related(
            "inventory_item__item"
        )
        await EquipmentService.apply_equipment_stats(user)
        skill_deck = await SkillDeckService.get_deck_as_list(user)
        set_summary = await SetDetectionService.get_set_summary(user)
        view = UserInfoView(
            discord_user=ctx.author,
            user=user,
            equipment=list(equipment),
            skill_deck=skill_deck,
            set_summary=set_summary,
        )
        # Golden capture is asynchronous and can happen long after publication.
        # Keep the real production View alive until the run cleanup removes it.
        view.timeout = None
        return await ctx.send(embed=view.create_embed(), view=view)

    async def _visual_tower(self, ctx: RunContext, user: User):
        from service.session import create_session
        from service.tower.tower_service import initialize_tower_session
        from service.tower.tower_season_service import get_current_season
        from views.tower_view import TowerEntryView

        await end_session(user.discord_id)
        session = await create_session(user.discord_id)
        progress = await initialize_tower_session(user, session)
        view = TowerEntryView(ctx.author, timeout=None)
        message = await ctx.send(embed=view.create_embed(get_current_season(), progress), view=view)
        await end_session(user.discord_id)
        return message

    async def _visual_raid_lobby(self, ctx: RunContext, user: User):
        from service.raid.raid_lobby_service import create_raid_lobby, close_raid_lobby
        from views.raid_lobby_view import create_raid_lobby_embed, RaidLobbyView

        lobby = create_raid_lobby(
            leader_id=user.discord_id,
            raid_id=1,
            raid_name="E2E 테스트 레이드",
            dungeon_id=100,
            required_level=10,
            max_party_size=3,
            voice_channel_id=None,
            timeout_seconds=600,
        )
        message = await ctx.send(embed=create_raid_lobby_embed(lobby), view=RaidLobbyView(lobby, timeout=None))
        close_raid_lobby(user.discord_id)
        return message

    async def _ensure_user(self, ctx: RunContext) -> User:
        user = await find_account_by_discordid(ctx.author.id)
        if user is None:
            user = User(discord_id=ctx.author.id, username=ctx.author.display_name)
            await user.save()
        return user

    def _e2e_cog(self):
        cog = self.bot.get_cog("E2EGameFlow")
        if not cog:
            raise RuntimeError("E2EGameFlow cog is not loaded")
        return cog
