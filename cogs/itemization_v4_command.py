"""Discord interfaces for Farming and Buildcraft V4."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import GUILD_IDS
from decorator.account import requires_account
from models import EquipmentItem, Item, UserBuildPreset, UserCraftingWallet, UserFarmProgress, UserLootRule
from models.repos import find_account_by_discordid
from service.buildcraft_service import (
    analyze_build, apply_build, compare_equipment, delete_build, rename_build, save_build,
)
from service.item.affix_service import AFFIX_BY_ID
from service.item.progression_service import (
    craft_target, expand_equipment_storage, inherit_enhancement,
    get_reforge_quote, recover_destroyed_item, reforge_affix,
    salvage_equipment, salvage_many,
)


def requires_v4_feature(feature: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        from service.game_settings import is_v4_feature_enabled
        enabled = await is_v4_feature_enabled(interaction.guild_id, feature)
        if not enabled and not interaction.response.is_done():
            await interaction.response.send_message("이 서버에서는 해당 V4 기능이 아직 비활성 상태입니다.", ephemeral=True)
        return enabled
    return app_commands.check(predicate)


farming = app_commands.Group(name="파밍", description="목표 장비와 지역 인장 진행을 관리합니다.", guild_ids=GUILD_IDS)
build = app_commands.Group(name="빌드", description="장비·스탯·스킬 통합 프리셋을 관리합니다.", guild_ids=GUILD_IDS)
auto_salvage = app_commands.Group(name="자동분해", description="보호 규칙이 적용된 자동 분해를 설정합니다.", guild_ids=GUILD_IDS)
salvage_group = app_commands.Group(name="분해", description="장비를 단일 또는 일괄 분해합니다.", guild_ids=GUILD_IDS)


class ItemizationV4Command(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @farming.command(name="검색", description="장비 이름으로 획득처와 세트를 검색합니다.")
    @requires_v4_feature("farming_focus")
    @requires_account()
    async def farm_search(self, interaction: discord.Interaction, 이름: str):
        from config import BALANCE_V2, DROP
        from models import Dungeon, UserInventory
        from service.auction.auction_service import AuctionService
        user = await find_account_by_discordid(interaction.user.id)
        items = await Item.filter(name__icontains=이름).limit(20)
        rows = list(await EquipmentItem.filter(item_id__in=[item.id for item in items]).prefetch_related("item")) if items else []
        if not rows:
            await interaction.response.send_message("검색되는 장비가 없습니다.", ephemeral=True)
            return
        progress = {row.source_key: row for row in await UserFarmProgress.filter(user=user)}
        lines = []
        for row in rows[:5]:
            state = f" · 진척 {progress[row.acquisition_source].progress}" if row.acquisition_source in progress else ""
            set_text = f" · {row.set_key} 세트" if row.set_key else ""
            source_count = max(1, await EquipmentItem.filter(acquisition_source=row.acquisition_source).count())
            is_dungeon = bool(row.acquisition_source and await Dungeon.filter(name=row.acquisition_source).exists())
            base_pool_rate = DROP.DUNGEON_EQUIPMENT_DROP_RATE if is_dungeon else DROP.EQUIPMENT_DROP_RATE
            target_rate = base_pool_rate / source_count
            weights = BALANCE_V2.drop_weights["boss" if is_dungeon else "normal"]
            grades = "/".join(f"{name} {weight/sum(weights):.1%}" for name, weight in zip(("D","C","B","A","S","SS","SSS","신화"), weights))
            market = await AuctionService.get_market_summary(row.item_id)
            market_text = f"7일 중앙가 {market['median']:,}G" if market["median"] is not None else "최근 거래 없음"
            missing = ""
            if row.set_key:
                set_ids = await EquipmentItem.filter(set_key=row.set_key).values_list("item_id", flat=True)
                owned = await UserInventory.filter(user=user, item_id__in=set_ids).values_list("item_id", flat=True)
                missing = f" · 세트 미보유 {len(set(set_ids) - set(owned))}부위"
            lines.append(
                f"`{row.item_id}` **{row.item.name}** · {row.acquisition_source or '미지정'}{set_text}{state}{missing}\n"
                f"대상 베이스 약 **{target_rate:.3%}** · {market_text}\n등급: {grades}"
            )
        await interaction.response.send_message(embed=discord.Embed(title="🎯 파밍 검색", description="\n".join(lines), color=discord.Color.green()), ephemeral=True)

    @farming.command(name="목표", description="장비를 목표로 지정하고 획득처 진척을 시작합니다.")
    @requires_v4_feature("farming_focus")
    @requires_account()
    async def farm_target(self, interaction: discord.Interaction, 장비_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        equipment = await EquipmentItem.get_or_none(item_id=장비_id).prefetch_related("item")
        if not equipment or not equipment.acquisition_source:
            await interaction.response.send_message("목표로 지정할 수 없는 장비입니다.", ephemeral=True)
            return
        kind = "elite" if (equipment.require_level or 1) >= 31 else "normal"
        row, _ = await UserFarmProgress.get_or_create(user=user, source_type=kind, source_key=equipment.acquisition_source)
        row.target_item_id = 장비_id
        await row.save(update_fields=["target_item_id"])
        await interaction.response.send_message(f"🎯 **{equipment.item.name}** 목표 설정 · `{equipment.acquisition_source}` {row.progress}회", ephemeral=True)

    @farming.command(name="해제", description="현재 장비 파밍 목표를 모두 해제합니다.")
    @requires_v4_feature("farming_focus")
    @requires_account()
    async def farm_target_clear(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        changed = await UserFarmProgress.filter(user=user, target_item_id__not_isnull=True).update(target_item_id=None)
        await interaction.response.send_message(f"파밍 목표 {changed}개를 해제했습니다. 지역 인장 진척은 유지됩니다.", ephemeral=True)

    @farming.command(name="현황", description="지역 인장과 장비 정수 현황을 확인합니다.")
    @requires_v4_feature("farming_focus")
    @requires_account()
    async def farm_status(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        wallet, _ = await UserCraftingWallet.get_or_create(user=user)
        rows = await UserFarmProgress.filter(user=user).order_by("source_key")
        lines = [f"**{row.source_key}** · {row.progress}회 · 인장 누적 {row.seals_earned}" for row in rows[:20]] or ["진행 중인 지역이 없습니다."]
        seals = ", ".join(f"{key} {value}" for key, value in (wallet.source_seals or {}).items() if value) or "없음"
        embed = discord.Embed(title="🧭 파밍 현황", description="\n".join(lines), color=discord.Color.teal())
        embed.add_field(name="재료", value=f"장비 정수 **{wallet.equipment_essence}**\n완성 인장: {seals}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @farming.command(name="제작", description="완성 인장과 정수로 A등급 목표 장비를 제작합니다.")
    @requires_v4_feature("crafting_v4")
    @requires_account()
    async def farm_craft(self, interaction: discord.Interaction, 장비_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        equipment = await EquipmentItem.get_or_none(item_id=장비_id)
        try:
            result = await craft_target(user, equipment.acquisition_source if equipment else "", 장비_id, str(interaction.id))
            await interaction.response.send_message(f"🛠️ A등급 제작 완료 · 인벤토리 `{result['inventory_id']}`", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @build.command(name="저장", description="현재 장비·스탯·스킬을 통합 프리셋으로 저장합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_save(self, interaction: discord.Interaction, 이름: str, 메모: str = ""):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            preset = await save_build(user, 이름, note=메모)
            await interaction.response.send_message(f"💾 **{preset.name}** 빌드를 저장했습니다.", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @build.command(name="보기", description="저장한 통합 빌드를 확인합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_list(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        rows = await UserBuildPreset.filter(user=user).order_by("id")
        text = "\n".join(f"`{row.id}` **{row.name}** · {row.note or '메모 없음'}" for row in rows) or "저장한 빌드가 없습니다."
        await interaction.response.send_message(embed=discord.Embed(title="🧰 통합 빌드", description=text), ephemeral=True)

    @build.command(name="적용", description="통합 빌드를 전투 밖에서 적용합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_apply(self, interaction: discord.Interaction, 프리셋_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await apply_build(user, 프리셋_id)
            missing = f" · 누락 슬롯 {', '.join(map(str, result.missing_slots))}" if result.missing_slots else ""
            await interaction.response.send_message(f"✅ **{result.name}** 적용 완료{missing}", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @build.command(name="이름변경", description="통합 빌드 프리셋의 이름을 변경합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_rename(self, interaction: discord.Interaction, 프리셋_id: int, 새_이름: str):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            preset = await rename_build(user, 프리셋_id, 새_이름)
            await interaction.response.send_message(f"✏️ 빌드 이름을 **{preset.name}**(으)로 변경했습니다.", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @build.command(name="삭제", description="통합 빌드 프리셋을 삭제합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_delete(self, interaction: discord.Interaction, 프리셋_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            name = await delete_build(user, 프리셋_id)
            await interaction.response.send_message(f"🗑️ **{name}** 빌드를 삭제했습니다.", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @build.command(name="분석", description="현재 덱과 장비 옵션의 생성·소비 연결을 분석합니다.")
    @requires_v4_feature("build_presets_v4")
    @requires_account()
    async def build_analysis(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        result = await analyze_build(user)
        links = [f"**{row['tag']}** 생성 {row['setup']} / 소비 {row['payoff']} · 선연계 {row['probability']:.0%}" for row in result["links"][:15]] or ["연계 태그 없음"]
        warnings = []
        if result["orphan_payoffs"]:
            warnings.append("소비기만 있음: " + ", ".join(result["orphan_payoffs"]))
        if result["unused_setups"]:
            warnings.append("생성 후 소비 없음: " + ", ".join(result["unused_setups"]))
        embed = discord.Embed(title="🧩 빌드 연결 분석", description="\n".join(links), color=discord.Color.blurple())
        embed.add_field(name="경고", value="\n".join(warnings) or "고립된 연계가 없습니다.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="장비비교", description="인벤토리 장비를 현재 장착 장비와 비교합니다.")
    @requires_v4_feature("itemization_v4")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def equipment_compare(self, interaction: discord.Interaction, 인벤토리_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await compare_equipment(user, 인벤토리_id)
            lines = [f"{key}: **{value:+g}**" for key, value in result["deltas"].items() if value]
            sets = result["set_change"]
            embed = discord.Embed(title=f"⚖️ {result['current_name']} → {result['candidate_name']}", description="\n".join(lines) or "기본 수치 변화 없음")
            embed.add_field(name="세트", value=f"{sets['from'] or '없음'} → {sets['to'] or '없음'}", inline=False)
            before, after = result["trial"]["before"], result["trial"]["after"]
            embed.add_field(
                name="세팅 시험장",
                value=(
                    f"보스 8행동 피해 **{before['boss_damage_8_actions']:,} → {after['boss_damage_8_actions']:,}**\n"
                    f"적 10행동 후 HP **{before['survival_after_10_enemy_actions']:,} → {after['survival_after_10_enemy_actions']:,}**\n"
                    f"예상 클리어율 **{before['estimated_clear_rate']:.1%} → {after['estimated_clear_rate']:.1%}**\n"
                    f"상대 보상/분 **{before['relative_reward_per_minute']:.2f} → {after['relative_reward_per_minute']:.2f}**"
                ), inline=False,
            )
            if result["warnings"]:
                embed.add_field(name="경고", value="\n".join(f"⚠️ {row}" for row in result["warnings"]), inline=False)
            embed.set_footer(text="시험장 수치는 동레벨 표준 적을 사용한 이론 비교이며 자동 장착 추천이 아닙니다.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @salvage_group.command(name="단일", description="장비 하나를 분해해 장비 정수를 얻습니다.")
    @requires_v4_feature("crafting_v4")
    @requires_account()
    async def salvage(self, interaction: discord.Interaction, 인벤토리_id: int, 확인: bool = False):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await salvage_equipment(user, 인벤토리_id, str(interaction.id), confirmed=확인)
            await interaction.response.send_message(f"♻️ **{result['item_name']}** 분해 · 정수 +{result['essence']}", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @salvage_group.command(name="일괄", description="쉼표로 구분한 장비를 최대 30개 일괄 분해합니다.")
    @requires_v4_feature("crafting_v4")
    @requires_account()
    async def salvage_bulk(self, interaction: discord.Interaction, 인벤토리_ids: str, 확인: bool = False):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            ids = [int(value.strip()) for value in 인벤토리_ids.split(",") if value.strip()]
            result = await salvage_many(user, ids, str(interaction.id), confirmed=확인)
            await interaction.response.send_message(
                f"♻️ 장비 {result['count']}개 분해 · 정수 +{result['essence']}", ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @app_commands.command(name="재련", description="장비 옵션 슬롯 하나를 다시 추첨합니다.")
    @requires_v4_feature("crafting_v4")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def reforge(self, interaction: discord.Interaction, 인벤토리_id: int, 옵션_위치: app_commands.Range[int, 0, 2], 확인: bool = False):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            quote = await get_reforge_quote(user, 인벤토리_id, 옵션_위치)
            if not 확인:
                current = quote["current"]
                definition = AFFIX_BY_ID.get(current["id"])
                tiers = quote["tier_range"]
                await interaction.response.send_message(
                    f"🔎 현재: T{current['tier']} {definition.name if definition else current['id']} +{current['value']:g}\n"
                    f"가능 범위: T{tiers[0]}~T{tiers[1]} · 호환 옵션 {quote['candidate_count']}종\n"
                    f"비용: 정수 {quote['essence_cost']} · {quote['gold_cost']:,}G\n"
                    "같은 명령에 `확인:참`을 넣어 확정하세요.", ephemeral=True,
                )
                return
            result = await reforge_affix(user, 인벤토리_id, 옵션_위치, str(interaction.id))
            after = result["after"]
            definition = AFFIX_BY_ID.get(after["id"])
            await interaction.response.send_message(f"🔨 T{after['tier']} {definition.name if definition else after['id']} +{after['value']:g} · 품질 {after['quality']}%\n정수 {result['essence_cost']} · {result['gold_cost']:,}G", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @app_commands.command(name="계승", description="같은 슬롯의 새 장비로 강화 단계를 계승합니다.")
    @requires_v4_feature("crafting_v4")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def inherit(self, interaction: discord.Interaction, 재료_id: int, 대상_id: int, 보존_촉매: bool = False):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await inherit_enhancement(user, 재료_id, 대상_id, str(interaction.id), use_catalyst=보존_촉매)
            await interaction.response.send_message(f"🧬 계승 완료 · 대상 +{result['enhancement']}", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @app_commands.command(name="장비복구", description="같은 베이스의 파손된 핵으로 새 장비를 +12 복구합니다.")
    @requires_v4_feature("crafting_v4")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def recover(self, interaction: discord.Interaction, 대상_id: int):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await recover_destroyed_item(user, 대상_id, str(interaction.id))
            await interaction.response.send_message(f"🧩 **{result['item_name']}** 복구 완료 · +12", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @app_commands.command(name="창고확장", description="골드로 장비 창고를 50칸 확장합니다. 최대 600칸입니다.")
    @requires_v4_feature("itemization_v4")
    @app_commands.guilds(*GUILD_IDS)
    @requires_account()
    async def storage_expand(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            result = await expand_equipment_storage(user, str(interaction.id))
            await interaction.response.send_message(
                f"📦 장비 창고 **{result['capacity']}칸** · {result['gold_cost']:,}G 사용", ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)

    @auto_salvage.command(name="설정", description="지정 등급 이하 중복 장비를 자동 분해합니다.")
    @requires_v4_feature("itemization_v4")
    @requires_account()
    @app_commands.rename(slots="장비_슬롯", protected_bases="보호_베이스_id")
    @app_commands.describe(
        slots="장비 슬롯 번호를 쉼표로 구분합니다. 비우면 모든 슬롯입니다.",
        protected_bases="자동 분해에서 제외할 장비 베이스 ID를 쉼표로 구분합니다.",
    )
    async def auto_set(
        self,
        interaction: discord.Interaction,
        최대_등급: app_commands.Range[int, 1, 6],
        최소_보호_옵션_티어: app_commands.Range[int, 1, 5] | None = None,
        slots: str | None = None,
        protected_bases: str | None = None,
    ):
        user = await find_account_by_discordid(interaction.user.id)
        try:
            slot_values = sorted({int(value.strip()) for value in (slots or "").split(",") if value.strip()})
            protected_ids = sorted({int(value.strip()) for value in (protected_bases or "").split(",") if value.strip()})
        except ValueError:
            await interaction.response.send_message("슬롯과 베이스 ID는 쉼표로 구분한 숫자로 입력해 주세요.", ephemeral=True)
            return
        if any(value < 1 or value > 9 for value in slot_values) or len(slot_values) > 9:
            await interaction.response.send_message("장비 슬롯은 1~9만 지정할 수 있습니다.", ephemeral=True)
            return
        if any(value <= 0 for value in protected_ids) or len(protected_ids) > 50:
            await interaction.response.send_message("보호 베이스 ID는 양수 50개 이하로 지정할 수 있습니다.", ephemeral=True)
            return
        await UserLootRule.update_or_create(
            user=user,
            defaults={
                "enabled": True,
                "max_grade": 최대_등급,
                "minimum_affix_tier": 최소_보호_옵션_티어,
                "slots": slot_values,
                "excluded_item_ids": protected_ids,
            },
        )
        await interaction.response.send_message("♻️ 자동 분해 설정 완료. 첫 보유·프리셋·장착·잠금·SSS 이상은 항상 보호됩니다.", ephemeral=True)

    @auto_salvage.command(name="해제", description="자동 분해를 해제합니다.")
    @requires_v4_feature("itemization_v4")
    @requires_account()
    async def auto_clear(self, interaction: discord.Interaction):
        user = await find_account_by_discordid(interaction.user.id)
        await UserLootRule.update_or_create(user=user, defaults={"enabled": False})
        await interaction.response.send_message("자동 분해를 해제했습니다.", ephemeral=True)

    @auto_salvage.command(name="미리보기", description="현재 규칙으로 분해될 장비를 변경 없이 확인합니다.")
    @requires_v4_feature("itemization_v4")
    @requires_account()
    async def auto_preview(self, interaction: discord.Interaction):
        from service.item.auto_salvage_service import should_auto_salvage
        user = await find_account_by_discordid(interaction.user.id)
        equipment_ids = await EquipmentItem.all().values_list("item_id", flat=True)
        candidates = await user.inventory.filter(item_id__in=equipment_ids).prefetch_related("item")
        matched = []
        for item in candidates:
            should, _ = await should_auto_salvage(user, item)
            if should:
                matched.append(f"`{item.id}` {item.item.name} · 등급 {item.instance_grade}")
        await interaction.response.send_message(
            embed=discord.Embed(title="♻️ 자동 분해 미리보기", description="\n".join(matched[:30]) or "분해 대상이 없습니다."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    bot.tree.add_command(farming)
    bot.tree.add_command(build)
    bot.tree.add_command(auto_salvage)
    bot.tree.add_command(salvage_group)
    await bot.add_cog(ItemizationV4Command(bot))
