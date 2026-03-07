"""
궁극기 서비스 테스트
"""
from types import SimpleNamespace

import pytest

from models import UserStatEnum
from service.dungeon.status.dot_effects import BurnEffect
from service.skill import ultimate_service


class DummyUser:
    def __init__(self, mode="manual", ultimate_id=5004):
        self.ultimate_mode = mode
        self.equipped_ultimate_skill = ultimate_id
        self.ultimate_gauge = 100
        self.ultimate_cooldown_remaining = 0
        self.manual_ultimate_requested = False
        self.now_hp = 100
        self.hp = 200
        self._next_skill = SimpleNamespace(id=1001, name="강타")

    def next_skill(self):
        return self._next_skill

    def get_stat(self):
        return {UserStatEnum.HP: self.hp}


class TestUltimateService:
    @staticmethod
    def _ultimate_skill(skill_id: int, attribute: str, keyword: str, mode: str, cooldown: int):
        return SimpleNamespace(
            id=skill_id,
            attribute=attribute,
            skill_model=SimpleNamespace(
                keyword=keyword,
                config={"ultimate": {"mode": mode, "cooldown": cooldown}},
            ),
        )

    def test_manual_ultimate_cast_consumes_gauge(self, monkeypatch):
        user = DummyUser(mode="manual", ultimate_id=5002)
        user.manual_ultimate_requested = True
        monsters = [SimpleNamespace(now_hp=100, hp=100, status=[])]

        ultimate_skill = self._ultimate_skill(
            skill_id=5002,
            attribute="무속성",
            keyword="물리/피니셔",
            mode="manual",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)

        skill, log, scale = ultimate_service.select_skill_for_user_turn(user, monsters)
        assert skill.id == 5002
        assert "수동 궁극기" in log
        assert scale == 1.0
        assert user.ultimate_gauge == 0
        assert user.ultimate_cooldown_remaining > 0

        # 게이지가 0이면 일반 스킬
        skill2, log2, scale2 = ultimate_service.select_skill_for_user_turn(user, monsters)
        assert skill2.id == 1001
        assert log2 is None
        assert scale2 == 1.0

    def test_auto_ultimate_trigger_on_burn_condition(self, monkeypatch):
        user = DummyUser(mode="auto", ultimate_id=5004)
        user.ultimate_gauge = 0

        burn = BurnEffect()
        burn.stacks = 5
        burn.duration = 3
        monster = SimpleNamespace(now_hp=100, hp=200, status=[burn])

        ultimate_skill = self._ultimate_skill(
            skill_id=5004,
            attribute="화염",
            keyword="화염/피니셔",
            mode="auto",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)

        skill, log, scale = ultimate_service.select_skill_for_user_turn(user, [monster])
        assert skill.id == 5004
        assert "자동 궁극기" in log
        assert scale == pytest.approx(0.8)
        assert user.ultimate_gauge == 0

    def test_auto_ultimate_fallback_to_normal_skill_when_condition_not_met(self, monkeypatch):
        user = DummyUser(mode="auto", ultimate_id=5004)
        user.ultimate_gauge = 0
        monster = SimpleNamespace(now_hp=200, hp=200, status=[])

        ultimate_skill = self._ultimate_skill(
            skill_id=5004,
            attribute="화염",
            keyword="화염/피니셔",
            mode="auto",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)

        skill, log, scale = ultimate_service.select_skill_for_user_turn(user, [monster])
        assert skill.id == 1001
        assert log is None
        assert scale == 1.0

    def test_cooldown_blocks_cast_even_with_full_gauge(self, monkeypatch):
        user = DummyUser(mode="manual", ultimate_id=5002)
        user.manual_ultimate_requested = True
        user.ultimate_gauge = 100
        user.ultimate_cooldown_remaining = 2
        monsters = [SimpleNamespace(now_hp=100, hp=100, status=[])]
        ultimate_skill = self._ultimate_skill(
            skill_id=5002,
            attribute="무속성",
            keyword="물리/피니셔",
            mode="manual",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)

        skill, log, scale = ultimate_service.select_skill_for_user_turn(user, monsters)
        assert skill.id == 1001
        assert log is None
        assert scale == 1.0

    def test_skill_specific_cooldown_value(self, monkeypatch):
        skill_by_id = {
            5002: self._ultimate_skill(5002, "무속성", "피니셔", "manual", 4),
            5005: self._ultimate_skill(5005, "무속성", "피니셔", "manual", 6),
        }
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda sid: skill_by_id.get(sid))
        assert ultimate_service.get_ultimate_cooldown(5002) != ultimate_service.get_ultimate_cooldown(5005)
        assert ultimate_service.get_ultimate_cooldown(5002) > 0

    def test_tick_cooldown(self):
        user = DummyUser(mode="manual", ultimate_id=5002)
        user.ultimate_cooldown_remaining = 3
        ultimate_service.tick_ultimate_cooldown(user)
        assert user.ultimate_cooldown_remaining == 2
        ultimate_service.tick_ultimate_cooldown(user)
        ultimate_service.tick_ultimate_cooldown(user)
        assert user.ultimate_cooldown_remaining == 0

    def test_insufficient_gauge_blocks_cast(self, monkeypatch):
        user = DummyUser(mode="manual", ultimate_id=5002)
        user.ultimate_gauge = 40
        user.manual_ultimate_requested = True
        monsters = [SimpleNamespace(now_hp=100, hp=100, status=[])]
        ultimate_skill = self._ultimate_skill(
            skill_id=5002,
            attribute="무속성",
            keyword="물리/피니셔",
            mode="manual",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)

        skill, log, scale = ultimate_service.select_skill_for_user_turn(user, monsters)
        assert skill.id == 1001
        assert log is None
        assert scale == 1.0

    def test_gauge_charge_by_damage_and_action(self):
        user = DummyUser(mode="manual", ultimate_id=5002)
        user.ultimate_gauge = 0

        ultimate_service.add_ultimate_gauge(user, dealt_damage=200, taken_damage=100, acted=True)
        assert user.ultimate_gauge > 0

    def test_auto_mode_does_not_gain_gauge(self, monkeypatch):
        user = DummyUser(mode="auto", ultimate_id=5004)
        user.ultimate_gauge = 0
        ultimate_skill = self._ultimate_skill(
            skill_id=5004,
            attribute="화염",
            keyword="화염/피니셔",
            mode="auto",
            cooldown=4,
        )
        monkeypatch.setattr(ultimate_service, "get_skill_by_id", lambda _sid: ultimate_skill)
        ultimate_service.add_ultimate_gauge(user, dealt_damage=500, taken_damage=500, acted=True)
        assert user.ultimate_gauge == 0
