"""
Bag 조작 컴포넌트

스킬 덱/가방 시스템에 특화된 컴포넌트들입니다.
- SkillRefreshComponent: 스킬 사용 후 재장전
- SkillRerollComponent: 스킬 리롤
- DoubleDrawComponent: 스킬 2개 중 선택
"""
import random
from service.dungeon.components.base import SkillComponent, register_skill_with_tag


@register_skill_with_tag("skill_refresh")
class SkillRefreshComponent(SkillComponent):
    """
    스킬 재장전 컴포넌트

    스킬 사용 후 일정 확률로 가방에 다시 넣음

    Config:
        refresh_chance: 재장전 확률 (0.0 ~ 1.0)
        specific_skill_ids: 특정 스킬 ID만 재장전 (빈 리스트면 전체)
    """

    def __init__(self):
        super().__init__()
        self.refresh_chance = 0.0
        self.specific_skill_ids = []

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.refresh_chance = config.get("refresh_chance", 0.0)
        self.specific_skill_ids = config.get("specific_skill_ids", [])

    def on_skill_used(self, user, skill_id: int) -> str:
        """
        스킬 사용 직후 호출 (장비 전용)

        Args:
            user: 스킬 사용자
            skill_id: 사용한 스킬 ID

        Returns:
            로그 메시지
        """
        # 특정 스킬만 재장전하는 경우
        if self.specific_skill_ids and skill_id not in self.specific_skill_ids:
            return ""

        # 확률 체크
        if random.random() < self.refresh_chance:
            # 스킬을 다시 가방에 넣음
            if hasattr(user, 'skill_queue'):
                user.skill_queue.insert(0, skill_id)  # 맨 앞에 넣어서 다음에 나올 확률 높임
                return f"   🔄 스킬 재장전! 「{skill_id}」 다시 사용 가능"

        return ""


@register_skill_with_tag("skill_reroll")
class SkillRerollComponent(SkillComponent):
    """
    스킬 리롤 컴포넌트

    턴당 N회 스킬을 다시 뽑을 수 있음

    Config:
        rerolls_per_turn: 턴당 리롤 횟수
        skip_skill_types: 리롤 시 제외할 스킬 타입 (예: ["heal"])
    """

    def __init__(self):
        super().__init__()
        self.rerolls_per_turn = 1
        self.skip_skill_types = []
        self._rerolls_used_this_turn = 0

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.rerolls_per_turn = config.get("rerolls_per_turn", 1)
        self.skip_skill_types = config.get("skip_skill_types", [])

    def on_turn_start(self, user, target) -> str:
        """턴 시작 시 리롤 카운터 리셋"""
        self._rerolls_used_this_turn = 0
        if self.rerolls_per_turn > 0:
            return f"   🎲 리롤 가능: {self.rerolls_per_turn}회"
        return ""

    def try_reroll(self, user):
        """
        리롤 시도 (외부에서 호출)

        Args:
            user: 유저

        Returns:
            (새 스킬, 메시지) 튜플
        """
        if self._rerolls_used_this_turn >= self.rerolls_per_turn:
            return None, "⚠️ 리롤 횟수를 모두 사용했습니다"

        # 현재 스킬을 다시 가방에 넣고 새로운 스킬 뽑기
        new_skill = user.next_skill()
        self._rerolls_used_this_turn += 1

        remaining = self.rerolls_per_turn - self._rerolls_used_this_turn
        return new_skill, f"🎲 스킬 리롤! (남은 횟수: {remaining})"


@register_skill_with_tag("double_draw")
class DoubleDrawComponent(SkillComponent):
    """
    스킬 2개 뽑기 컴포넌트

    스킬을 2개 뽑아서 선택

    Config:
        proc_chance: 발동 확률 (1.0 = 100% 항상)
        auto_select_better: 자동으로 더 강한 스킬 선택 (False면 랜덤)
    """

    def __init__(self):
        super().__init__()
        self.proc_chance = 1.0
        self.auto_select_better = False

    def apply_config(self, config: dict, skill_name: str = ""):
        """설정 적용"""
        self.proc_chance = config.get("proc_chance", 1.0)
        self.auto_select_better = config.get("auto_select_better", False)

    def on_draw_skill(self, user):
        """
        스킬 뽑을 때 호출 (장비 전용)

        Args:
            user: 유저

        Returns:
            (선택된 스킬, 로그 메시지) 튜플
        """
        if random.random() > self.proc_chance:
            return None, ""

        # 2개 뽑기
        skill1 = user.next_skill()
        skill2 = user.next_skill()

        if not skill1 or not skill2:
            # 스킬이 부족하면 하나만 반환
            return skill1 or skill2, ""

        if self.auto_select_better:
            # 공격 스킬 우선, 없으면 첫 번째
            if hasattr(skill1, 'components'):
                for comp in skill1.components:
                    if getattr(comp, '_tag', '') == 'attack':
                        return skill1, f"🎴 2장 중 공격 스킬 선택! 「{skill1.name}」"

            if hasattr(skill2, 'components'):
                for comp in skill2.components:
                    if getattr(comp, '_tag', '') == 'attack':
                        return skill2, f"🎴 2장 중 공격 스킬 선택! 「{skill2.name}」"

            # 둘 다 공격 스킬이 아니면 첫 번째
            return skill1, f"🎴 2장 중 선택! 「{skill1.name}」"
        else:
            # 랜덤 선택
            chosen = random.choice([skill1, skill2])
            return chosen, f"🎴 2장 중 1장 선택! 「{chosen.name}」"
