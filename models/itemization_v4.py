"""Persistent Farming and Buildcraft V4 state."""
from tortoise import fields, models


class EquipmentAffixDefinition(models.Model):
    id = fields.CharField(max_length=48, pk=True)
    name = fields.CharField(max_length=64)
    family = fields.CharField(max_length=32)
    effect_group = fields.CharField(max_length=48)
    allowed_slots = fields.JSONField(default=list)
    setup_tags = fields.JSONField(default=list)
    payoff_tags = fields.JSONField(default=list)
    runtime_key = fields.CharField(max_length=48)
    tier_values = fields.JSONField(default=dict)
    weight = fields.FloatField(default=1.0)

    class Meta:
        table = "equipment_affix_definition"


class UserEquipmentAffix(models.Model):
    id = fields.BigIntField(pk=True)
    inventory_item = fields.ForeignKeyField(
        "models.UserInventory", related_name="affixes", on_delete=fields.CASCADE,
    )
    affix_definition = fields.ForeignKeyField(
        "models.EquipmentAffixDefinition", related_name="instances", on_delete=fields.RESTRICT,
    )
    position = fields.IntField()
    tier = fields.IntField()
    value = fields.FloatField()
    quality_percentile = fields.IntField(default=0)

    class Meta:
        table = "user_equipment_affix"
        unique_together = (("inventory_item", "position"),)


class EquipmentProvenance(models.Model):
    id = fields.BigIntField(pk=True)
    inventory_item = fields.OneToOneField(
        "models.UserInventory", related_name="provenance", on_delete=fields.CASCADE,
    )
    source_type = fields.CharField(max_length=24, default="legacy")
    source_key = fields.CharField(max_length=128, default="")
    original_owner_id = fields.IntField(null=True)
    crafted = fields.BooleanField(default=False)
    reforge_count = fields.IntField(default=0)
    acquired_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "equipment_provenance"


class UserCraftingWallet(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.OneToOneField(
        "models.User", related_name="crafting_wallet", on_delete=fields.CASCADE,
    )
    equipment_essence = fields.IntField(default=0)
    source_seals = fields.JSONField(default=dict)
    preservation_catalysts = fields.IntField(default=0)
    recovery_cores = fields.JSONField(default=dict)
    equipment_storage = fields.IntField(default=300)

    class Meta:
        table = "user_crafting_wallet"


class UserFarmProgress(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="farm_progress", on_delete=fields.CASCADE,
    )
    source_type = fields.CharField(max_length=16)
    source_key = fields.CharField(max_length=128)
    progress = fields.IntField(default=0)
    seals_earned = fields.IntField(default=0)
    target_item_id = fields.IntField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_farm_progress"
        unique_together = (("user", "source_type", "source_key"),)


class UserBuildPreset(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="build_presets", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=24)
    note = fields.CharField(max_length=160, default="")
    content_key = fields.CharField(max_length=64, default="")
    bonus_str = fields.IntField(default=0)
    bonus_int = fields.IntField(default=0)
    bonus_dex = fields.IntField(default=0)
    bonus_vit = fields.IntField(default=0)
    bonus_luk = fields.IntField(default=0)
    skill_ids = fields.JSONField(default=list)
    last_measurement = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_build_preset"
        unique_together = (("user", "name"),)


class UserBuildPresetItem(models.Model):
    id = fields.BigIntField(pk=True)
    preset = fields.ForeignKeyField(
        "models.UserBuildPreset", related_name="items", on_delete=fields.CASCADE,
    )
    slot = fields.IntField()
    inventory_item = fields.ForeignKeyField(
        "models.UserInventory", related_name="build_preset_refs",
        null=True, on_delete=fields.SET_NULL,
    )

    class Meta:
        table = "user_build_preset_item"
        unique_together = (("preset", "slot"),)


class UserLootRule(models.Model):
    id = fields.BigIntField(pk=True)
    user = fields.OneToOneField(
        "models.User", related_name="loot_rule", on_delete=fields.CASCADE,
    )
    enabled = fields.BooleanField(default=False)
    max_grade = fields.IntField(default=0)
    slots = fields.JSONField(default=list)
    excluded_item_ids = fields.JSONField(default=list)
    minimum_affix_tier = fields.IntField(null=True)

    class Meta:
        table = "user_loot_rule"


class EquipmentActionReceipt(models.Model):
    id = fields.BigIntField(pk=True)
    interaction_id = fields.CharField(max_length=80, unique=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="equipment_action_receipts", on_delete=fields.CASCADE,
    )
    action = fields.CharField(max_length=24)
    inventory_item_id = fields.BigIntField(null=True)
    result = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "equipment_action_receipt"
