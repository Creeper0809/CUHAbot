"""
아이템 설명 View

현재 페이지의 아이템 상세 설명을 보여주는 뷰입니다.
"""
from typing import List, Optional

import discord

from config import EmbedColor
from models.user_inventory import UserInventory
from resources.item_emoji import ItemType
from utils.grade_display import format_item_name, format_skill_name


class ItemDescriptionDropdown(discord.ui.Select):
    """아이템 설명 드롭다운"""

    def __init__(self, page_items: List[UserInventory], current_tab: ItemType):
        options = []
        self.current_tab = current_tab

        for inv in page_items[:25]:
            if current_tab == ItemType.SKILL:
                # 스킬인 경우
                from models.repos.static_cache import skill_cache_by_id
                skill = skill_cache_by_id.get(inv.skill_id)
                if skill:
                    grade_id = getattr(skill.skill_model, 'grade', None)
                    formatted_name = format_skill_name(skill.name, grade_id)
                    options.append(
                        discord.SelectOption(
                            label=f"{formatted_name}",
                            description=f"x{inv.quantity}개 보유",
                            value=str(inv.skill_id),
                            emoji="📜"
                        )
                    )
            else:
                # 일반 아이템인 경우
                emoji = self._get_type_emoji(inv.item.type)
                enhance = f" +{inv.enhancement_level}" if inv.enhancement_level > 0 else ""
                instance_grade = getattr(inv, 'instance_grade', 0)
                formatted_name = format_item_name(inv.item.name, instance_grade if instance_grade > 0 else None)

                options.append(
                    discord.SelectOption(
                        label=f"{formatted_name}{enhance}",
                        description=f"x{inv.quantity}개 보유",
                        value=str(inv.id),
                        emoji=emoji
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="아이템 없음",
                    value="0"
                )
            )

        super().__init__(
            placeholder="📖 아이템 선택",
            options=options,
            row=0
        )

    @staticmethod
    def _get_type_emoji(item_type) -> str:
        """아이템 타입별 이모지"""
        if item_type == ItemType.EQUIP:
            return "⚔️"
        elif item_type == ItemType.CONSUME:
            return "🧪"
        return "📦"

    async def callback(self, interaction: discord.Interaction):
        view: ItemDescriptionView = self.view
        item_id = int(self.values[0])

        if item_id == 0:
            await interaction.response.send_message(
                "선택 가능한 아이템이 없습니다.",
                ephemeral=True
            )
            return

        # 선택된 아이템 찾기
        if self.current_tab == ItemType.SKILL:
            # 스킬인 경우
            selected_inv = next((inv for inv in view.page_items if inv.skill_id == item_id), None)
        else:
            # 일반 아이템인 경우
            selected_inv = next((inv for inv in view.page_items if inv.id == item_id), None)

        if selected_inv:
            view.selected_item = selected_inv
            embed = view.create_embed()
            await interaction.response.edit_message(embed=embed, view=view)


class ItemDescriptionView(discord.ui.View):
    """
    아이템 설명 View

    현재 페이지의 아이템 상세 정보를 표시합니다.
    """

    def __init__(
        self,
        user: discord.User,
        page_items: List[UserInventory],
        current_tab: ItemType,
        timeout: int = 60
    ):
        super().__init__(timeout=timeout)
        self.user = user
        self.page_items = page_items
        self.current_tab = current_tab
        self.selected_item: Optional[UserInventory] = None

        self.add_item(ItemDescriptionDropdown(page_items, current_tab))
        self.add_item(CloseButton())

    def create_embed(self) -> discord.Embed:
        """설명 임베드 생성"""
        if self.selected_item:
            # 선택된 아이템이 있으면 아이템 이름을 타이틀로
            if self.current_tab == ItemType.SKILL:
                from models.repos.static_cache import skill_cache_by_id
                skill = skill_cache_by_id.get(self.selected_item.skill_id)
                if skill:
                    grade_id = getattr(skill.skill_model, 'grade', None)
                    formatted_name = format_skill_name(skill.name, grade_id)
                    title = f"✨ {formatted_name}"
                else:
                    title = "✨ 스킬 정보"
            elif self.current_tab == ItemType.EQUIP:
                instance_grade = getattr(self.selected_item, 'instance_grade', 0)
                enhancement = self.selected_item.enhancement_level
                formatted_name = format_item_name(
                    self.selected_item.item.name,
                    instance_grade if instance_grade > 0 else None
                )
                enhance_text = f" +{enhancement}" if enhancement > 0 else ""

                # 축복/저주 상태
                if getattr(self.selected_item, 'is_blessed', False):
                    status_emoji = " ✨"
                elif getattr(self.selected_item, 'is_cursed', False):
                    status_emoji = " 💀"
                else:
                    status_emoji = ""

                title = f"⚔️ {formatted_name}{enhance_text}{status_emoji}"
            else:
                grade_id = getattr(self.selected_item.item, 'grade_id', None)
                formatted_name = format_item_name(self.selected_item.item.name, grade_id)
                title = f"📦 {formatted_name}"
        else:
            title = "📖 아이템 설명"

        embed = discord.Embed(
            title=title,
            color=EmbedColor.DEFAULT
        )

        if self.selected_item:
            if self.current_tab == ItemType.SKILL:
                self._add_skill_description(embed)
            elif self.current_tab == ItemType.EQUIP:
                self._add_equipment_description(embed)
            else:
                self._add_item_description(embed)
        else:
            embed.description = "위 드롭다운에서 아이템을 선택하세요."

        return embed

    def _add_skill_description(self, embed: discord.Embed) -> None:
        """스킬 상세 설명"""
        from models.repos.static_cache import skill_cache_by_id

        skill = skill_cache_by_id.get(self.selected_item.skill_id)
        if not skill:
            embed.description = "❌ 스킬 정보를 찾을 수 없습니다."
            return

        # === 보유 정보 ===
        ownership_info = f"**{self.selected_item.quantity}개** 보유"
        if self.selected_item.equipped_count > 0:
            ownership_info += f" (⚔️ **{self.selected_item.equipped_count}개** 장착 중)"
        embed.add_field(name="📦 보유 현황", value=ownership_info, inline=False)

        # === 스킬 기본 정보 ===
        skill_info_parts = []

        # 타입
        skill_type = getattr(skill.skill_model, 'type', None)
        if skill_type:
            skill_info_parts.append(f"**타입**: {skill_type}")

        # 카테고리
        category = getattr(skill.skill_model, 'category', None)
        if category:
            skill_info_parts.append(f"**분류**: {category}")

        # 속성
        element = getattr(skill.skill_model, 'element', None)
        if element:
            element_emoji = {
                "물리": "⚔️",
                "화염": "🔥",
                "냉기": "❄️",
                "번개": "⚡",
                "물": "💧",
                "신성": "✨",
                "암흑": "🌑"
            }
            element_icon = element_emoji.get(element, "")
            skill_info_parts.append(f"**속성**: {element_icon} {element}")

        if skill_info_parts:
            embed.add_field(
                name="📋 기본 정보",
                value="\n".join(skill_info_parts),
                inline=False
            )

        # === 스킬 효과 설명 ===
        if skill.skill_model.description:
            effect_desc = skill.skill_model.description
            # 패시브 스킬인 경우 표시
            if skill.is_passive:
                effect_desc += "\n\n💡 **패시브 스킬**: 전투 시작 시 자동으로 효과가 적용됩니다"
            embed.add_field(
                name="📝 스킬 효과",
                value=effect_desc,
                inline=False
            )

        # === 키워드 정보 ===
        keywords = getattr(skill.skill_model, 'keywords', None)
        if keywords:
            keyword_desc = f"**{keywords}**\n"
            keyword_desc += "💡 키워드는 스킬의 특수 효과나 연계를 나타냅니다"
            embed.add_field(
                name="🏷️ 키워드",
                value=keyword_desc,
                inline=False
            )

        # === 스킬 컴포넌트 정보 (상세) ===
        if skill.components:
            components_text = []
            for comp in skill.components[:8]:  # 최대 8개
                comp_name = comp.__class__.__name__.replace("Component", "")
                comp_tag = getattr(comp, '_tag', '알 수 없음')
                components_text.append(f"• **{comp_name}** (`{comp_tag}`)")

            if components_text:
                comp_desc = "\n".join(components_text)
                comp_desc += "\n\n💡 컴포넌트는 스킬의 실제 동작을 구성하는 요소입니다"
                embed.add_field(
                    name="🔧 구성 요소",
                    value=comp_desc,
                    inline=False
                )

        # === 획득처 정보 ===
        acquisition = getattr(skill.skill_model, 'acquisition_source', None)
        if acquisition:
            embed.add_field(
                name="📍 획득처",
                value=acquisition,
                inline=False
            )

        # === 사용 가능 여부 ===
        is_player_usable = getattr(skill.skill_model, 'is_player_usable', True)
        if not is_player_usable:
            embed.add_field(
                name="⚠️ 제한 사항",
                value="이 스킬은 플레이어가 사용할 수 없습니다 (몬스터 전용)",
                inline=False
            )

    def _add_equipment_description(self, embed: discord.Embed) -> None:
        """장비 상세 설명 (인스턴스 정보 포함)"""
        from models.repos.static_cache import get_equipment_info
        from service.item.grade_service import GradeService
        from config.grade import get_grade_info

        # 장비 정보 가져오기
        info = get_equipment_info(self.selected_item.item.id)
        instance_grade = getattr(self.selected_item, 'instance_grade', 0)
        enhancement = self.selected_item.enhancement_level
        is_blessed = getattr(self.selected_item, 'is_blessed', False)
        is_cursed = getattr(self.selected_item, 'is_cursed', False)

        # === 기본 정보 ===
        embed.add_field(name="📦 보유 수량", value=f"{self.selected_item.quantity}개", inline=True)

        # 요구 레벨
        if info.get("require_level", 1) > 1:
            embed.add_field(name="📌 요구 레벨", value=f"Lv {info['require_level']}", inline=True)

        # 장착 부위
        if info.get("equip_pos"):
            embed.add_field(name="🎯 장착 부위", value=info['equip_pos'], inline=True)

        # 세트 정보
        if info.get("set_name"):
            embed.add_field(name="🔗 세트", value=info['set_name'], inline=True)

        # === 요구 능력치 (기본 정보 바로 뒤) ===
        req_stats = []
        for stat_name in ["require_str", "require_int", "require_dex", "require_vit", "require_luk"]:
            val = info.get(stat_name, 0)
            if val > 0:
                display_name = stat_name.replace("require_", "").upper()
                req_stats.append(f"{display_name} {val}")

        if req_stats:
            req_desc = " / ".join(req_stats)
            req_desc += "\n💡 장착하려면 위 능력치를 만족해야 합니다"
            embed.add_field(
                name="📋 요구 능력치",
                value=req_desc,
                inline=False
            )

        # === 축복/저주 상태 ===
        if is_blessed or is_cursed:
            if is_blessed:
                status_desc = "✨ **축복받은 장비**\n"
                status_desc += "• 특별한 가호가 깃든 장비입니다\n"
                status_desc += "• 추가 효과가 부여될 수 있습니다"
            else:  # is_cursed
                status_desc = "💀 **저주받은 장비**\n"
                status_desc += "• 사악한 기운이 깃든 장비입니다\n"
                status_desc += "• 착용 시 불리한 효과가 있을 수 있습니다"

            embed.add_field(
                name="🔮 특수 상태",
                value=status_desc,
                inline=False
            )

        # === 스탯 정보 (상세 계산식 포함) ===
        grade_mult = GradeService.get_stat_multiplier(instance_grade) if instance_grade > 0 else 1.0
        enhance_mult = 1 + (enhancement * 0.05) if enhancement > 0 else 1.0

        stat_labels = {
            "attack": "⚔️ 공격력",
            "ap_attack": "🔮 마법공격력",
            "hp": "❤️ 체력",
            "ad_defense": "🛡️ 물리방어",
            "ap_defense": "✨ 마법방어",
            "speed": "⚡ 속도",
        }

        stat_lines = []
        total_bonus = 0

        # ANSI 색상 코드
        green = "\u001b[0;32m"  # 초록색 (등급)
        yellow = "\u001b[1;33m"  # 노란색 (강화)
        reset = "\u001b[0m"

        for key, label in stat_labels.items():
            base_val = info.get(key) or 0
            if base_val <= 0:
                continue

            # 단계별 계산
            grade_bonus = int(base_val * (grade_mult - 1))
            total_before_enhance = int(base_val * grade_mult)
            enhance_bonus = int(total_before_enhance * (enhance_mult - 1))
            final_val = int(base_val * grade_mult * enhance_mult)
            total_bonus += (final_val - base_val)

            # 표시 형식: 전체 스탯(기본 스탯 + 등급 스탯 + 업그레이드 스탯)
            if grade_bonus == 0 and enhance_bonus == 0:
                # 등급/강화 없음: 기본값만
                stat_lines.append(f"{label}: {base_val}")
            else:
                # 전체(기본 + 등급(초록색) + 강화(노란색))
                breakdown_parts = [str(base_val)]
                if grade_bonus > 0:
                    breakdown_parts.append(f"{green}{grade_bonus}{reset}")
                if enhance_bonus > 0:
                    breakdown_parts.append(f"{yellow}{enhance_bonus}{reset}")
                breakdown_text = " + ".join(breakdown_parts)
                stat_lines.append(f"{label}: {final_val} ({breakdown_text})")

        # === 스탯 상세 필드 (왼쪽) ===
        if stat_lines:
            stat_header = "📊 스탯 상세"
            if total_bonus > 0:
                stat_header += f" (총 보너스: +{total_bonus})"

            # ANSI 코드블록으로 감싸기
            stat_value = "```ansi\n" + "\n".join(stat_lines) + "\n```"
            embed.add_field(
                name=stat_header,
                value=stat_value,
                inline=True  # 같은 행에 표시
            )

        # === 특수 효과 필드 (오른쪽) ===
        # 1. 아이템 기본 특수 효과 (EquipmentItem.config)
        # 2. 인스턴스 등급 특수 효과 (UserInventory.special_effects)
        from config.grade import SPECIAL_EFFECT_POOL

        effect_lines = []
        name_map = {e.effect_type: e for e in SPECIAL_EFFECT_POOL}

        # 1) 아이템 기본 특수 효과 (config.components에서 passive_buff 추출)
        equipment_config = info.get("config")
        if equipment_config and isinstance(equipment_config, dict):
            components = equipment_config.get("components", [])
            for component in components:
                # passive_buff 태그를 가진 컴포넌트에서 특수 효과 추출
                if component.get("tag") == "passive_buff":
                    # lifesteal, crit_rate 등의 키를 찾아서 매칭
                    for key, value in component.items():
                        if key == "tag":
                            continue
                        # SPECIAL_EFFECT_POOL에서 해당 효과 찾기
                        effect_def = name_map.get(key)
                        if effect_def:
                            suffix = "%" if effect_def.is_percent else ""
                            effect_lines.append(f"✦ {effect_def.name}: +{value}{suffix}")

        # 2) 인스턴스 등급 특수 효과
        instance_effects = getattr(self.selected_item, 'special_effects', None)
        if instance_effects and isinstance(instance_effects, list):
            for effect in instance_effects:
                effect_def = name_map.get(effect.get("type"))
                if effect_def:
                    value = effect.get("value", 0)
                    suffix = "%" if effect_def.is_percent else ""
                    # 등급 효과는 ⭐ 표시로 구분
                    effect_lines.append(f"⭐ {effect_def.name}: +{value}{suffix}")

        # 특수 효과가 하나라도 있으면 필드 추가
        if effect_lines:
            effect_value = "```ansi\n" + "\n".join(effect_lines) + "\n```"
            embed.add_field(
                name="✨ 특수 효과",
                value=effect_value,
                inline=True  # 같은 행에 표시
            )

        # === 아이템 설명 ===
        if self.selected_item.item.description:
            embed.add_field(
                name="📝 아이템 설명",
                value=self.selected_item.item.description,
                inline=False
            )

        # === 인스턴스 정보 요약 ===
        if instance_grade > 0 or enhancement > 0 or is_blessed or is_cursed:
            summary_parts = []
            if instance_grade > 0:
                summary_parts.append(f"등급 {get_grade_info(instance_grade).name}")
            if enhancement > 0:
                summary_parts.append(f"강화 +{enhancement}")
            if is_blessed:
                summary_parts.append("축복")
            if is_cursed:
                summary_parts.append("저주")

            summary_text = " | ".join(summary_parts)
            embed.set_footer(text=f"인스턴스 정보: {summary_text}")

    def _add_item_description(self, embed: discord.Embed) -> None:
        """일반 아이템 상세 설명 (소비 아이템, 상자 등)"""
        from config import BOX_CONFIGS
        from resources.item_emoji import ItemType

        # === 보유 정보 ===
        embed.add_field(
            name="📦 보유 수량",
            value=f"**{self.selected_item.quantity}개** 보유",
            inline=True
        )

        # === 아이템 타입 정보 ===
        item_type = self.selected_item.item.type
        type_info = {
            ItemType.CONSUME: ("🧪 소비 아이템", "사용 시 즉시 효과가 발동되며 소모됩니다"),
            ItemType.EQUIP: ("⚔️ 장비 아이템", "장착하여 능력치를 향상시킬 수 있습니다"),
            ItemType.ETC: ("📦 기타 아이템", "특수한 용도로 사용되는 아이템입니다"),
        }

        if item_type in type_info:
            type_name, type_desc = type_info[item_type]
            embed.add_field(
                name="🏷️ 아이템 분류",
                value=f"{type_name}\n💡 {type_desc}",
                inline=False
            )

        # === 상자 아이템 특수 정보 ===
        instance_grade = getattr(self.selected_item, 'instance_grade', 0)
        if self.selected_item.item.id in BOX_CONFIGS:
            box_config = BOX_CONFIGS[self.selected_item.item.id]

            box_desc = f"🎁 **{box_config.name}**\n"
            box_desc += "• 사용 시 랜덤한 보상을 획득할 수 있습니다\n"

            # 레벨 범위 정보
            if instance_grade > 0:
                from models.repos.static_cache import get_previous_dungeon_level
                prev_level = get_previous_dungeon_level(instance_grade)
                box_desc += f"• **보상 레벨 범위**: Lv {prev_level} ~ {instance_grade}\n"
                box_desc += "💡 상자를 획득한 던전 레벨에 따라 보상이 결정됩니다"
            else:
                box_desc += "• 보상 레벨이 설정되지 않았습니다"

            embed.add_field(
                name="🎁 상자 정보",
                value=box_desc,
                inline=False
            )

            # 보상 확률 정보
            if box_config.rewards:
                from config.drops import BoxRewardType

                rewards_info = "**보상 구성:**\n"
                reward_type_display = {
                    BoxRewardType.GOLD: "💰 골드",
                    BoxRewardType.EQUIPMENT: "⚔️ 장비",
                    BoxRewardType.SKILL: "✨ 스킬",
                }

                for reward in box_config.rewards:
                    type_name = reward_type_display.get(reward.reward_type, reward.reward_type)
                    probability_pct = reward.probability * 100

                    reward_line = f"• {type_name}: **{probability_pct:.1f}%**"

                    # 확정 등급 표시
                    if reward.guaranteed_grade:
                        reward_line += f" (등급: {reward.guaranteed_grade})"

                    rewards_info += reward_line + "\n"

                # 골드 배율
                if box_config.gold_multiplier != 1.0:
                    rewards_info += f"\n💰 골드 보상 배율: **×{box_config.gold_multiplier}**"

                embed.add_field(
                    name="🎲 보상 확률",
                    value=rewards_info,
                    inline=False
                )

        # === 소비 아이템 효과 정보 ===
        if item_type == ItemType.CONSUME and hasattr(self.selected_item.item, 'consume_item'):
            try:
                # ConsumeItem 모델에서 효과 정보 가져오기
                consume_item = self.selected_item.item.consume_item
                if consume_item:
                    effect_desc = "**사용 효과:**\n"

                    # HP 회복
                    if consume_item.amount and consume_item.amount > 0:
                        effect_desc += f"• ❤️ HP **+{consume_item.amount}** 회복\n"

                    # 버프 효과
                    if consume_item.buff_type and consume_item.buff_amount:
                        buff_display = {
                            "attack": "⚔️ 공격력",
                            "defense": "🛡️ 방어력",
                            "speed": "⚡ 속도",
                            "hp": "❤️ 체력",
                        }.get(consume_item.buff_type, consume_item.buff_type)

                        duration_text = f" ({consume_item.buff_duration}턴)" if consume_item.buff_duration else ""
                        effect_desc += f"• ✨ {buff_display} **+{consume_item.buff_amount}** 증가{duration_text}\n"

                    # 디버프 정화
                    if consume_item.cleanse_debuff:
                        effect_desc += "• 🧹 모든 디버프 제거\n"

                    # 투척 아이템
                    if consume_item.throwable_damage and consume_item.throwable_damage > 0:
                        effect_desc += f"• 💣 투척 데미지 **{consume_item.throwable_damage}**\n"
                        effect_desc += "  💡 전투 중 사용 가능한 투척 아이템입니다\n"
                    else:
                        effect_desc += "\n💡 전투 중에는 사용할 수 없습니다 (탐험 중에만 사용 가능)"

                    embed.add_field(
                        name="💊 효과 상세",
                        value=effect_desc,
                        inline=False
                    )
            except Exception:
                # consume_item 정보를 가져올 수 없는 경우 무시
                pass

        # === 아이템 설명 ===
        if self.selected_item.item.description:
            embed.add_field(
                name="📝 아이템 설명",
                value=self.selected_item.item.description,
                inline=False
            )

        # === 사용 제한 정보 ===
        restrictions = []
        if item_type == ItemType.CONSUME:
            restrictions.append("⚠️ 전투 중 사용 불가")
        # 다른 제한 사항 추가 가능

        if restrictions:
            embed.add_field(
                name="⚠️ 사용 제한",
                value="\n".join(restrictions),
                inline=False
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user


class CloseButton(discord.ui.Button):
    """닫기 버튼"""

    def __init__(self):
        super().__init__(
            label="닫기",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="설명 창을 닫았습니다.",
            embed=None,
            view=None
        )
