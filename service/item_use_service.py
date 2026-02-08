"""
ItemUseService

아이템 사용 (장비 장착 / 소모품 사용)을 담당합니다.
"""
import logging
import random
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from models import EquipmentItem, Grade, ItemGradeProbability, User
from models.user_inventory import UserInventory
from models.consume_item import ConsumeItem
from models.user_equipment import EquipmentSlot
from resources.item_emoji import ItemType
from config import DROP
from exceptions import (
    ItemNotFoundError,
    ItemNotEquippableError,
    CombatRestrictionError,
    InventoryFullError,
)
from service.session import get_session
from service.equipment_service import EquipmentService
from service.inventory_service import InventoryService

if TYPE_CHECKING:
    from service.session import DungeonSession

logger = logging.getLogger(__name__)


@dataclass
class ItemUseResult:
    """아이템 사용 결과"""
    success: bool
    message: str
    item_name: str
    effect_description: Optional[str] = None


class ItemUseService:
    """아이템 사용 서비스"""

    # equip_pos -> EquipmentSlot 매핑
    EQUIP_POS_TO_SLOT = {
        1: EquipmentSlot.HELMET,
        2: EquipmentSlot.ARMOR,
        3: EquipmentSlot.BOOTS,
        4: EquipmentSlot.WEAPON,
        5: EquipmentSlot.SUB_WEAPON,
        6: EquipmentSlot.GLOVES,
        7: EquipmentSlot.NECKLACE,
        8: EquipmentSlot.RING1,
    }

    @staticmethod
    async def use_item(
        user: User,
        inventory_id: int
    ) -> ItemUseResult:
        """
        아이템 사용

        Args:
            user: 사용자
            inventory_id: 인벤토리 아이템 ID

        Returns:
            사용 결과

        Raises:
            CombatRestrictionError: 전투 중 아이템 사용 시도 (투척 아이템 제외)
            ItemNotFoundError: 아이템을 찾을 수 없음
        """
        # 인벤토리 아이템 조회
        inv_item = await UserInventory.get_or_none(
            id=inventory_id,
            user=user
        ).prefetch_related("item")

        if not inv_item:
            raise ItemNotFoundError(inventory_id)

        # 전투 중 체크 (투척 아이템은 예외)
        session = get_session(user.discord_id)
        if session and session.in_combat:
            # 소비 아이템인 경우 투척 가능 여부 확인
            if inv_item.item.type == ItemType.CONSUME:
                consume = await ConsumeItem.get_or_none(item=inv_item.item)
                # 투척 아이템이 아니면 전투 중 사용 불가
                if not consume or not consume.throwable_damage:
                    raise CombatRestrictionError("아이템 사용")
            else:
                # 소비 아이템이 아니면 전투 중 사용 불가
                raise CombatRestrictionError("아이템 사용")

        item = inv_item.item
        item_type = item.type

        # 타입별 처리
        if item_type == ItemType.EQUIP:
            return await ItemUseService._use_equipment(user, inv_item)
        elif item_type == ItemType.CONSUME:
            return await ItemUseService._use_consumable(user, inv_item)
        elif item_type == ItemType.SKILL:
            return ItemUseResult(
                success=False,
                message="스킬 아이템은 사용할 수 없습니다.",
                item_name=item.name
            )
        else:
            return ItemUseResult(
                success=False,
                message="이 아이템은 사용할 수 없습니다.",
                item_name=item.name
            )

    @staticmethod
    async def _use_equipment(
        user: User,
        inv_item: UserInventory
    ) -> ItemUseResult:
        """장비 아이템 사용 (장착)"""
        item = inv_item.item

        # 장비 정보 조회
        equipment = await EquipmentItem.get_or_none(item=item)
        if not equipment:
            raise ItemNotEquippableError(item.name)

        # equip_pos로 슬롯 결정
        slot = ItemUseService.EQUIP_POS_TO_SLOT.get(equipment.equip_pos)
        if not slot:
            # equip_pos가 없으면 기본적으로 무기 슬롯 사용
            slot = EquipmentSlot.WEAPON

        # 장비 장착
        await EquipmentService.equip_item(user, inv_item.id, slot)

        slot_name = EquipmentSlot.get_korean_name(slot)

        logger.info(
            f"User {user.id} equipped item {item.id} ({item.name}) "
            f"in slot {slot_name}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) [{slot_name}]에 장착했습니다!",
            item_name=item.name,
            effect_description=f"슬롯: {slot_name}"
        )

    @staticmethod
    async def _use_consumable(
        user: User,
        inv_item: UserInventory
    ) -> ItemUseResult:
        """소모품 아이템 사용"""
        item = inv_item.item

        # 소모품 정보 조회
        consume = await ConsumeItem.get_or_none(item=item)
        if not consume:
            return ItemUseResult(
                success=False,
                message="소모품 정보를 찾을 수 없습니다.",
                item_name=item.name
            )

        # 새 박스 시스템 체크
        from config import BOX_CONFIGS
        box_config = BOX_CONFIGS.get(item.id)
        if box_config:
            return await ItemUseService._use_box_consumable(user, inv_item, box_config)

        # 투척 아이템 전투 중 사용
        session = get_session(user.discord_id)
        if consume.throwable_damage and session and session.in_combat:
            return await ItemUseService._use_throwable(user, inv_item, consume, session)

        # 효과 적용
        effect_desc = await ItemUseService._apply_consume_effect(user, consume)

        # 수량 차감
        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            await inv_item.delete()
        else:
            await inv_item.save()

        # 유저 저장
        await user.save()

        logger.info(
            f"User {user.id} used consumable {item.id} ({item.name}): {effect_desc}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) 사용했습니다!",
            item_name=item.name,
            effect_description=effect_desc
        )

    @staticmethod
    async def _apply_consume_effect(user: User, consume: ConsumeItem) -> str:
        """소모품 효과 적용 (버프, 회복, 정화)"""
        from service.dungeon.buff import get_buff_by_tag, remove_status_effects

        effects = []

        # HP 회복
        if consume.amount and consume.amount > 0:
            actual_heal = user.heal(consume.amount)
            effects.append(f"HP +{actual_heal}")

        # 버프 적용
        if consume.buff_type and consume.buff_amount and consume.buff_duration:
            try:
                buff = get_buff_by_tag(consume.buff_type)
                buff.amount = consume.buff_amount
                buff.duration = consume.buff_duration
                user.status.append(buff)
                effects.append(f"{buff.get_description()}")
            except KeyError:
                logger.warning(f"Unknown buff type: {consume.buff_type}")

        # 디버프 정화
        if consume.cleanse_debuff:
            cleanse_msg = remove_status_effects(user, count=99, filter_debuff=True)
            if cleanse_msg:
                effects.append("디버프 정화")

        if not effects:
            effects.append("효과 없음")

        return ", ".join(effects)

    @staticmethod
    async def _use_throwable(
        user: User,
        inv_item: UserInventory,
        consume: ConsumeItem,
        session: "DungeonSession"
    ) -> ItemUseResult:
        """
        투척 아이템 전투 중 사용

        Args:
            user: 사용자
            inv_item: 인벤토리 아이템
            consume: 소모품 정보
            session: 던전 세션

        Returns:
            사용 결과
        """
        item = inv_item.item

        if not session.combat_context or not session.combat_context.monsters:
            return ItemUseResult(
                success=False,
                message="전투 중이 아닙니다.",
                item_name=item.name
            )

        # 투척 데미지 계산 (기본 데미지)
        damage = consume.throwable_damage
        total_damage = 0
        targets_hit = []

        # 모든 적에게 데미지 (AOE)
        for monster in session.combat_context.monsters:
            if monster.is_alive():
                monster.take_damage(damage)
                total_damage += damage
                targets_hit.append(monster.name)

                logger.info(
                    f"User {user.id} threw {item.name} at {monster.name} "
                    f"for {damage} damage"
                )

        # 수량 차감
        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            await inv_item.delete()
        else:
            await inv_item.save()

        # 결과 메시지
        targets_str = ", ".join(targets_hit) if targets_hit else "적"
        effect_desc = f"{targets_str}에게 {damage} 데미지"

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) 투척했습니다!",
            item_name=item.name,
            effect_description=effect_desc
        )

    @staticmethod
    def _calculate_chest_gold(user_level: int, chest_grade: str) -> int:
        grade_multiplier = {
            "normal": 1.0,
            "silver": 2.0,
            "gold": 5.0
        }.get(chest_grade, 1.0)
        base_gold = 20
        gold = int(base_gold * grade_multiplier * (1 + user_level / 10))
        return int(gold * random.uniform(0.8, 1.2))

    @staticmethod
    async def _roll_item_grade(chest_grade: str) -> Optional[str]:
        chest_id_map = {"normal": 1, "silver": 2, "gold": 3}
        chest_id = chest_id_map.get(chest_grade)

        if chest_id is not None:
            grade_probs = await ItemGradeProbability.filter(cheat_id=chest_id).all()
            if grade_probs:
                grades = []
                weights = []
                for entry in grade_probs:
                    if entry.grade is None:
                        continue
                    grade_value = entry.grade.value if hasattr(entry.grade, "value") else str(entry.grade)
                    grades.append(grade_value)
                    weights.append(float(entry.probability or 0))
                if grades and sum(weights) > 0:
                    return random.choices(grades, weights=weights, k=1)[0]

        grades = ["D", "C", "B", "A", "S", "SS", "SSS", "Mythic"]
        weights = [
            DROP.DROP_RATE_D,
            DROP.DROP_RATE_C,
            DROP.DROP_RATE_B,
            DROP.DROP_RATE_A,
            DROP.DROP_RATE_S,
            DROP.DROP_RATE_SS,
            DROP.DROP_RATE_SSS,
            DROP.DROP_RATE_MYTHIC,
        ]
        return random.choices(grades, weights=weights, k=1)[0]

    @staticmethod
    async def _pick_equipment_by_grade(grade_name: str) -> Optional[EquipmentItem]:
        grade = await Grade.get_or_none(name=grade_name)
        if not grade:
            return None
        candidates = await EquipmentItem.filter(grade=grade.id).prefetch_related("item")
        if not candidates:
            return None
        return random.choice(candidates)

    @staticmethod
    async def _pick_skill_by_grade(grade_name: str) -> Optional["Skill_Model"]:
        """
        등급별 스킬 무작위 선택

        Args:
            grade_name: 등급 이름 ("D", "C", "B", "A", "S" 등)

        Returns:
            Skill_Model 또는 None
        """
        from models import Skill_Model

        grade = await Grade.get_or_none(name=grade_name)
        if not grade:
            return None

        # 몬스터 전용 스킬 제외 (ID 9000번대)
        candidates = await Skill_Model.filter(grade=grade.id, id__lt=9000)

        if not candidates:
            return None

        return random.choice(candidates)

    @staticmethod
    async def _roll_item_grade_by_table(table_id: int) -> Optional[str]:
        """
        특정 테이블 ID로 등급 롤

        Args:
            table_id: ItemGradeProbability.cheat_id

        Returns:
            등급 이름 또는 None
        """
        grade_probs = await ItemGradeProbability.filter(cheat_id=table_id).all()
        if not grade_probs:
            return None

        grades = []
        weights = []
        for entry in grade_probs:
            if entry.grade is None:
                continue
            grade_value = entry.grade.value if hasattr(entry.grade, "value") else str(entry.grade)
            grades.append(grade_value)
            weights.append(float(entry.probability or 0))

        if grades and sum(weights) > 0:
            return random.choices(grades, weights=weights, k=1)[0]

        return None

    @staticmethod
    async def _use_box_consumable(
        user: User,
        inv_item: UserInventory,
        box_config: "BoxConfig"
    ) -> ItemUseResult:
        """
        상자 아이템 사용 (새로운 박스 시스템)

        Args:
            user: 사용자
            inv_item: 인벤토리 아이템
            box_config: 상자 설정

        Returns:
            사용 결과
        """
        from config import BoxRewardType
        from service.skill_ownership_service import SkillOwnershipService

        item = inv_item.item

        # 설정 검증
        if not box_config.validate():
            return ItemUseResult(
                success=False,
                message="상자 설정이 올바르지 않습니다.",
                item_name=item.name
            )

        # 보상 타입 선택 (확률 기반)
        reward_types = [r.reward_type for r in box_config.rewards]
        weights = [r.probability for r in box_config.rewards]
        selected_type = random.choices(reward_types, weights=weights, k=1)[0]

        # 선택된 보상 설정 찾기
        reward_config = next(
            r for r in box_config.rewards if r.reward_type == selected_type
        )

        effect_desc = ""

        # 보상 타입별 처리
        if selected_type == BoxRewardType.GOLD:
            # 골드 지급
            gold_gained = ItemUseService._calculate_chest_gold(user.level, "normal")
            gold_gained = int(gold_gained * box_config.gold_multiplier)
            user.gold += gold_gained
            await user.save()
            effect_desc = f"골드 +{gold_gained}"

        elif selected_type == BoxRewardType.EQUIPMENT:
            # 등급 결정
            if reward_config.guaranteed_grade:
                grade_name = reward_config.guaranteed_grade
            elif reward_config.grade_table_id:
                grade_name = await ItemUseService._roll_item_grade_by_table(
                    reward_config.grade_table_id
                )
            else:
                grade_name = await ItemUseService._roll_item_grade("normal")

            if not grade_name:
                return ItemUseResult(
                    success=False,
                    message="등급 판정에 실패했습니다.",
                    item_name=item.name
                )

            # 장비 선택
            equipment = await ItemUseService._pick_equipment_by_grade(grade_name)
            if not equipment or not equipment.item:
                return ItemUseResult(
                    success=False,
                    message="상자에서 나올 장비를 찾을 수 없습니다.",
                    item_name=item.name
                )

            # 인벤토리 추가
            try:
                await InventoryService.add_item(user, equipment.item.id, 1)
            except InventoryFullError:
                return ItemUseResult(
                    success=False,
                    message="인벤토리가 가득 차서 상자를 열 수 없습니다.",
                    item_name=item.name
                )

            effect_desc = f"장비 '{equipment.item.name}' ({grade_name}등급) 획득"

        elif selected_type == BoxRewardType.SKILL:
            # 등급 결정
            if reward_config.guaranteed_grade:
                grade_name = reward_config.guaranteed_grade
            elif reward_config.grade_table_id:
                grade_name = await ItemUseService._roll_item_grade_by_table(
                    reward_config.grade_table_id
                )
            else:
                grade_name = await ItemUseService._roll_item_grade("normal")

            if not grade_name:
                return ItemUseResult(
                    success=False,
                    message="등급 판정에 실패했습니다.",
                    item_name=item.name
                )

            # 스킬 선택
            skill = await ItemUseService._pick_skill_by_grade(grade_name)
            if not skill:
                return ItemUseResult(
                    success=False,
                    message="상자에서 나올 스킬을 찾을 수 없습니다.",
                    item_name=item.name
                )

            # 스킬 추가
            await SkillOwnershipService.add_skill(user, skill.id, quantity=1)
            effect_desc = f"스킬 '{skill.name}' ({grade_name}등급) 획득"

        # 상자 소모
        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            await inv_item.delete()
        else:
            await inv_item.save()

        logger.info(
            f"User {user.id} opened box {item.id} ({item.name}): "
            f"{selected_type.value} - {effect_desc}"
        )

        return ItemUseResult(
            success=True,
            message=f"'{item.name}'을(를) 열었습니다!",
            item_name=item.name,
            effect_description=effect_desc
        )
