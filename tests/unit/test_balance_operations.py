from types import SimpleNamespace

from config import BALANCE_V2, RouteKind
from scripts.reset_balance_v2_season import DELETE_TABLES, DIRECT_TABLES, RELATED_TABLES
from service.dungeon.roguelike_routes import RouteOffer, npc_offer_details, offer_clue
from service.telemetry import summarize_balance_events


def test_live_balance_telemetry_aggregation_covers_player_funnels():
    rows = [
        {
            "event_type": "dungeon_run_finished", "level": 50, "content_type": "roguelike",
            "metrics": {"cleared": True, "result": "clear", "gold": 1000, "room": 9, "augments": 3},
        },
        {
            "event_type": "dungeon_run_finished", "level": 50, "content_type": "roguelike",
            "metrics": {"cleared": False, "result": "death", "gold": 300, "room": 6, "augments": 2},
        },
        {"event_type": "roguelike_route_selected", "level": 50, "metrics": {"kind": "elite"}},
        {"event_type": "shop_purchase", "level": 50, "metrics": {"cost": 500}},
        {"event_type": "enhancement", "level": 50, "metrics": {"cost": 280}},
        {"event_type": "equipment_replaced", "level": 50, "metrics": {}},
        {"event_type": "box_opened", "level": 50, "metrics": {"grades": [4, 6]}},
    ]
    report = summarize_balance_events(rows, days=7)
    assert report["clear_by_level_band"]["41-50"]["clear_rate"] == 0.5
    assert report["gold_earned"] == 1300
    assert report["gold_spent"] == 780
    assert report["gold_spend_ratio"] == 0.6
    assert report["route_choices"] == {"elite": 1}
    assert report["death_rooms"] == {"6": 1}
    assert report["augment_counts"] == {"3": 1, "2": 1}
    assert report["box_grades"] == {"4": 1, "6": 1}
    assert report["equipment_replacements"] == 1


def test_npc_offer_shows_the_exact_level_scaled_transaction():
    healer = RouteOffer(
        token="one", kind=RouteKind.NPC, room=3, risk=1, reward_grade="C",
        title="healer", clue="hidden", payload={"npc_type": "healer", "resolution_seed": 1},
    )
    price, effect = npc_offer_details(healer, 70)
    assert price == round(BALANCE_V2.dungeon_gold(70) * 0.12 / 10) * 10
    assert "30%" in effect
    clue = offer_clue(healer, 70)
    assert f"{price:,}" in clue and effect in clue


def test_season_reset_covers_real_table_names_and_discord_voice_identity():
    assert "user_deck_presets" in DIRECT_TABLES
    assert "skill_equip" in DIRECT_TABLES
    assert "user_deck_presets" in DELETE_TABLES
    assert "skill_equip" in DELETE_TABLES
    assert RELATED_TABLES["voice_channel_level"] == ("mvp_user_id=$1", "discord_id")
    assert "user_deck_preset" not in DIRECT_TABLES
