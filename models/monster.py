"""
Monster 모델 정의

몬스터 정보 및 전투 관련 런타임 상태를 관리합니다.
"""
import random
from enum import Enum
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional

from tortoise import models, fields

if TYPE_CHECKING:
    from service.dungeon.status import Buff
    from service.dungeon.skill import Skill


class MonsterTypeEnum(str, Enum):
    COMMON = "CommonMob"
    ELITE = "EliteMob"
    BOSS = "BossMob"
    RAID = "RadeMob"


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
    type = fields.CharEnumField(MonsterTypeEnum, null=True)
    hp = fields.IntField()
    attack = fields.IntField()
    """물리 공격력"""
    defense = fields.IntField(default=0)
    """물리 방어력"""
    ap_attack = fields.IntField(default=0)
    """마법 공격력"""
    ap_defense = fields.IntField(default=0)
    """마법 방어력"""
    speed = fields.IntField(default=10)
    """속도"""
    evasion = fields.IntField(default=0)
    """회피율 (%)"""
    skill_ids = fields.JSONField(default=[])
    """몬스터가 사용하는 스킬 ID 목록 (최대 10개)"""

    attribute = fields.CharField(max_length=20, default="무속성")
    """몬스터 속성 (화염/냉기/번개/수속성/신성/암흑/무속성)"""

    race = fields.CharField(max_length=30, default="미지")
    """몬스터 종족 (슬라임/고블린/언데드/드래곤/마수/정령/골렘/인간형/수생/야수/미지)"""

    drop_skill_ids = fields.JSONField(default=[])
    """처치 시 드롭 가능한 스킬 ID 목록"""

    group_ids = fields.JSONField(default=[])
    """그룹 스폰 가능한 몬스터 ID 목록 (빈 리스트면 솔로 전용)"""

    # ==========================================================================
    # 런타임 필드 (DB 미저장) - __init__에서 초기화
    # ==========================================================================
    now_hp: int
    status: list["Buff"]
    use_skill: list[int]
    skill_queue: list[int]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._init_runtime_fields()

    def _init_runtime_fields(self) -> None:
        """런타임 필드 초기화 (인스턴스별로 독립적인 리스트 생성)"""
        self.now_hp = getattr(self, 'hp', 0)
        self.status = []

        # use_skill은 combat_skill_deck 프로퍼티로 대체 예정 (하위 호환성 유지)
        self.use_skill = self.combat_skill_deck
        self.skill_queue = []

    @property
    def combat_skill_deck(self) -> list[int]:
        """
        전투용 스킬 덱 (항상 10슬롯)

        DB의 skill_ids를 10개 슬롯에 맞게 패딩하여 반환합니다.
        이 프로퍼티를 사용하면 skill_ids와 use_skill의 차이를 명확히 할 수 있습니다.

        Returns:
            10개 슬롯의 스킬 ID 리스트
        """
        db_skill_ids = getattr(self, 'skill_ids', [])
        if db_skill_ids and len(db_skill_ids) > 0:
            # 10개 슬롯에 맞게 패딩 (부족하면 0으로 채움)
            return (list(db_skill_ids) + [0] * 10)[:10]
        else:
            return [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def next_skill(self) -> Optional["Skill"]:
        """
        덱에서 다음 액티브 스킬을 랜덤하게 선택하여 반환
        (패시브 스킬은 덱 셔플에서 제외)

        Returns:
            선택된 스킬 객체, 스킬이 없으면 None
        """
        from models.repos.skill_repo import get_skill_by_id
        from service.dungeon.skill import is_passive_skill

        if not self.skill_queue:
            active_ids = [
                sid for sid in self.use_skill
                if sid != 0 and not is_passive_skill(sid)
            ]
            if not active_ids:
                return None
            self.skill_queue = active_ids[:]
            random.shuffle(self.skill_queue)

        if not self.skill_queue:
            return None

        skill_id = self.skill_queue.pop()
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
        if not hasattr(self, 'status'):
            self._init_runtime_fields()

        new_monster = Monster(
            id=self.id,
            name=self.name,
            description=self.description,
            type=getattr(self, 'type', None),
            hp=self.hp,
            attack=self.attack,
            defense=getattr(self, 'defense', 0),
            ap_attack=getattr(self, 'ap_attack', 0),
            ap_defense=getattr(self, 'ap_defense', 0),
            speed=getattr(self, 'speed', 10),
            evasion=getattr(self, 'evasion', 0),
            skill_ids=getattr(self, 'skill_ids', []),
            drop_skill_ids=getattr(self, 'drop_skill_ids', []),
            attribute=getattr(self, 'attribute', '무속성'),
            race=getattr(self, 'race', '미지'),
            group_ids=getattr(self, 'group_ids', []),
        )
        new_monster.now_hp = self.hp
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
        현재 스탯 반환 (패시브 + 버프 적용 포함)

        Returns:
            스탯 열거형을 키로 하는 스탯 딕셔너리
        """
        from config import DAMAGE
        from models import UserStatEnum
        from service.dungeon.skill import get_passive_stat_bonuses

        stat = {
            UserStatEnum.HP: self.hp,
            UserStatEnum.SPEED: getattr(self, 'speed', 10),
            UserStatEnum.ATTACK: self.attack,
            UserStatEnum.DEFENSE: getattr(self, 'defense', 0),
            UserStatEnum.AP_ATTACK: getattr(self, 'ap_attack', 0),
            UserStatEnum.AP_DEFENSE: getattr(self, 'ap_defense', 0),
            UserStatEnum.ACCURACY: DAMAGE.DEFAULT_ACCURACY,
            UserStatEnum.EVASION: getattr(self, 'evasion', 0),
        }

        # 패시브 스킬 스탯 보너스 적용
        passive = get_passive_stat_bonuses(getattr(self, 'use_skill', []))
        stat[UserStatEnum.ATTACK] = int(stat[UserStatEnum.ATTACK] * (1 + passive["attack_percent"]))
        stat[UserStatEnum.DEFENSE] = int(stat[UserStatEnum.DEFENSE] * (1 + passive["defense_percent"]))
        stat[UserStatEnum.SPEED] = int(stat[UserStatEnum.SPEED] * (1 + passive["speed_percent"]))
        stat[UserStatEnum.HP] = int(stat[UserStatEnum.HP] * (1 + passive["hp_percent"]))
        stat[UserStatEnum.AP_ATTACK] = int(stat[UserStatEnum.AP_ATTACK] * (1 + passive["ap_attack_percent"]))

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
