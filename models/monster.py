"""
Monster 모델 정의

몬스터 정보 및 전투 관련 런타임 상태를 관리합니다.
"""
import random
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional

from tortoise import models, fields

if TYPE_CHECKING:
    from service.dungeon.buff import Buff
    from service.dungeon.skill import Skill


class Monster(models.Model):
    """
    몬스터 모델

    DB 필드와 런타임 필드를 분리하여 관리합니다.
    런타임 필드는 __init__에서 인스턴스별로 초기화됩니다.
    """

    # ==========================================================================
    # DB 필드
    # ==========================================================================
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    hp = fields.IntField()
    attack = fields.IntField()

    # ==========================================================================
    # 런타임 필드 (DB 미저장) - __init__에서 초기화
    # ==========================================================================
    speed: int
    now_hp: int
    status: list["Buff"]
    use_skill: list[int]
    skill_queue: list[int]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._init_runtime_fields()

    def _init_runtime_fields(self) -> None:
        """런타임 필드 초기화 (인스턴스별로 독립적인 리스트 생성)"""
        self.speed = 10
        self.now_hp = getattr(self, 'hp', 0)
        self.status = []
        self.use_skill = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.skill_queue = []

    def next_skill(self) -> Optional["Skill"]:
        """
        덱에서 다음 스킬을 랜덤하게 선택하여 반환

        Returns:
            선택된 스킬 객체, 스킬이 없으면 None
        """
        from models.repos.skill_repo import get_skill_by_id

        if not self.skill_queue:
            self.skill_queue = self.use_skill[:]
            random.shuffle(self.skill_queue)

        skill_id = self.skill_queue.pop()
        if skill_id == 0:
            return None

        return get_skill_by_id(skill_id)

    def get_name(self) -> str:
        """몬스터 이름 반환"""
        return self.name

    def copy(self) -> "Monster":
        """
        몬스터 복사본 생성 (전투용)

        Returns:
            독립적인 런타임 상태를 가진 몬스터 복사본
        """
        # DB에서 로드 시 런타임 필드가 없을 수 있음
        if not hasattr(self, 'speed'):
            self._init_runtime_fields()

        new_monster = Monster(
            name=self.name,
            description=self.description,
            hp=self.hp,
            attack=self.attack,
        )
        new_monster.now_hp = self.hp
        new_monster.speed = getattr(self, 'speed', 10)
        new_monster.status = deepcopy(getattr(self, 'status', []))
        new_monster.use_skill = getattr(self, 'use_skill', [0] * 10)[:]
        new_monster.skill_queue = []
        return new_monster

    def on_turn_start(self) -> None:
        """턴 시작 시 호출되는 콜백"""
        pass

    def on_turn_end(self) -> None:
        """턴 종료 시 호출되는 콜백"""
        pass

    def get_stat(self) -> dict:
        """
        현재 스탯 반환 (버프 적용 포함)

        Returns:
            스탯 열거형을 키로 하는 스탯 딕셔너리
        """
        from models import UserStatEnum

        stat = {
            UserStatEnum.HP: self.hp,
            UserStatEnum.SPEED: self.speed,
            UserStatEnum.ATTACK: self.attack,
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
        table = "monster"
