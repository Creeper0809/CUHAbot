"""Structured normal-dungeon monster phase transitions."""
from __future__ import annotations

from copy import deepcopy


def process_monster_phase_transitions(monster, context) -> list[str]:
    logs: list[str] = []
    if getattr(monster, "_phase_invulnerable", False):
        living_summons = [
            value for value in context.monsters
            if getattr(value, "_phase_parent", None) is monster and value.now_hp > 0
        ]
        if not living_summons:
            monster._phase_invulnerable = False
            logs.append(f"🔓 **{monster.get_name()}**의 분신 보호가 해제되었습니다.")

    config = getattr(monster, "phase_config", None) or {}
    phases = config.get("phases", [])
    index = int(getattr(monster, "phase_index", 0) or 0)
    if index >= len(phases) or monster.now_hp <= 0:
        return logs
    hp_ratio = monster.now_hp / max(1, monster.hp)
    while index < len(phases) and hp_ratio <= float(phases[index]["hp_threshold"]):
        phase = phases[index]
        monster.attack = max(1, round(monster.attack * (1 + float(phase.get("attack_pct", 0)))))
        monster.ap_attack = max(0, round(monster.ap_attack * (1 + float(phase.get("attack_pct", 0)))))
        monster.defense = max(0, round(monster.defense * (1 + float(phase.get("defense_pct", 0)))))
        monster.ap_defense = max(0, round(monster.ap_defense * (1 + float(phase.get("defense_pct", 0)))))
        monster.speed = max(1, round(monster.speed * (1 + float(phase.get("speed_pct", 0)))))
        heal = min(monster.hp - monster.now_hp, round(monster.hp * float(phase.get("heal_pct", 0))))
        monster.now_hp += max(0, heal)
        shield = round(monster.hp * float(phase.get("shield_pct", 0)))
        if shield > 0:
            from service.dungeon.status.stat_buffs import ShieldBuff

            shield_buff = ShieldBuff()
            shield_buff.shield_hp = shield
            shield_buff.duration = 999
            monster.status.append(shield_buff)
        summons = []
        for _ in range(min(2, int(phase.get("summon_count", 0) or 0))):
            echo = monster.copy()
            echo.name = f"{monster.name}의 분신"
            echo.hp = max(1, round(monster.hp * .30))
            echo.now_hp = echo.hp
            echo.attack = max(1, round(monster.attack * .50))
            echo.ap_attack = max(0, round(monster.ap_attack * .50))
            echo.phase_config = {}
            echo.phase_index = 0
            echo.is_phase_summon = True
            echo._phase_parent = monster
            context.monsters.append(echo)
            context.action_gauges[id(echo)] = 0
            summons.append(echo.name)
        if summons and phase.get("invulnerable_until_summons"):
            monster._phase_invulnerable = True
        index += 1
        monster.phase_index = index
        details = [f"공격/속도 강화"]
        if heal:
            details.append(f"HP +{heal}")
        if shield:
            details.append(f"보호막 +{shield}")
        if summons:
            details.append(f"{len(summons)}체 소환")
        if getattr(monster, "_phase_invulnerable", False):
            details.append("분신 처치 전 본체 무적")
        logs.append(f"🌗 **{monster.get_name()}** 페이즈 {index} 전환 · " + " · ".join(details))
    return logs
