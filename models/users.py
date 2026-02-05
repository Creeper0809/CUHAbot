"""
User 모델 정의

사용자 정보 및 전투 관련 런타임 상태를 관리합니다.
"""
import random
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from tortoise import models, fields

if TYPE_CHECKING:
    from service.dungeon.buff import Buff
    from service.dungeon.skill import Skill


class UserStatEnum(str, Enum):
    """사용자 스탯 열거형"""
    HP = "HP"
    ATTACK = "ATTACK"
    DEFENSE = "DEFENSE"
    SPEED = "SPEED"
    AP_ATTACK = "AP_ATTACK"
    AP_DEFENSE = "AP_DEFENSE"


class User(models.Model):
    """
    사용자 모델

    DB 필드와 런타임 필드를 분리하여 관리합니다.
    런타임 필드는 __init__에서 인스턴스별로 초기화됩니다.
    """

    # ==========================================================================
    # DB 필드
    # ==========================================================================
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField(unique=True)
    username = fields.CharField(max_length=255, null=True)
    cuha_point = fields.BigIntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    user_role = fields.CharField(max_length=255, default="user")

    # 기본 스탯 (분배 가능)
    hp = fields.IntField(default=300)  # 기본 HP
    attack = fields.IntField(default=10)  # 물리 공격력
    defense = fields.IntField(default=5)  # 물리 방어력
    speed = fields.IntField(default=10)  # 속도

    # 마법 스탯
    ap_attack = fields.IntField(default=5)  # 마법 공격력
    ap_defense = fields.IntField(default=5)  # 마법 방어력

    # 레벨 및 경험치
    level = fields.IntField(default=1)
    exp = fields.BigIntField(default=0)  # 현재 경험치
    stat_points = fields.IntField(default=0)  # 분배 가능한 스탯 포인트

    # 상태
    now_hp = fields.IntField(default=100)
    hp_regen = fields.IntField(default=5)  # 분당 HP 회복량
    last_regen_time = fields.DatetimeField(auto_now_add=True)  # 마지막 회복 시간

    # ==========================================================================
    # 런타임 필드 (DB 미저장) - __init__에서 초기화
    # ==========================================================================
    status: list["Buff"]
    equipped_skill: list[int]
    skill_queue: list[int]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._init_runtime_fields()

    def _init_runtime_fields(self) -> None:
        """런타임 필드 초기화 (인스턴스별로 독립적인 리스트 생성)"""
        self.status = []
        self.equipped_skill = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.skill_queue = []

    def next_skill(self) -> Optional["Skill"]:
        """
        덱에서 다음 스킬을 랜덤하게 선택하여 반환

        Returns:
            선택된 스킬 객체, 스킬이 없으면 None
        """
        from models.repos.skill_repo import get_skill_by_id

        if not self.skill_queue:
            self.skill_queue = self.equipped_skill[:]
            random.shuffle(self.skill_queue)

        skill_id = self.skill_queue.pop()
        if skill_id == 0:
            return None

        return get_skill_by_id(skill_id)

    def get_name(self) -> str:
        """사용자 표시 이름 반환"""
        return self.username or f"User#{self.discord_id}"

    def on_turn_start(self) -> None:
        """턴 시작 시 호출되는 콜백"""
        pass

    def on_turn_end(self) -> None:
        """턴 종료 시 호출되는 콜백"""
        pass

    def get_stat(self) -> dict[UserStatEnum, int]:
        """
        현재 스탯 반환 (버프 적용 포함)

        Returns:
            스탯 열거형을 키로 하는 스탯 딕셔너리
        """
        stat: dict[UserStatEnum, int] = {
            UserStatEnum.HP: self.hp,
            UserStatEnum.ATTACK: self.attack,
            UserStatEnum.DEFENSE: self.defense,
            UserStatEnum.SPEED: self.speed,
            UserStatEnum.AP_ATTACK: self.ap_attack,
            UserStatEnum.AP_DEFENSE: self.ap_defense,
        }

        for buff in self.status:
            buff.apply_stat(stat)

        return stat

    def is_dead(self) -> bool:
        """사망 여부 확인"""
        return self.now_hp <= 0

    def take_damage(self, damage: int) -> int:
        """
        데미지를 받음

        Args:
            damage: 받을 데미지량

        Returns:
            실제로 받은 데미지량
        """
        actual_damage = min(damage, self.now_hp)
        self.now_hp -= actual_damage
        return actual_damage

    def heal(self, amount: int) -> int:
        """
        HP 회복

        Args:
            amount: 회복량

        Returns:
            실제로 회복된 HP량
        """
        actual_heal = min(amount, self.hp - self.now_hp)
        self.now_hp += actual_heal
        return actual_heal

    class Meta:
        table = "users"

class SkillEquip(models.Model):
    id = fields.BigIntField(pk=True)
    pos = fields.IntField(null=True)
    user = fields.ForeignKeyField('models.User', related_name='equipped_skills', on_delete=fields.CASCADE)
    skill = fields.ForeignKeyField('models.Skill_Model', related_name='equipped_by_users', on_delete=fields.CASCADE)

    class Meta:
        table = "skill_equip"

