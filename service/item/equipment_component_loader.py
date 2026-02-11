"""
Equipment Component Loader

장비 컴포넌트를 로드하고 관리합니다. (스킬 시스템과 동일)
"""
from typing import List, Dict, Any
from service.dungeon.components.base import skill_component_register


def load_equipment_components(config: dict) -> List[Any]:
    """
    장비 config에서 컴포넌트 인스턴스 생성 (스킬과 동일한 방식)

    Args:
        config: {"components": [{"tag": "passive_buff", "crit_rate": 5, ...}]}

    Returns:
        컴포넌트 인스턴스 리스트
    """
    if not config or "components" not in config:
        return []

    components = []
    components_config = config["components"]

    for comp_config in components_config:
        tag = comp_config.get("tag")
        if not tag:
            continue

        # skill_component_register에서 컴포넌트 클래스 가져오기
        component_class = skill_component_register.get(tag)
        if not component_class:
            continue

        # 컴포넌트 인스턴스 생성
        component = component_class()

        # apply_config 호출 (스킬과 동일)
        component.apply_config(comp_config, "Equipment", priority=0)

        # tag 저장 (get_passive_stat_bonuses에서 사용)
        component._tag = tag

        components.append(component)

    return components


def get_equipment_passive_stats(components: List[Any]) -> Dict[str, float]:
    """
    장비 컴포넌트에서 패시브 스탯 보너스 추출

    PassiveBuffComponent는 percentage 기반 스탯만 가지므로,
    equipment의 고정값 스탯은 _raw_config에서 직접 추출합니다.

    Args:
        components: 컴포넌트 인스턴스 리스트

    Returns:
        스탯 보너스 딕셔너리
    """
    totals = {
        "attack": 0,
        "ap_attack": 0,
        "ad_defense": 0,
        "ap_defense": 0,
        "speed": 0,
        "crit_rate": 0.0,
        "crit_damage": 0.0,
        "lifesteal": 0.0,
        "drop_rate": 0.0,
        "evasion": 0.0,
        "accuracy": 0.0,
        "block_rate": 0.0,
        "armor_pen": 0.0,
        "magic_pen": 0.0,
        "fire_resist": 0.0,
        "ice_resist": 0.0,
        "lightning_resist": 0.0,
        "water_resist": 0.0,
        "holy_resist": 0.0,
        "dark_resist": 0.0,
        "fire_damage": 0.0,
        "ice_damage": 0.0,
        "lightning_damage": 0.0,
        "water_damage": 0.0,
        "holy_damage": 0.0,
        "dark_damage": 0.0,
        "exp_bonus": 0.0,
        "bonus_hp_pct": 0.0,
        "bonus_speed_pct": 0.0,
        "bonus_all_stats_pct": 0.0,
    }

    for comp in components:
        tag = getattr(comp, '_tag', '')
        if tag != "passive_buff":
            continue

        # _raw_config에서 모든 스탯 추출
        # PassiveBuffComponent는 일부 속성만 처리하지만,
        # equipment는 고정값 스탯도 필요하므로 raw_config 사용
        if hasattr(comp, '_raw_config'):
            raw_config = comp._raw_config
            for key, value in raw_config.items():
                if key in totals:
                    totals[key] += value

    return totals
