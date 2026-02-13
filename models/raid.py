from tortoise import fields, models


class Raid(models.Model):
    raid_id = fields.IntField(pk=True)
    dungeon_id = fields.IntField(index=True)
    raid_key = fields.CharField(max_length=100, unique=True)
    raid_name = fields.CharField(max_length=255)
    recommended_level = fields.IntField(default=1)
    max_party_size = fields.IntField(default=3)
    boss_code = fields.CharField(max_length=100)
    boss_name = fields.CharField(max_length=255)
    main_attribute = fields.CharField(max_length=50, default="all")
    phase_count = fields.IntField(default=3)
    phase_hp_triggers = fields.CharField(max_length=50, default="70|35")
    enrage_turn_limit = fields.IntField(default=20)
    default_priority_1 = fields.CharField(max_length=50, default="body")
    default_priority_2 = fields.CharField(max_length=50, default="body")
    default_priority_3 = fields.CharField(max_length=50, default="body")
    notes = fields.TextField(default="")

    class Meta:
        table = "raid"


class RaidTargetingRule(models.Model):
    raid_id = fields.IntField(pk=True)
    dropbox_enabled = fields.BooleanField(default=True)
    apply_delay_turns = fields.IntField(default=1)
    team_priority_slots = fields.IntField(default=3)
    personal_override_enabled = fields.BooleanField(default=True)
    personal_override_slots = fields.IntField(default=1)
    persist_selection = fields.BooleanField(default=True)
    single_target_rule = fields.CharField(max_length=100, default="selected_priority_first")
    aoe_target_rule = fields.CharField(max_length=100, default="body_plus_active_parts")
    destroyed_part_fallback = fields.CharField(max_length=100, default="next_valid_priority")
    notes = fields.TextField(default="")

    class Meta:
        table = "raid_targeting_rule"


class RaidSpecialAction(models.Model):
    action_key = fields.CharField(max_length=50, pk=True)
    action_name = fields.CharField(max_length=100)
    cooldown_rounds = fields.IntField(default=0)
    max_uses_per_round = fields.IntField(default=1)
    target_type = fields.CharField(max_length=50)
    effect_type = fields.CharField(max_length=100)
    base_value = fields.IntField(default=0)
    scaling_stat = fields.CharField(max_length=50, default="none")
    description = fields.TextField(default="")

    class Meta:
        table = "raid_special_action"


class RaidMinigame(models.Model):
    minigame_id = fields.IntField(pk=True)
    raid_id = fields.IntField(index=True)
    minigame_key = fields.CharField(max_length=100)
    minigame_name = fields.CharField(max_length=100)
    minigame_type = fields.CharField(max_length=50)
    time_limit_sec = fields.IntField(default=20)
    input_count = fields.IntField(default=3)
    success_effect = fields.CharField(max_length=150)
    fail_effect = fields.CharField(max_length=150)

    class Meta:
        table = "raid_minigame"


class RaidPhaseTransition(models.Model):
    transition_id = fields.IntField(pk=True)
    raid_id = fields.IntField(index=True)
    from_phase = fields.IntField()
    to_phase = fields.IntField()
    trigger_type = fields.CharField(max_length=50)
    trigger_value = fields.CharField(max_length=50)
    minigame_id = fields.IntField(index=True)
    success_buff_key = fields.CharField(max_length=100)
    fail_penalty_key = fields.CharField(max_length=100)

    class Meta:
        table = "raid_phase_transition"


class RaidPart(models.Model):
    part_id = fields.IntField(pk=True)
    raid_id = fields.IntField(index=True)
    part_key = fields.CharField(max_length=50)
    part_name = fields.CharField(max_length=100)
    max_hp_ratio = fields.FloatField(default=0.2)
    defense_multiplier = fields.FloatField(default=1.0)
    targetable_from_turn = fields.IntField(default=1)
    destructible = fields.BooleanField(default=True)
    on_destroy_effect = fields.CharField(max_length=100, default="none")
    on_destroy_value = fields.FloatField(default=0.0)
    disabled_boss_skill_keys = fields.CharField(max_length=200, null=True)
    skill_lock_duration_turns = fields.IntField(default=-1)
    priority_hint = fields.CharField(max_length=30, default="mid")

    class Meta:
        table = "raid_part"


class RaidGimmick(models.Model):
    gimmick_id = fields.IntField(pk=True)
    raid_id = fields.IntField(index=True)
    phase = fields.IntField()
    gimmick_key = fields.CharField(max_length=100)
    gimmick_name = fields.CharField(max_length=100)
    trigger_type = fields.CharField(max_length=50)
    trigger_value = fields.CharField(max_length=100)
    duration_turns = fields.IntField(default=0)
    target_scope = fields.CharField(max_length=50)
    success_condition_type = fields.CharField(max_length=100)
    success_condition_value = fields.CharField(max_length=255)
    success_effect = fields.CharField(max_length=150)
    fail_effect = fields.CharField(max_length=150)
    cooldown_turns = fields.IntField(default=0)

    class Meta:
        table = "raid_gimmick"


class RaidBossSkill(models.Model):
    id = fields.IntField(pk=True)
    raid_id = fields.IntField(index=True)
    skill_key = fields.CharField(max_length=100)
    skill_name = fields.CharField(max_length=100)
    skill_id = fields.IntField(null=True)
    phase = fields.IntField(default=1)
    removable_by_part = fields.BooleanField(default=False)
    remove_source_part_key = fields.CharField(max_length=50, null=True)
    notes = fields.TextField(default="")

    class Meta:
        table = "raid_boss_skill"
        unique_together = (("raid_id", "skill_key"),)
