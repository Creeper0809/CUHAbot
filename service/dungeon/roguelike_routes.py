"""Deterministic route offer generation for normal roguelike dungeons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import random
import secrets

from config import ROGUELIKE, RouteKind
from config import BALANCE_V2


ROUTE_META = {
    RouteKind.COMBAT: ("⚔️ 일반 전투", "정면에서 적의 기척이 느껴진다.", "B"),
    RouteKind.ELITE: ("👹 정예 전투", "강한 적이 값진 전리품을 지키고 있다.", "A"),
    RouteKind.TREASURE: ("🎁 보물", "잠긴 상자에서 희미한 빛이 새어 나온다.", "B"),
    RouteKind.EVENT: ("🔮 사건", "결과를 알 수 없는 마력이 일렁인다.", "C"),
    RouteKind.HAZARD: ("⚠️ 위험 통로", "빠른 길이지만 함정 흔적이 선명하다.", "A"),
    RouteKind.REST: ("🏕️ 휴식", "잠시 숨을 고를 수 있는 안전한 공간이다.", "D"),
    RouteKind.SECRET: ("🚪 비밀방", "벽 너머에서 희귀한 기운이 감지된다.", "S"),
    RouteKind.NPC: ("🧙 NPC", "누군가가 거래를 기다리고 있다.", "C"),
}


@dataclass(frozen=True)
class RouteOffer:
    token: str
    kind: RouteKind
    room: int
    risk: int
    reward_grade: str
    title: str
    clue: str
    payload: dict

    def to_dict(self) -> dict:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RouteOffer":
        return cls(**{**data, "kind": RouteKind(data["kind"])})


def room_weights(room: int) -> tuple[tuple[RouteKind, int], ...]:
    if room <= 2:
        return ROGUELIKE.EARLY_WEIGHTS
    if room <= 5:
        return ROGUELIKE.MID_WEIGHTS
    return ROGUELIKE.LATE_WEIGHTS


def room_stat_scale(room: int) -> float:
    index = min(max(room, 1), ROGUELIKE.ROUTE_ROOMS) - 1
    return ROGUELIKE.ROOM_STAT_SCALES[index]


def _risk(kind: RouteKind, room: int, rng: random.Random) -> int:
    if kind == RouteKind.COMBAT:
        return 2 if room <= 2 else 3 if room <= 5 else 4
    if kind == RouteKind.ELITE:
        return 4 if room <= 5 else 5
    if kind == RouteKind.HAZARD:
        return 3 if room <= 5 else 4
    if kind == RouteKind.EVENT:
        return rng.randint(1, 4)
    if kind == RouteKind.NPC:
        return rng.randint(1, 3)
    return {RouteKind.REST: 0, RouteKind.TREASURE: 1, RouteKind.SECRET: 2}[kind]


def _payload(kind: RouteKind, room: int, rng: random.Random) -> dict:
    payload = {"resolution_seed": rng.getrandbits(63)}
    if kind == RouteKind.TREASURE:
        payload["chest_grade"] = rng.choices(
            ["normal", "silver", "gold"], weights=[85, 14, 1], k=1
        )[0]
    elif kind == RouteKind.SECRET:
        payload["box_id"] = rng.choices([5941, 5942, 5943], weights=[70, 25, 5], k=1)[0]
    elif kind == RouteKind.HAZARD:
        payload["triggered"] = rng.random() < ROGUELIKE.HAZARD_TRIGGER_CHANCE
        payload["damage_rate"] = rng.uniform(
            ROGUELIKE.HAZARD_DAMAGE_MIN, ROGUELIKE.HAZARD_DAMAGE_MAX
        )
    elif kind == RouteKind.EVENT:
        payload["event_type"] = rng.choice(("heal", "attack_boost", "lucky", "damage", "gold_loss"))
    elif kind == RouteKind.NPC:
        payload["npc_type"] = rng.choice(("merchant", "healer", "sage"))
    return payload


def npc_offer_details(offer: RouteOffer, level: int) -> tuple[int, str]:
    """Return the exact price/effect shown before an NPC route is selected."""
    npc_type = offer.payload.get("npc_type")
    if npc_type == "healer":
        cost = max(10, round(BALANCE_V2.dungeon_gold(level) * .12 / 10) * 10)
        return cost, "최대 HP의 30% 회복"
    if npc_type == "sage":
        cost = max(10, round(BALANCE_V2.dungeon_gold(level) * .10 / 10) * 10)
        exp = max(1, round(BALANCE_V2.dungeon_exp(level) * .08))
        return cost, f"EXP +{exp:,}"
    cost = max(10, round(BALANCE_V2.dungeon_gold(level) * .20 / 10) * 10)
    return cost, "혼합 상자(하급) 1개"


def offer_clue(offer: RouteOffer, level: int) -> str:
    if offer.kind != RouteKind.NPC:
        return offer.clue
    cost, effect = npc_offer_details(offer, level)
    return f"비용 {cost:,} G · {effect} (선택 즉시 거래)"


def foresight_clue(offer: RouteOffer) -> str:
    """예지 패시브가 노출할 수 있는 이미 확정된 결과만 표시한다."""
    if offer.kind == RouteKind.HAZARD:
        if not offer.payload.get("triggered"):
            return "예지: 함정을 피해 보상만 얻습니다."
        damage = float(offer.payload.get("damage_rate", 0.0))
        return f"예지: 함정이 발동해 최대 HP의 {damage:.0%} 피해를 입습니다."
    if offer.kind == RouteKind.EVENT:
        labels = {
            "heal": "HP 회복", "attack_boost": "공격 강화", "lucky": "행운 보상",
            "damage": "HP 손실", "gold_loss": "골드 손실",
        }
        return f"예지: {labels.get(offer.payload.get('event_type'), '예측할 수 없는 사건')}이 발생합니다."
    if offer.kind == RouteKind.TREASURE:
        labels = {"normal": "하급", "silver": "중급", "gold": "상급"}
        return f"예지: {labels.get(offer.payload.get('chest_grade'), '미지의')} 상자입니다."
    if offer.kind == RouteKind.SECRET:
        labels = {5941: "중급", 5942: "상급", 5943: "최상급"}
        return f"예지: {labels.get(offer.payload.get('box_id'), '미지의')} 상자입니다."
    return "예지: 현재 경로의 종류 외 추가 변수는 없습니다."


def make_offer(kind: RouteKind, room: int, rng: random.Random) -> RouteOffer:
    title, clue, reward_grade = ROUTE_META[kind]
    return RouteOffer(
        token=secrets.token_urlsafe(6),
        kind=kind,
        room=room,
        risk=_risk(kind, room, rng),
        reward_grade=reward_grade,
        title=title,
        clue=clue,
        payload=_payload(kind, room, rng),
    )


def generate_route_offers(
    room: int,
    rng: random.Random,
    *,
    force_treasure: bool = False,
    secret_find_bonus: float = 0.0,
) -> list[RouteOffer]:
    weighted = room_weights(room)
    kinds = [kind for kind, _ in weighted]
    weights = [
        weight * (1.0 + max(0.0, secret_find_bonus)) if kind == RouteKind.SECRET else weight
        for kind, weight in weighted
    ]
    offers: list[RouteOffer] = []
    signatures: set[tuple] = set()

    if force_treasure:
        offer = make_offer(RouteKind.TREASURE, room, rng)
        offers.append(offer)
        signatures.add((
            offer.kind, offer.risk, offer.reward_grade,
            tuple(sorted((key, str(value)) for key, value in offer.payload.items())),
        ))

    while len(offers) < 3:
        offer = make_offer(rng.choices(kinds, weights=weights, k=1)[0], room, rng)
        signature = (
            offer.kind, offer.risk, offer.reward_grade,
            tuple(sorted((key, str(value)) for key, value in offer.payload.items())),
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        offers.append(offer)
    return offers
