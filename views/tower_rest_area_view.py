"""
주간 타워 휴식공간 UI
"""
from __future__ import annotations

import discord

from config import EmbedColor, SKILL_ID
from models.repos.static_cache import skill_cache_by_id, dungeon_cache
from service.item.inventory_service import InventoryService
from service.item.equipment_service import EquipmentService
from service.skill.skill_deck_service import SkillDeckService
from service.skill.skill_ownership_service import SkillOwnershipService
from service.collection_service import CollectionService
from views.inventory import InventoryView
from views.skill_deck import SkillDeckView
from service.tower.tower_service import get_dungeon_for_floor


class TowerRestAreaView(discord.ui.View):
    def __init__(self, user: discord.User, db_user, session, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.user = user
        self.db_user = db_user
        self.session = session
        self.action = None

    def create_embed(self, reward_result, tower_coins: int) -> discord.Embed:
        cleared_floor = self.session.current_floor
        next_floor = cleared_floor + 1
        dungeon_id = get_dungeon_for_floor(next_floor)
        dungeon = dungeon_cache.get(dungeon_id)
        dungeon_name = dungeon.name if dungeon else f"던전 {dungeon_id}"

        embed = discord.Embed(
            title="🛌 휴식공간 도착",
            description=(
                f"**{cleared_floor}층 클리어!**\n"
                f"💎 경험치: +{reward_result.exp_gained:,}\n"
                f"💰 골드: +{reward_result.gold_gained:,}\n"
                f"🪙 타워 코인: +{tower_coins}\n"
                f"다음 구간: **{next_floor}-{next_floor + 9}층** ({dungeon_name})"
            ),
            color=EmbedColor.DEFAULT
        )
        embed.set_footer(text="휴식공간에서는 스킬/장비 변경과 상점 이용이 가능합니다.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="스킬 변경", style=discord.ButtonStyle.primary, emoji="🧠")
    async def change_skills(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_skill_deck(interaction)

    @discord.ui.button(label="장비 변경", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def change_equipment(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_inventory(interaction)

    @discord.ui.button(label="상점", style=discord.ButtonStyle.secondary, emoji="🛒")
    async def open_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛒 타워 상점은 준비 중입니다.", ephemeral=True)

    @discord.ui.button(label="다음으로", style=discord.ButtonStyle.success, emoji="➡️")
    async def next_area(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "next"
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="귀환", style=discord.ButtonStyle.danger, emoji="🚪")
    async def return_tower(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.action = "return"
        self.stop()
        await interaction.response.edit_message(content="주간 타워를 종료했습니다.", embed=None, view=None)

    async def _open_skill_deck(self, interaction: discord.Interaction) -> None:
        current_deck = await SkillDeckService.get_deck_as_list(self.db_user)

        await SkillOwnershipService.migrate_existing_user(self.db_user, current_deck)
        for skill_id in set(current_deck):
            if skill_id != 0:
                await CollectionService.register_skill(self.db_user, skill_id)

        owned_skills = await SkillOwnershipService.get_all_owned_skills(self.db_user)
        available_skills = [
            skill_cache_by_id[owned.skill_id]
            for owned in owned_skills
            if owned.skill_id in skill_cache_by_id
        ]

        skill_quantities = {owned.skill_id: owned for owned in owned_skills}

        basic_skill_id = SKILL_ID.BASIC_ATTACK_ID
        if basic_skill_id in skill_cache_by_id:
            basic_skill = skill_cache_by_id[basic_skill_id]
            if basic_skill not in available_skills:
                available_skills.insert(0, basic_skill)
            if basic_skill_id not in skill_quantities:
                from models.user_owned_skill import UserOwnedSkill
                skill_quantities[basic_skill_id] = UserOwnedSkill(
                    user=self.db_user,
                    skill_id=basic_skill_id,
                    quantity=999,
                    equipped_count=0
                )

        if not available_skills:
            await interaction.response.send_message(
                "⚠️ 보유한 스킬이 없습니다.",
                ephemeral=True
            )
            return

        view = SkillDeckView(
            user=interaction.user,
            current_deck=current_deck,
            available_skills=available_skills,
            db_user=self.db_user,
            skill_quantities=skill_quantities
        )
        await view.initialize()

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

        await view.wait()

        if view.saved and view.changes_made:
            can_change, error_msg = await SkillOwnershipService.can_change_deck(
                self.db_user, current_deck, view.current_deck
            )
            if not can_change:
                await interaction.followup.send(
                    f"⚠️ 덱 저장 실패: {error_msg}",
                    ephemeral=True
                )
                return

            await SkillOwnershipService.apply_deck_change(
                self.db_user, current_deck, view.current_deck
            )

            for slot_index, skill_id in enumerate(view.current_deck):
                await SkillDeckService.set_skill(self.db_user, slot_index, skill_id)

            await SkillDeckService.load_deck_to_user(self.db_user)

    async def _open_inventory(self, interaction: discord.Interaction) -> None:
        inventory = await InventoryService.get_inventory(self.db_user)
        owned_skills = await SkillOwnershipService.get_all_owned_skills(self.db_user)

        view = InventoryView(
            user=interaction.user,
            db_user=self.db_user,
            inventory=list(inventory),
            owned_skills=owned_skills
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

        await EquipmentService.apply_equipment_stats(self.db_user)
