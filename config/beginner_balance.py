"""Entry-area calibration against naked, unallocated real starter accounts.

These are static monster definitions, not player damage caps or test-only buffs.
Room multipliers still apply to their combat copies. Upper areas are untouched.
"""

REVISION = "beginner-2026-09-v2"
# id: HP, AD, AP, defense. Forest reference Lv1 HP300/AD15; cave Lv5 HP372/AD23.
MONSTER_STATS = {
    1: (13, 8, 8, 3),      # slime: 9001 is AP-based; keep its unique action meaningful but novice-safe
    2: (17, 9, 0, 3),      # goblin: two strikes summed as one action
    3: (17, 9, 0, 3),      # wolf: bleed is part of its damage budget
    8: (15, 0, 10, 3),     # mushroom: poison lasts across rooms
    7: (35, 12, 0, 4),     # king slime: split included in kill-action validation
    122: (88, 27, 38, 5),  # forest king: direct attacks calibrated, not averaged with heals
    6: (27, 15, 0, 5),     # bat: both damage components count toward one action
    4: (30, 12, 0, 5),     # archer: three-hit total
    5: (55, 15, 0, 6),     # shaman: curse must not turn fallback AD into 15,528
    101: (150, 20, 0, 7),  # chief: rage/critical worst case stays below 12% of Lv5 HP
    # Bridge Lv11--20: actual prior-area D +0 nine-slot fixture (see runner).
    # Keep phase multipliers, status skills and summons; no upper-region edits.
    13: (105, 0, 28, 15),
    10: (105, 0, 28, 15),
    12: (105, 0, 28, 15),
    14: (115, 0, 35, 15),
    16: (115, 35, 0, 15),
    15: (115, 35, 0, 15),
    11: (170, 28, 40, 20),  # magma slam 9012 needs a real physical channel
    17: (180, 0, 50, 20),
    102: (310, 0, 48, 25),
    103: (210, 0, 50, 25),
    21: (150, 0, 40, 18),
    25: (150, 40, 0, 18),
    18: (150, 0, 40, 18),
    20: (150, 0, 40, 18),
    22: (150, 0, 40, 18),
    19: (150, 0, 40, 18),
    23: (150, 0, 40, 18),
    24: (150, 40, 0, 18),
    42: (240, 45, 45, 24),
    43: (240, 45, 45, 24),
    104: (420, 45, 45, 28),
    105: (270, 45, 45, 28),
}

# Foreign endgame instant-death fields are not valid novice-area encounters.
# Keep the existing 30% field roll for region-appropriate bridge hazards.
AREA_FIELDS = {1: (), 2: (), 3: ("burn_zone",), 4: ("freeze_zone",),
               5: ("shock_zone",), 6: ("drown_timer",)}

AREA_TARGETS = {1: {"entry_level": 1, "random": .99, "elite": .95},
                2: {"entry_level": 5, "random": .97, "elite": .95}}
