import discord
from discord.ext import commands

from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id


# ============================================================
# 던전 카테고리 분류
# ============================================================

DUNGEON_CATEGORIES = [
    {"key": "normal", "label": "일반 던전", "emoji": "🌲", "filter": lambda d: d.id < 10},
    {"key": "elite", "label": "정예 던전", "emoji": "⚔️", "filter": lambda d: 10 <= d.id < 100},
    {"key": "raid", "label": "레이드", "emoji": "🐉", "filter": lambda d: d.id >= 100},
]


def categorize_dungeons(dungeons: list) -> dict[str, list]:
    """던전 목록을 카테고리별로 분류"""
    result = {}
    for cat in DUNGEON_CATEGORIES:
        filtered = [d for d in dungeons if cat["filter"](d)]
        if filtered:
            result[cat["key"]] = filtered
    return result


# ============================================================
# UI 컴포넌트
# ============================================================

class DungeonDropdown(discord.ui.Select):
    def __init__(self, dungeons: list):
        self.dungeons = dungeons
        options = [
            discord.SelectOption(
                label=dungeon.name,
                description=f"Lv.{dungeon.require_level}+",
                value=str(dungeon.id)
            ) for dungeon in dungeons
        ]
        super().__init__(placeholder="던전을 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        selected_id = int(self.values[0])
        view.selected_dungeon = next(d for d in self.dungeons if d.id == selected_id)

        dungeon = view.selected_dungeon
        user_level = view.session.user.level
        level_ok = user_level >= dungeon.require_level

        embed = discord.Embed(
            title=f"{dungeon.name} 던전 선택됨",
            description=dungeon.description,
            color=discord.Color.green() if level_ok else discord.Color.red()
        )

        embed.add_field(name="입장 조건", value=f"최소 레벨: {dungeon.require_level}", inline=False)

        dungeon_spawn_monsters = find_all_dungeon_spawn_monster_by(dungeon.id)
        monsters_name = []
        for spawn in dungeon_spawn_monsters:
            monster = find_monster_by_id(spawn.monster_id)
            if monster:
                monsters_name.append(monster.name)
        view.selected_dungeon_monsters = monsters_name
        monster_list_str = ", ".join(monsters_name) if monsters_name else "없음"
        embed.add_field(name="등장 몬스터", value=monster_list_str, inline=False)

        if not level_ok:
            embed.add_field(
                name="⚠️ 경고",
                value="이 던전은 너에겐 너무 위험하다!\n레벨을 더 올리고 다시 도전해라.",
                inline=False
            )

        for child in view.children:
            if isinstance(child, EnterButton):
                child.disabled = not level_ok

        await interaction.response.edit_message(embed=embed, view=view)


class CategoryButton(discord.ui.Button):
    def __init__(self, key: str, label: str, emoji: str, is_active: bool = False):
        self.category_key = key
        style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary
        super().__init__(label=label, emoji=emoji, style=style, custom_id=f"cat_{key}")

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        view.set_category(self.category_key)

        embed = discord.Embed(
            title="🎯 던전을 선택하세요",
            description="카테고리를 선택한 후 드롭다운에서 던전을 골라주세요.",
            color=discord.Color.blurple()
        )

        cat_info = next(c for c in DUNGEON_CATEGORIES if c["key"] == self.category_key)
        embed.set_footer(text=f"{cat_info['emoji']} {cat_info['label']} 목록")

        await interaction.response.edit_message(embed=embed, view=view)


class EnterButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="입장", style=discord.ButtonStyle.success, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        if not view.selected_dungeon:
            await interaction.response.send_message("던전을 선택해주세요.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass
        view.stop()


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="취소", style=discord.ButtonStyle.danger, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        view.selected_dungeon = None
        await interaction.response.defer()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass
        view.stop()


# ============================================================
# 메인 뷰
# ============================================================

class DungeonSelectView(discord.ui.View):
    def __init__(self, user, dungeons, session, timeout=20):
        super().__init__(timeout=timeout)
        self.user = user
        self.all_dungeons = sorted(
            dungeons,
            key=lambda d: (d.require_level, d.id)
        )
        self.session = session
        self.selected_dungeon = None
        self.message = None

        self.categorized = categorize_dungeons(self.all_dungeons)

        # 첫 번째로 존재하는 카테고리를 기본값으로 설정
        self.current_category = next(
            (cat["key"] for cat in DUNGEON_CATEGORIES if cat["key"] in self.categorized),
            None
        )

        self._rebuild_items()

    def set_category(self, category_key: str):
        """카테고리 변경 및 UI 재구성"""
        self.current_category = category_key
        self.selected_dungeon = None
        self._rebuild_items()

    def _rebuild_items(self):
        """현재 카테고리에 맞게 UI 컴포넌트 재구성"""
        self.clear_items()

        # Row 0: 카테고리 버튼
        for cat in DUNGEON_CATEGORIES:
            if cat["key"] not in self.categorized:
                continue
            count = len(self.categorized[cat["key"]])
            is_active = cat["key"] == self.current_category
            btn = CategoryButton(
                key=cat["key"],
                label=f"{cat['label']} ({count})",
                emoji=cat["emoji"],
                is_active=is_active,
            )
            btn.row = 0
            self.add_item(btn)

        # Row 1: 던전 드롭다운 (현재 카테고리)
        if self.current_category and self.current_category in self.categorized:
            dropdown = DungeonDropdown(self.categorized[self.current_category])
            dropdown.row = 1
            self.add_item(dropdown)

        # Row 3: 입장/취소 버튼
        self.add_item(EnterButton())
        self.add_item(CancelButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def on_timeout(self):
        self.selected_dungeon = None
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
