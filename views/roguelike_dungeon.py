"""Discord controls for roguelike route and skill-augment choices."""

from __future__ import annotations

import asyncio

import discord

from config import ROGUELIKE
from service.dungeon.roguelike_routes import RouteOffer, foresight_clue, offer_clue
from service.dungeon.skill_augments import AUGMENTS, AugmentDefinition, AugmentId


def create_route_embed(session, offers: list[RouteOffer]) -> discord.Embed:
    from service.dungeon.skill import get_passive_effect_bonuses

    has_foresight = get_passive_effect_bonuses(session.user).get("foresight", 0.0) > 0
    max_hp = session.user.get_stat().get(__import__("models").UserStatEnum.HP, session.user.hp)
    embed = discord.Embed(
        title=f"🗺️ {session.dungeon.name} · {session.exploration_step + 1}/{ROGUELIKE.ROUTE_ROOMS}방",
        description=(
            f"❤️ {session.user.now_hp}/{max_hp} · ⭐ {session.total_exp} EXP · 💰 {session.total_gold} G\n"
            "경로 등급은 기대 보상 수준이며 아이템 확정 등급이 아닙니다."
        ),
        color=discord.Color.blurple(),
    )
    for index, offer in enumerate(offers, start=1):
        risk = "☠" * offer.risk if offer.risk else "안전"
        clue = offer_clue(offer, getattr(session.dungeon, 'require_level', session.user.level))
        if has_foresight:
            clue += f"\n🔮 {foresight_clue(offer)}"
        embed.add_field(
            name=f"{index}. {offer.title}",
            value=(
                f"위험: {risk} · 기대 보상: **{offer.reward_grade}**\n"
                f"{clue}"
            ),
            inline=False,
        )
    return embed


class RouteChoiceView(discord.ui.View):
    def __init__(self, owner_id: int, session, offers: list[RouteOffer]):
        super().__init__(timeout=ROGUELIKE.CHOICE_TIMEOUT_SECONDS)
        self.owner_id = owner_id
        self.session = session
        self.selected: RouteOffer | None = None
        for index, offer in enumerate(offers, start=1):
            self.add_item(RouteButton(index, offer, session))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("이 던전의 탐험자만 선택할 수 있습니다.", ephemeral=True)
        return False


class RouteButton(discord.ui.Button):
    def __init__(self, index: int, offer: RouteOffer, session):
        super().__init__(
            label=f"{index}. {offer.title.split(' ', 1)[-1]}",
            style=discord.ButtonStyle.danger if offer.risk >= 4 else discord.ButtonStyle.primary,
            custom_id=f"rl:{session.run_nonce}:{offer.room}:{offer.token}",
        )
        self.offer = offer

    async def callback(self, interaction: discord.Interaction):
        view: RouteChoiceView = self.view
        async with view.session.route_choice_lock:
            expected_room = view.session.exploration_step + 1
            if self.offer.room != expected_room or view.session.selected_route_token:
                await interaction.response.send_message("이미 처리됐거나 지난 방의 선택입니다.", ephemeral=True)
                return
            view.session.selected_route_token = self.offer.token
            view.selected = self.offer
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(view=view)
            view.stop()


class ResumeView(discord.ui.View):
    def __init__(self, owner_id: int, session):
        super().__init__(timeout=ROGUELIKE.PAUSE_GRACE_SECONDS)
        self.owner_id = owner_id
        self.session = session
        self.resumed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    @discord.ui.button(label="계속하기", style=discord.ButtonStyle.success, custom_id="rl:resume")
    async def resume(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.resumed = True
        await interaction.response.defer()
        self.stop()


async def wait_for_route_choice(session, discord_user, message) -> RouteOffer | None:
    offers = [RouteOffer.from_dict(value) for value in session.route_offers]
    if __import__("os").getenv("E2E_UI_AUTOPILOT") == "TRUE":
        session.selected_route_token = offers[0].token
        return offers[0]

    view = RouteChoiceView(discord_user.id, session, offers)
    await message.edit(embed=create_route_embed(session, offers), view=view)
    view_task = asyncio.create_task(view.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait(
        {view_task, end_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    if end_task in done and session.run_end_event.is_set():
        view.stop()
        return None
    if view.selected:
        return view.selected

    loop = asyncio.get_running_loop()
    session.pause_started_at = loop.time()
    session.pause_deadline = session.pause_started_at + ROGUELIKE.PAUSE_GRACE_SECONDS
    pause_embed = create_route_embed(session, offers)
    pause_embed.title = "⏸️ 탐험 일시정지"
    pause_embed.description = "같은 경로가 5분 동안 보존됩니다. 시간 안에 계속해 주세요."
    resume = ResumeView(discord_user.id, session)
    await message.edit(embed=pause_embed, view=resume)
    resume_task = asyncio.create_task(resume.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait(
        {resume_task, end_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    if end_task in done and session.run_end_event.is_set():
        resume.stop()
        return None
    if not resume.resumed:
        return None
    session.pause_started_at = None
    session.pause_deadline = None
    view = RouteChoiceView(discord_user.id, session, offers)
    await message.edit(embed=create_route_embed(session, offers), view=view)
    view_task = asyncio.create_task(view.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait({view_task, end_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    if session.run_end_event.is_set():
        view.stop()
        return None
    return view.selected


class SkillSelect(discord.ui.Select):
    def __init__(self, skills):
        super().__init__(
            placeholder="개조할 스킬 선택",
            options=[discord.SelectOption(label=skill.name[:100], value=str(skill.id)) for skill in skills],
        )

    async def callback(self, interaction: discord.Interaction):
        view: SkillAugmentView = self.view
        view.selected_skill_id = int(self.values[0])
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class SkillAugmentView(discord.ui.View):
    def __init__(self, owner_id: int, session, skills):
        super().__init__(timeout=ROGUELIKE.CHOICE_TIMEOUT_SECONDS)
        self.owner_id = owner_id
        self.session = session
        self.skills = {skill.id: skill for skill in skills}
        self.selected_skill_id: int | None = None
        self.chosen: tuple[int, str] | None = None
        self.add_item(SkillSelect(skills))
        self.add_item(ShowAugmentsButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def create_embed(self) -> discord.Embed:
        selected = self.skills.get(self.selected_skill_id)
        description = "먼저 현재 덱에서 개조할 액티브 또는 궁극기를 고르세요."
        if selected:
            count = len(self.session.skill_augments.get(selected.id, []))
            description = f"**{selected.name}** · 현재 개조 {count}/2\n확인하면 호환 개조 3개를 제시합니다."
        return discord.Embed(title="🧬 스킬 개조", description=description, color=discord.Color.purple())


class ShowAugmentsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="개조 후보 확인", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: SkillAugmentView = self.view
        if not view.selected_skill_id:
            await interaction.response.send_message("스킬을 먼저 선택하세요.", ephemeral=True)
            return
        from service.dungeon.skill_augments import generate_augment_offers
        from service.skill.ultimate_service import is_ultimate_skill

        skill = view.skills[view.selected_skill_id]
        cache_key = f"{view.session.exploration_step}:{skill.id}"
        cached_ids = view.session.augment_offer_cache.get(cache_key)
        if cached_ids:
            offers = [AUGMENTS[AugmentId(value)] for value in cached_ids]
        else:
            offers = generate_augment_offers(
                skill,
                view.session.skill_augments.get(skill.id, []),
                view.session.run_rng,
                is_ultimate=is_ultimate_skill(skill.id),
            )
            view.session.augment_offer_cache[cache_key] = [item.augment_id.value for item in offers]
        view.clear_items()
        for definition in offers[:3]:
            view.add_item(AugmentButton(skill.id, definition))
        embed = discord.Embed(
            title=f"🧬 {skill.name} 개조",
            description="\n".join(f"**{item.label}** · {item.description}" for item in offers[:3]),
            color=discord.Color.purple(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class AugmentButton(discord.ui.Button):
    def __init__(self, skill_id: int, definition: AugmentDefinition):
        super().__init__(
            label=definition.label,
            style=discord.ButtonStyle.success,
            custom_id=f"rl:augment:{skill_id}:{definition.augment_id.value}",
        )
        self.skill_id = skill_id
        self.definition = definition

    async def callback(self, interaction: discord.Interaction):
        view: SkillAugmentView = self.view
        async with view.session.augment_choice_lock:
            existing = view.session.skill_augments.setdefault(self.skill_id, [])
            if view.chosen or len(existing) >= 2 or self.definition.augment_id.value in existing:
                await interaction.response.send_message("이 개조는 더 적용할 수 없습니다.", ephemeral=True)
                return
            existing.append(self.definition.augment_id.value)
            view.chosen = (self.skill_id, self.definition.augment_id.value)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="✅ 개조 완료",
                    description=f"**{self.definition.label}** · {self.definition.description}",
                    color=discord.Color.green(),
                ),
                view=None,
            )
            view.stop()


async def wait_for_skill_augment(session, discord_user, message, skills) -> bool:
    eligible = [skill for skill in skills if len(session.skill_augments.get(skill.id, [])) < 2]
    if not eligible:
        return True
    if __import__("os").getenv("E2E_UI_AUTOPILOT") == "TRUE":
        from service.dungeon.skill_augments import generate_augment_offers
        from service.skill.ultimate_service import is_ultimate_skill
        skill = eligible[0]
        offers = generate_augment_offers(skill, session.skill_augments.get(skill.id, []), session.run_rng, is_ultimate=is_ultimate_skill(skill.id))
        if offers:
            session.skill_augments.setdefault(skill.id, []).append(offers[0].augment_id.value)
        return True
    view = SkillAugmentView(discord_user.id, session, eligible)
    await message.edit(embed=view.create_embed(), view=view)
    view_task = asyncio.create_task(view.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait({view_task, end_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    if view.chosen is not None:
        return True
    if session.run_end_event.is_set():
        return False

    pause = ResumeView(discord_user.id, session)
    await message.edit(
        embed=discord.Embed(
            title="⏸️ 개조 선택 일시정지",
            description="같은 개조 후보를 5분 동안 보존합니다. 시간 안에 계속해 주세요.",
            color=discord.Color.orange(),
        ),
        view=pause,
    )
    pause_task = asyncio.create_task(pause.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait({pause_task, end_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    if not pause.resumed or session.run_end_event.is_set():
        return False
    resumed = SkillAugmentView(discord_user.id, session, eligible)
    await message.edit(embed=resumed.create_embed(), view=resumed)
    resumed_task = asyncio.create_task(resumed.wait())
    end_task = asyncio.create_task(session.run_end_event.wait())
    done, pending = await asyncio.wait({resumed_task, end_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    if session.run_end_event.is_set():
        resumed.stop()
        return False
    return resumed.chosen is not None
