from types import SimpleNamespace

from service.skill import synergy_service


def _skill(skill_id: int, keywords: str, components: list[dict] | None = None, extra_config: dict | None = None):
    config = {"components": components or []}
    if extra_config:
        config.update(extra_config)
    return SimpleNamespace(
        id=skill_id,
        skill_model=SimpleNamespace(
            keyword=keywords,
            config=config,
        ),
    )


def test_mastery_excludes_other_attribute_synergies(monkeypatch):
    cache = {
        sid: _skill(sid, "화염/냉기", components=[{"tag": "attack"}])
        for sid in range(1, 11)
    }
    monkeypatch.setattr(synergy_service, "skill_cache_by_id", cache)

    active = synergy_service.SynergyService.get_active_synergies(list(range(1, 11)))
    names = [s.name for s in active]

    assert "화염 ×10" in names
    assert not any(name.startswith("냉기 ×") for name in names)


def test_effect_density_synergy_activates_tier_5(monkeypatch):
    cache = {
        sid: _skill(sid, "화상", components=[{"tag": "status", "type": "burn"}])
        for sid in range(1, 6)
    }
    monkeypatch.setattr(synergy_service, "skill_cache_by_id", cache)

    active = synergy_service.SynergyService.get_active_synergies([1, 2, 3, 4, 5])
    names = [s.name for s in active]
    assert "화상 ×5" in names


def test_new_combo_synergies_activation(monkeypatch):
    cache = {
        1: _skill(1, "셋업", components=[{"tag": "heal"}]),
        2: _skill(2, "셋업", components=[{"tag": "heal"}]),
        3: _skill(3, "셋업", components=[{"tag": "heal"}]),
        7: _skill(7, "셋업", components=[{"tag": "heal"}]),
        4: _skill(4, "피니셔/화상", components=[{"tag": "attack"}]),
        5: _skill(5, "피니셔/중독", components=[{"tag": "attack"}]),
        6: _skill(6, "피니셔/마비", components=[{"tag": "attack"}]),
        5001: _skill(5001, "피니셔", components=[{"tag": "attack"}], extra_config={"ultimate": {"mode": "manual"}}),
        5002: _skill(5002, "피니셔", components=[{"tag": "attack"}], extra_config={"ultimate": {"mode": "manual"}}),
    }
    monkeypatch.setattr(synergy_service, "skill_cache_by_id", cache)

    deck = [1, 2, 3, 7, 4, 5, 6, 5001, 5002]
    active = synergy_service.SynergyService.get_active_synergies(deck)
    names = [s.name for s in active]

    assert "서바이버" in names
    assert "상태이상 마스터" in names
    assert "셋업-피니셔 특화" in names
    assert "궁극기 특화" in names


def test_damage_taken_multiplier_applies_defensive_combos(monkeypatch):
    cache = {
        sid: _skill(sid, "셋업", components=[{"tag": "heal"}])
        for sid in range(1, 8)
    }
    monkeypatch.setattr(synergy_service, "skill_cache_by_id", cache)

    mult = synergy_service.SynergyService.calculate_damage_taken_multiplier([1, 2, 3, 4, 5, 6, 7])
    assert mult < 1.0


def test_ultimate_specialization_only_boosts_ultimate(monkeypatch):
    cache = {
        1: _skill(1, "피니셔", components=[{"tag": "attack"}]),
        5001: _skill(5001, "피니셔", components=[{"tag": "attack"}], extra_config={"ultimate": {"mode": "manual"}}),
        5002: _skill(5002, "피니셔", components=[{"tag": "attack"}], extra_config={"ultimate": {"mode": "manual"}}),
    }
    monkeypatch.setattr(synergy_service, "skill_cache_by_id", cache)

    deck = [1, 5001, 5002]
    normal_mult = synergy_service.SynergyService.calculate_damage_multiplier(
        deck,
        attribute="무속성",
        current_skill=cache[1],
    )
    ultimate_mult = synergy_service.SynergyService.calculate_damage_multiplier(
        deck,
        attribute="무속성",
        current_skill=cache[5001],
    )
    assert ultimate_mult > normal_mult
