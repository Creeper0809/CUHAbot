import discord
from discord.ext import commands

from models.repos.dungeon_repo import find_all_dungeon_spawn_monster_by
from models.repos.monster_repo import find_monster_by_id
from models.repos.static_cache import monster_cache_by_id


class DungeonDropdown(discord.ui.Select):
    def __init__(self, dungeons):
        self.dungeons = dungeons
        options = [
            discord.SelectOption(
                label=dungeon.name,
                description=f"레벨 제한: {dungeon.require_level}",
                value=str(dungeon.id)
            ) for dungeon in dungeons
        ]
        super().__init__(placeholder="던전을 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_id = int(self.values[0])
        self.view.selected_dungeon = next(d for d in self.dungeons if d.id == selected_id)

        dungeon = self.view.selected_dungeon
        user_level = self.view.session.user.level
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
        self.view.selected_dungeon_monsters = monsters_name
        monster_list_str = ", ".join(monsters_name) if monsters_name else "없음"
        embed.add_field(name="등장 몬스터", value=monster_list_str, inline=False)

        if not level_ok:
            embed.add_field(
                name="⚠️ 경고",
                value="이 던전은 너에겐 너무 위험하다! 🔥\n레벨을 더 올리고 다시 도전해라.",
                inline=False
            )

        for child in self.view.children:
            if isinstance(child, EnterButton):
                child.disabled = not level_ok

        await interaction.response.edit_message(embed=embed, view=self.view)


class EnterButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="입장", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        if not view.selected_dungeon:
            await interaction.response.send_message("던전을 선택해주세요.", ephemeral=True)
            return
        # 먼저 응답 후 메시지 수정
        await interaction.response.defer()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass
        view.stop()


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="취소", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: DungeonSelectView = self.view
        view.selected_dungeon = None
        # 먼저 응답 후 메시지 수정
        await interaction.response.defer()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass
        view.stop()


class DungeonSelectView(discord.ui.View):
    def __init__(self, user, dungeons,session, timeout=20):
        super().__init__(timeout=timeout)
        self.user = user
        self.dungeons = sorted(
            dungeons,
            key=lambda dungeon: (dungeon.require_level, dungeon.id)
        )
        self.session = session
        self.selected_dungeon = None
        self.message = None
        self.add_item(DungeonDropdown(self.dungeons))
        self.add_item(EnterButton())
        self.add_item(CancelButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def on_timeout(self):
        self.selected_dungeon = None  # 타임아웃 시 항상 리셋
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass

