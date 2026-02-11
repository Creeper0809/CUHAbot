"""
필드 효과 시스템

전투 중 발동되는 필드 효과를 정의하고 처리합니다.
"""
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from models import User, Monster


class FieldEffectType(Enum):
    """필드 효과 타입"""
    BURN_ZONE = "burn_zone"              # 화상 지대
    FREEZE_ZONE = "freeze_zone"          # 동결 확률
    SHOCK_ZONE = "shock_zone"            # 감전 연쇄
    DROWN_TIMER = "drown_timer"          # 익사 타이머
    CHAOS_RIFT = "chaos_rift"            # 차원 불안정
    TIME_WARP = "time_warp"              # 시간 왜곡
    VOID_EROSION = "void_erosion"        # 공허의 잠식
    WATER_PRESSURE = "water_pressure"    # 수압 효과
    AWAKENING_AURA = "awakening_aura"    # 각성의 기운
    ANCIENT_CURSE = "ancient_curse"      # 고대의 저주


@dataclass
class FieldEffectData:
    """필드 효과 데이터"""
    effect_type: FieldEffectType
    name: str
    description: str
    emoji: str


class FieldEffect(ABC):
    """필드 효과 기본 추상 클래스"""

    def __init__(self, data: FieldEffectData):
        self.data = data
        self.turn_count = 0

    @abstractmethod
    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        """
        라운드 시작 시 효과 발동

        Args:
            users: 유저 엔티티 리스트 (리더 + 난입자)
            monsters: 살아있는 몬스터 리스트

        Returns:
            로그 메시지 리스트
        """
        pass

    @abstractmethod
    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        """
        턴 종료 시 효과 발동

        Args:
            actor: 행동한 엔티티

        Returns:
            로그 메시지 리스트
        """
        pass

    def get_display_text(self) -> str:
        """UI 표시용 텍스트"""
        return f"{self.data.emoji} {self.data.name}"


# =============================================================================
# 필드 효과 구현체들
# =============================================================================


class BurnZoneEffect(FieldEffect):
    """화상 지대 - 매 라운드 최대 HP의 2% 데미지"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        from models import UserStatEnum

        logs = []
        self.turn_count += 1

        # 모든 유저에게 데미지
        for user in users:
            if user.now_hp > 0:
                max_hp = user.get_stat()[UserStatEnum.HP]
                damage = max(1, int(max_hp * 0.02))
                user.now_hp = max(0, user.now_hp - damage)
                logs.append(f"🔥 **화상 지대** → **{user.get_name()}** {damage} 데미지")

        # 몬스터들에게 데미지
        for monster in monsters:
            if monster.now_hp > 0:
                damage = max(1, int(monster.hp * 0.02))
                monster.now_hp = max(0, monster.now_hp - damage)
                logs.append(f"🔥 **화상 지대** → **{monster.get_name()}** {damage} 데미지")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class FreezeZoneEffect(FieldEffect):
    """동결 지대 - 매 행동마다 15% 확률로 1턴 동결"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        self.turn_count += 1
        return []

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        import random
        from service.dungeon.status import apply_status_effect
        from service.dungeon.status.cc_effects import FreezeEffect

        logs = []
        if random.random() < 0.15:
            apply_status_effect(actor, FreezeEffect(duration=1))
            logs.append(f"❄️ **동결 지대** → **{actor.get_name()}** 동결!")

        return logs


class ShockZoneEffect(FieldEffect):
    """감전 지대 - 데미지를 입힐 때 10% 확률로 인접 대상에게 연쇄"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        self.turn_count += 1
        return []

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        # 데미지 처리는 damage_pipeline에서 처리
        return []


class DrownTimerEffect(FieldEffect):
    """익사 타이머 - 매 3라운드마다 모두에게 최대 HP의 5% 데미지"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        from models import UserStatEnum

        logs = []
        self.turn_count += 1

        if self.turn_count % 3 == 0:
            # 모든 유저에게 데미지
            for user in users:
                if user.now_hp > 0:
                    max_hp = user.get_stat()[UserStatEnum.HP]
                    damage = max(1, int(max_hp * 0.05))
                    user.now_hp = max(0, user.now_hp - damage)
                    logs.append(f"🌊 **익사 타이머** (R{self.turn_count}) → **{user.get_name()}** {damage} 데미지")

            # 몬스터들에게 데미지
            for monster in monsters:
                if monster.now_hp > 0:
                    damage = max(1, int(monster.hp * 0.05))
                    monster.now_hp = max(0, monster.now_hp - damage)
                    logs.append(f"🌊 **익사 타이머** (R{self.turn_count}) → **{monster.get_name()}** {damage} 데미지")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class ChaosRiftEffect(FieldEffect):
    """차원 불안정 - 매 행동마다 20% 확률로 랜덤 상태이상"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        self.turn_count += 1
        return []

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        import random
        from service.dungeon.status import apply_status_effect
        from service.dungeon.status.dot_effects import BurnEffect, PoisonEffect
        from service.dungeon.status.cc_effects import StunEffect

        logs = []
        if random.random() < 0.20:
            effects = [
                (BurnEffect(stacks=1, duration=2), "화상"),
                (PoisonEffect(stacks=1, duration=2), "중독"),
                (StunEffect(duration=1), "기절"),
            ]
            effect, name = random.choice(effects)
            apply_status_effect(actor, effect)
            logs.append(f"🌀 **차원 불안정** → **{actor.get_name()}** {name} 발생!")

        return logs


class TimeWarpEffect(FieldEffect):
    """시간 왜곡 - 매 라운드 모든 엔티티의 속도 ±20% 랜덤 변동"""

    def __init__(self, data: FieldEffectData):
        super().__init__(data)
        self.original_speeds = {}

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        import random
        from models import UserStatEnum

        logs = []
        self.turn_count += 1

        # 모든 유저 속도 변동
        for user in users:
            if id(user) not in self.original_speeds:
                self.original_speeds[id(user)] = user.get_stat()[UserStatEnum.SPEED]

        # 몬스터 속도 변동
        for monster in monsters:
            if id(monster) not in self.original_speeds:
                self.original_speeds[id(monster)] = monster.speed

            # 속도 랜덤 변동 (-20% ~ +20%)
            variation = random.uniform(-0.2, 0.2)
            original_speed = self.original_speeds[id(monster)]
            new_speed = int(original_speed * (1 + variation))
            monster.speed = max(1, new_speed)

        if self.turn_count == 1:
            logs.append(f"⏰ **시간 왜곡** 발동! 속도가 불안정해진다...")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class VoidErosionEffect(FieldEffect):
    """공허의 잠식 - 매 라운드 모든 버프 지속시간 1턴 추가 감소"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        logs = []
        self.turn_count += 1

        # 모든 유저 버프 잠식
        for user in users:
            if user.status:
                for buff in user.status[:]:
                    if hasattr(buff, 'duration') and buff.duration > 0:
                        buff.duration = max(0, buff.duration - 1)
                        if buff.duration <= 0:
                            user.status.remove(buff)

        # 몬스터 버프 잠식
        for monster in monsters:
            if monster.status:
                for buff in monster.status[:]:
                    if hasattr(buff, 'duration') and buff.duration > 0:
                        buff.duration = max(0, buff.duration - 1)
                        if buff.duration <= 0:
                            monster.status.remove(buff)

        if self.turn_count == 1:
            logs.append(f"🕳️ **공허의 잠식** 발동! 버프가 빠르게 사라진다...")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class WaterPressureEffect(FieldEffect):
    """수압 효과 - 매 라운드 방어력 -10%"""

    def __init__(self, data: FieldEffectData):
        super().__init__(data)
        self.applied = False

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        from service.dungeon.status import DefenseBuff
        from models import UserStatEnum

        logs = []
        self.turn_count += 1

        if not self.applied:
            # 각 엔티티마다 개별 디버프 생성 (방어력 -10%)
            all_entities = []
            for user in users:
                if user.now_hp > 0:
                    all_entities.append(user)
            for monster in monsters:
                all_entities.append(monster)

            for entity in all_entities:
                stat = entity.get_stat()
                defense = stat.get(UserStatEnum.DEFENSE, getattr(entity, 'defense', 0))
                debuff_amount = -int(defense * 0.1)  # 음수로 디버프

                debuff = DefenseBuff()
                debuff.amount = debuff_amount
                debuff.duration = 999
                debuff.is_debuff = True
                entity.status.append(debuff)

            self.applied = True
            logs.append(f"💧 **수압 효과** 발동! 모두의 방어력 -10%")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class AwakeningAuraEffect(FieldEffect):
    """각성의 기운 - 모든 엔티티의 공격력 +15%"""

    def __init__(self, data: FieldEffectData):
        super().__init__(data)
        self.applied = False

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        from service.dungeon.status import AttackBuff
        from models import UserStatEnum

        logs = []
        self.turn_count += 1

        if not self.applied:
            # 각 엔티티마다 개별 버프 생성 (공격력 +15%)
            all_entities = []
            for user in users:
                if user.now_hp > 0:
                    all_entities.append(user)
            for monster in monsters:
                all_entities.append(monster)

            for entity in all_entities:
                stat = entity.get_stat()
                attack = stat.get(UserStatEnum.ATTACK, getattr(entity, 'attack', 0))
                buff_amount = int(attack * 0.15)

                buff = AttackBuff()
                buff.amount = buff_amount
                buff.duration = 999
                entity.status.append(buff)

            self.applied = True
            logs.append(f"✨ **각성의 기운** 발동! 모두의 공격력 +15%")

        return logs

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        return []


class AncientCurseEffect(FieldEffect):
    """고대의 저주 - 매 행동마다 3% 확률로 즉사 (보스 제외)"""

    def on_round_start(self, users: list["User"], monsters: list["Monster"]) -> list[str]:
        self.turn_count += 1
        return []

    def on_turn_end(self, actor: Union["User", "Monster"]) -> list[str]:
        import random
        from service.dungeon.reward_calculator import is_boss_monster
        from models import Monster

        logs = []
        # 보스는 즉사 면역
        if isinstance(actor, Monster) and is_boss_monster(actor):
            return []

        if random.random() < 0.03:
            actor.now_hp = 0
            logs.append(f"💀 **고대의 저주** → **{actor.get_name()}** 즉사!")

        return logs


# =============================================================================
# 필드 효과 팩토리
# =============================================================================


FIELD_EFFECT_DATA = {
    FieldEffectType.BURN_ZONE: FieldEffectData(
        effect_type=FieldEffectType.BURN_ZONE,
        name="화상 지대",
        description="불타는 광산 - 매 라운드 최대 HP의 2% 데미지",
        emoji="🔥"
    ),
    FieldEffectType.FREEZE_ZONE: FieldEffectData(
        effect_type=FieldEffectType.FREEZE_ZONE,
        name="동결 지대",
        description="얼어붙은 호수 - 매 행동마다 15% 확률로 1턴 동결",
        emoji="❄️"
    ),
    FieldEffectType.SHOCK_ZONE: FieldEffectData(
        effect_type=FieldEffectType.SHOCK_ZONE,
        name="감전 지대",
        description="폭풍의 봉우리 - 데미지 연쇄 확률 증가",
        emoji="⚡"
    ),
    FieldEffectType.DROWN_TIMER: FieldEffectData(
        effect_type=FieldEffectType.DROWN_TIMER,
        name="익사 타이머",
        description="수몰된 신전 - 3라운드마다 최대 HP의 5% 데미지",
        emoji="🌊"
    ),
    FieldEffectType.CHAOS_RIFT: FieldEffectData(
        effect_type=FieldEffectType.CHAOS_RIFT,
        name="차원 불안정",
        description="혼돈의 균열 - 매 행동마다 20% 확률로 랜덤 상태이상",
        emoji="🌀"
    ),
    FieldEffectType.TIME_WARP: FieldEffectData(
        effect_type=FieldEffectType.TIME_WARP,
        name="시간 왜곡",
        description="시공의 틈새 - 모든 속도가 불안정하게 변동",
        emoji="⏰"
    ),
    FieldEffectType.VOID_EROSION: FieldEffectData(
        effect_type=FieldEffectType.VOID_EROSION,
        name="공허의 잠식",
        description="공허의 심연 - 모든 버프 지속시간 2배 감소",
        emoji="🕳️"
    ),
    FieldEffectType.WATER_PRESSURE: FieldEffectData(
        effect_type=FieldEffectType.WATER_PRESSURE,
        name="수압 효과",
        description="깊은 심해 - 모든 방어력 -10%",
        emoji="💧"
    ),
    FieldEffectType.AWAKENING_AURA: FieldEffectData(
        effect_type=FieldEffectType.AWAKENING_AURA,
        name="각성의 기운",
        description="각성의 제단 - 모든 공격력 +15%",
        emoji="✨"
    ),
    FieldEffectType.ANCIENT_CURSE: FieldEffectData(
        effect_type=FieldEffectType.ANCIENT_CURSE,
        name="고대의 저주",
        description="잊혀진 문명 - 매 행동마다 3% 즉사 확률",
        emoji="💀"
    ),
}


FIELD_EFFECT_CLASSES = {
    FieldEffectType.BURN_ZONE: BurnZoneEffect,
    FieldEffectType.FREEZE_ZONE: FreezeZoneEffect,
    FieldEffectType.SHOCK_ZONE: ShockZoneEffect,
    FieldEffectType.DROWN_TIMER: DrownTimerEffect,
    FieldEffectType.CHAOS_RIFT: ChaosRiftEffect,
    FieldEffectType.TIME_WARP: TimeWarpEffect,
    FieldEffectType.VOID_EROSION: VoidErosionEffect,
    FieldEffectType.WATER_PRESSURE: WaterPressureEffect,
    FieldEffectType.AWAKENING_AURA: AwakeningAuraEffect,
    FieldEffectType.ANCIENT_CURSE: AncientCurseEffect,
}


def create_field_effect(effect_type: FieldEffectType) -> FieldEffect:
    """
    필드 효과 생성

    Args:
        effect_type: 필드 효과 타입

    Returns:
        생성된 필드 효과 인스턴스
    """
    data = FIELD_EFFECT_DATA[effect_type]
    effect_class = FIELD_EFFECT_CLASSES[effect_type]
    return effect_class(data)


def roll_random_field_effect() -> FieldEffect:
    """
    랜덤 필드 효과 생성

    Returns:
        랜덤으로 선택된 필드 효과
    """
    import random

    effect_type = random.choice(list(FieldEffectType))
    return create_field_effect(effect_type)
