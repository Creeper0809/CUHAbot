"""
사용자 정보 조회 View

사용자의 스탯, 장비, 스킬 덱 등을 보여주는 Discord UI입니다.
"""
import discord
from typing import Optional, List

from models import User, UserStatEnum
from models.user_equipment import UserEquipment, EquipmentSlot
from models.user_skill_deck import UserSkillDeck
from models.repos.static_cache import skill_cache_by_id, item_cache
from service.economy.reward_service import RewardService
from utils.grade_display import format_item_name, format_skill_name


class UserInfoView(discord.ui.View):
    """
    사용자 정보 조회 View

    탭 형식으로 기본 정보, 장비, 스킬 덱을 표시합니다.
    """

    def __init__(
        self,
        discord_user: discord.User,
        user: User,
        equipment: List[UserEquipment],
        skill_deck: List[int],
        set_summary: Optional[List] = None,
    ):
        super().__init__(timeout=120)
        self.discord_user = discord_user
        self.user = user
        self.equipment = equipment
        self.skill_deck = skill_deck
        self.set_summary = set_summary or []
        self.current_tab = "info"  # info, equipment, skills

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """본인만 조작 가능"""
        if interaction.user.id != self.discord_user.id:
            await interaction.response.send_message(
                "다른 사람의 정보는 조작할 수 없습니다.",
                ephemeral=True
            )
            return False
        return True

    def create_embed(self) -> discord.Embed:
        """현재 탭에 맞는 Embed 생성"""
        if self.current_tab == "info":
            return self._create_info_embed()
        elif self.current_tab == "equipment":
            return self._create_equipment_embed()
        elif self.current_tab == "skills":
            return self._create_skills_embed()
        return self._create_info_embed()

    def _create_info_embed(self) -> discord.Embed:
        """기본 정보 Embed 생성"""
        embed = discord.Embed(
            title=f"📊 {self.user.get_name()}의 정보",
            color=discord.Color.blue()
        )

        stat = self.user.get_stat()
        max_hp = stat[UserStatEnum.HP]
        total_attack = stat[UserStatEnum.ATTACK]
        total_defense = stat[UserStatEnum.DEFENSE]
        total_speed = stat[UserStatEnum.SPEED]
        total_ap_attack = stat[UserStatEnum.AP_ATTACK]
        total_ap_defense = stat[UserStatEnum.AP_DEFENSE]

        # HP 바
        hp_ratio = self.user.now_hp / max_hp if max_hp > 0 else 0
        hp_bar = self._create_bar(hp_ratio, 20)

        # 기본 전투 스탯
        embed.add_field(
            name="⚔️ 물리 스탯",
            value=(
                f"```\n"
                f"레벨     : Lv.{self.user.level}\n"
                f"체력     : {self.user.now_hp}/{max_hp}\n"
                f"공격력   : {total_attack}\n"
                f"방어력   : {total_defense}\n"
                f"속도     : {total_speed}\n"
                f"```"
            ),
            inline=True
        )

        # 마법 스탯
        embed.add_field(
            name="✨ 마법 스탯",
            value=(
                f"```\n"
                f"마법공격력: {total_ap_attack}\n"
                f"마법방어력: {total_ap_defense}\n"
                f"```"
            ),
            inline=True
        )

        # 5대 능력치
        embed.add_field(
            name="📊 능력치",
            value=(
                f"```\n"
                f"STR(힘)  : {self.user.bonus_str}\n"
                f"INT(지능): {self.user.bonus_int}\n"
                f"DEX(민첩): {self.user.bonus_dex}\n"
                f"VIT(활력): {self.user.bonus_vit}\n"
                f"LUK(행운): {self.user.bonus_luk}\n"
                f"```"
            ),
            inline=True
        )

        # 보조 전투 스탯 (능력치 변환 포함)
        accuracy = stat.get(UserStatEnum.ACCURACY, self.user.accuracy)
        evasion = stat.get(UserStatEnum.EVASION, self.user.evasion)
        crit_rate = stat.get(UserStatEnum.CRITICAL_RATE, self.user.critical_rate)
        crit_damage = stat.get(UserStatEnum.CRITICAL_DAMAGE, self.user.critical_damage)
        drop_rate = self.user.get_drop_rate_bonus()
        equipment_stats = getattr(self.user, "equipment_stats", {})
        lifesteal = equipment_stats.get("lifesteal", 0)

        # 패시브 스킬 보너스 추가
        from service.dungeon.skill import get_passive_stat_bonuses
        passive_bonuses = get_passive_stat_bonuses(self.skill_deck)
        lifesteal += passive_bonuses.get("lifesteal", 0) * 100  # 비율→퍼센트
        drop_rate += passive_bonuses.get("drop_rate", 0) * 100  # 비율→퍼센트

        embed.add_field(
            name="🎯 전투 보조",
            value=(
                f"```\n"
                f"명중률   : {accuracy}%\n"
                f"회피율   : {evasion}%\n"
                f"치명타율 : {crit_rate}%\n"
                f"치명타배율: {crit_damage}%\n"
                f"드롭률   : +{drop_rate:.1f}%\n"
                f"흡혈     : {lifesteal:.1f}%\n"
                f"```"
            ),
            inline=True
        )

        # 회복 및 재화
        regen_rate = self.user.get_hp_regen_rate()
        regen_per_min = max(1, int(max_hp * regen_rate))
        embed.add_field(
            name="💚 회복 / 💰 재화",
            value=(
                f"```\n"
                f"자연회복 : {regen_per_min} HP/분 ({regen_rate:.1%})\n"
                f"골드     : {self.user.gold:,}G\n"
                f"스탯 P   : {self.user.stat_points}P\n"
                f"```"
            ),
            inline=True
        )

        # 시너지 표시
        from service.player.synergy_service import SynergyService
        active_synergies = SynergyService.evaluate_synergies(
            self.user.bonus_str, self.user.bonus_int,
            self.user.bonus_dex, self.user.bonus_vit, self.user.bonus_luk
        )
        if active_synergies:
            synergy_text = SynergyService.format_synergies_display(active_synergies)
            embed.add_field(
                name="✨ 시너지",
                value=synergy_text,
                inline=False
            )

        # 경험치 바 계산
        level_progress = RewardService.get_level_progress(self.user)
        exp_bar = self._create_bar(level_progress["progress"], 20)

        # HP 바 + 경험치 바 표시
        embed.add_field(
            name="❤️ 체력 / ⭐ 경험치",
            value=(
                f"HP: {hp_bar} {int(hp_ratio * 100)}%\n"
                f"EXP: {exp_bar} {int(level_progress['progress'] * 100)}% ({level_progress['exp_in_level']:,}/{level_progress['exp_needed']:,})"
            ),
            inline=False
        )

        embed.set_footer(text="⬇️ 아래 버튼으로 장비/스킬 정보를 확인하세요")
        return embed

    def _create_equipment_embed(self) -> discord.Embed:
        """장비 정보 Embed 생성"""
        embed = discord.Embed(
            title=f"🛡️ {self.user.get_name()}의 장비",
            color=discord.Color.orange()
        )

        # 장비 슬롯 매핑
        equipped_items = {eq.slot: eq for eq in self.equipment}

        # 슬롯별 이모지
        slot_emojis = {
            EquipmentSlot.WEAPON: "⚔️",
            EquipmentSlot.HELMET: "🪖",
            EquipmentSlot.ARMOR: "🛡️",
            EquipmentSlot.GLOVES: "🧤",
            EquipmentSlot.BOOTS: "👢",
            EquipmentSlot.NECKLACE: "📿",
            EquipmentSlot.RING1: "💍",
            EquipmentSlot.RING2: "💍",
            EquipmentSlot.SUB_WEAPON: "🗡️",
        }

        # 좌우로 나누어 표시
        left_slots = [EquipmentSlot.WEAPON, EquipmentSlot.HELMET, EquipmentSlot.ARMOR, EquipmentSlot.GLOVES, EquipmentSlot.BOOTS]
        right_slots = [EquipmentSlot.NECKLACE, EquipmentSlot.RING1, EquipmentSlot.RING2, EquipmentSlot.SUB_WEAPON]

        left_text = []
        for slot in left_slots:
            slot_name = EquipmentSlot.get_korean_name(slot)
            emoji = slot_emojis.get(slot, "❓")
            if slot in equipped_items:
                item_name = self._format_equipped_item_name(equipped_items[slot])
                left_text.append(f"{emoji} {slot_name}: {item_name}")
            else:
                left_text.append(f"{emoji} {slot_name}: -")

        right_text = []
        for slot in right_slots:
            slot_name = EquipmentSlot.get_korean_name(slot)
            emoji = slot_emojis.get(slot, "❓")
            if slot in equipped_items:
                item_name = self._format_equipped_item_name(equipped_items[slot])
                right_text.append(f"{emoji} {slot_name}: {item_name}")
            else:
                right_text.append(f"{emoji} {slot_name}: -")

        embed.add_field(
            name="🔹 주요 장비",
            value="```\n" + "\n".join(left_text) + "\n```",
            inline=True
        )

        embed.add_field(
            name="🔸 장신구",
            value="```\n" + "\n".join(right_text) + "\n```",
            inline=True
        )

        # 세트 효과 표시
        if self.set_summary:
            set_text = []
            for set_name, count, effect_descs in self.set_summary:
                set_text.append(f"✨ {set_name} ({count}개)")
                for desc in effect_descs:
                    set_text.append(f"  • {desc}")

            embed.add_field(
                name="🌟 세트 효과",
                value="```\n" + "\n".join(set_text) + "\n```",
                inline=False
            )

        embed.set_footer(text="⬇️ 아래 버튼으로 다른 정보를 확인하세요")
        return embed

    @staticmethod
    def _format_equipped_item_name(equipment: UserEquipment) -> str:
        item = equipment.inventory_item.item if equipment.inventory_item else None
        if not item:
            return "장착됨"

        enhance = ""
        if equipment.inventory_item.enhancement_level > 0:
            enhance = f" +{equipment.inventory_item.enhancement_level}"

        # 등급별 색상 적용
        grade_id = getattr(item, 'grade_id', None)
        formatted_name = format_item_name(item.name, grade_id)
        return f"{formatted_name}{enhance}"

    def _create_skills_embed(self) -> discord.Embed:
        """스킬 덱 Embed 생성"""
        embed = discord.Embed(
            title=f"✨ {self.user.get_name()}의 스킬 덱",
            color=discord.Color.purple()
        )

        # 스킬 슬롯 표시
        skill_lines = []
        for i, skill_id in enumerate(self.skill_deck):
            slot_num = i + 1
            if skill_id and skill_id in skill_cache_by_id:
                skill = skill_cache_by_id[skill_id]
                # 등급별 색상 적용
                grade_id = skill.skill_model.grade
                formatted_name = format_skill_name(skill.name, grade_id)
                skill_lines.append(f"`{slot_num:2d}` │ **{formatted_name}**")
            elif skill_id:
                skill_lines.append(f"`{slot_num:2d}` │ 스킬 #{skill_id}")
            else:
                skill_lines.append(f"`{slot_num:2d}` │ `비어있음`")

        # 5개씩 나누어 표시
        left_skills = skill_lines[:5]
        right_skills = skill_lines[5:10]

        embed.add_field(
            name="슬롯 1-5",
            value="\n".join(left_skills) if left_skills else "없음",
            inline=True
        )

        embed.add_field(
            name="슬롯 6-10",
            value="\n".join(right_skills) if right_skills else "없음",
            inline=True
        )

        # 스킬 발동 확률 계산 (패시브 제외 - 백에서 셔플 안 됨)
        skill_counts = {}
        active_slot_count = 0
        for skill_id in self.skill_deck:
            if not skill_id:
                continue
            skill = skill_cache_by_id.get(skill_id)
            if skill and skill.is_passive:
                continue
            skill_counts[skill_id] = skill_counts.get(skill_id, 0) + 1
            active_slot_count += 1

        if skill_counts:
            prob_lines = []
            for skill_id, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
                if skill_id in skill_cache_by_id:
                    skill = skill_cache_by_id[skill_id]
                    grade_id = skill.skill_model.grade
                    formatted_name = format_skill_name(skill.name, grade_id)
                    prob = (count / active_slot_count * 100) if active_slot_count > 0 else 0
                    prob_lines.append(f"• {formatted_name}: {prob:.0f}%")

            embed.add_field(
                name="🎲 발동 확률",
                value="\n".join(prob_lines[:6]) if prob_lines else "없음",
                inline=False
            )

        # 활성화된 시너지 (이름만 간단히)
        from service.skill.synergy_service import SynergyService
        active_synergies = SynergyService.get_active_synergies(self.skill_deck)

        if active_synergies:
            synergy_names = [s.name for s in active_synergies]
            embed.add_field(
                name=f"🔮 시너지 ({len(synergy_names)}개)",
                value=", ".join(synergy_names),
                inline=False
            )

        embed.set_footer(text="💡 /덱 명령어로 스킬을 변경할 수 있고, /설명 명령어로 시너지 상세 정보를 확인하세요")
        return embed

    def _create_bar(self, ratio: float, length: int = 10) -> str:
        """프로그레스 바 생성"""
        filled = int(ratio * length)
        empty = length - filled
        return "█" * filled + "░" * empty

    @discord.ui.button(label="📊 기본 정보", style=discord.ButtonStyle.primary, row=0)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """기본 정보 탭"""
        self.current_tab = "info"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="🛡️ 장비", style=discord.ButtonStyle.secondary, row=0)
    async def equipment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """장비 탭"""
        self.current_tab = "equipment"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="✨ 스킬 덱", style=discord.ButtonStyle.secondary, row=0)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """스킬 탭"""
        self.current_tab = "skills"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """닫기"""
        await interaction.response.edit_message(content="정보 조회를 종료했습니다.", embed=None, view=None)
        self.stop()
