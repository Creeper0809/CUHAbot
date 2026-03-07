import discord
from discord import app_commands
from discord.ext import commands

from views.collection_view import CollectionView
from views.dungeon_select_view import DungeonSelectView
from views.inventory import InventoryView
from views.skill_deck import SkillDeckView
from views.stat_distribution_view import StatDistributionView
from views.user_info_view import UserInfoView
from bot import GUILD_IDS
from config import DUNGEON, SKILL_ID
from decorator.account import requires_account
from models.repos import find_account_by_discordid
from models.repos.dungeon_repo import find_all_dungeon
from models.repos.static_cache import skill_cache_by_id
from models.user_equipment import UserEquipment
from models.user_inventory import UserInventory
from service.dungeon.dungeon_service import start_dungeon
from service.collection_service import CollectionService, EntryNotFoundError
from service.dungeon.item_service import get_item_info, ItemNotFoundException
from service.player.healing_service import HealingService
from service.item.inventory_service import InventoryService
from service.session import ContentType, is_in_combat, create_session, end_session
from service.skill.skill_deck_service import SkillDeckService
from service.skill.ultimate_service import (
    get_ultimate_mode_for_skill,
    is_ultimate_skill,
    load_ultimate_to_user,
    set_ultimate_skill,
)
from service.item.equipment_service import EquipmentService
from service.skill.skill_ownership_service import SkillOwnershipService
from service.temp_admin_service import is_admin_or_temp
from service.raid.raid_service import init_raid_session_state
from service.raid.raid_progress_service import check_raid_entry, consume_raid_entry
from service.raid.raid_lobby_service import create_raid_lobby, close_raid_lobby, wait_raid_lobby_result
from models.repos.raid_repo import find_raid_by_dungeon_id
from models import User, UserStatEnum
from models.repos.static_cache import monster_cache_by_id
from service.dungeon.combat_context import CombatContext
from service.dungeon.combat_executor import execute_combat_context
from views.raid_lobby_view import create_raid_lobby_embed, RaidLobbyInviteView, RaidLobbyView


class DungeonCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @requires_account()
    @app_commands.command(
        name="던전입장",
        description="던전에 입장합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def enter_dungeon(self, interaction: discord.Interaction):
        # 원자적 세션 생성 (이미 존재하면 None 반환)
        session = await create_session(interaction.user.id)
        if session is None:
            await interaction.response.send_message("이미 던전 탐험중입니다.")
            return

        try:
            user: User = await find_account_by_discordid(session.user_id)
            session.user = user

            # 스킬 덱 로드 (전투에서 사용)
            await SkillDeckService.load_deck_to_user(user)
            await load_ultimate_to_user(user)

            # 장비 스탯 로드 (전투에서 사용)
            await EquipmentService.apply_equipment_stats(user)

            # 자연 회복 적용
            await HealingService.apply_natural_regen(user)

            # HP 체크 - 너무 낮으면 경고
            max_hp = user.get_stat()[UserStatEnum.HP]
            hp_percent = (user.now_hp / max_hp) * 100 if max_hp > 0 else 0
            min_hp_pct = DUNGEON.MIN_HP_PERCENT_TO_ENTER
            if hp_percent < min_hp_pct * 100:
                # 완전 회복까지 예상 시간 계산 (VIT 기반)
                hp_needed = int(max_hp * min_hp_pct) - user.now_hp
                regen_per_min = max(1, int(max_hp * user.get_hp_regen_rate()))
                minutes_needed = (hp_needed + regen_per_min - 1) // regen_per_min

                await interaction.response.send_message(
                    f"⚠️ HP가 너무 낮습니다! ({user.now_hp}/{max_hp}, {hp_percent:.0f}%)\n"
                    f"HP {int(min_hp_pct * 100)}% 이상이 되어야 입장 가능합니다.\n"
                    f"자연 회복으로 약 **{minutes_needed}분** 후 입장 가능합니다.",
                    ephemeral=True
                )
                return

            dungeons = find_all_dungeon()
            if not dungeons:
                await interaction.response.send_message("등록된 던전이 없습니다.")
                return

            embed = discord.Embed(
                title="🎯 던전을 선택하세요",
                description="드롭다운에서 던전을 선택한 후 입장하거나 취소하세요.",
                color=discord.Color.blurple()
            )
            view = DungeonSelectView(interaction.user, dungeons, session)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            await view.wait()

            if view.selected_dungeon is None:
                await interaction.followup.send("던전 입장이 취소되었습니다.")
                return

            # 레벨 체크 (방어 로직)
            if user.level < view.selected_dungeon.require_level:
                await interaction.followup.send(
                    f"⚠️ 레벨이 부족합니다. (현재: {user.level}, 필요: {view.selected_dungeon.require_level})"
                )
                return

            await interaction.followup.send(f"{view.selected_dungeon.name} 던전에 입장합니다!")

            session.dungeon = view.selected_dungeon
            session.content_type = (
                ContentType.RAID
                if view.selected_dungeon.id >= 100
                else ContentType.NORMAL_DUNGEON
            )
            session.allow_intervention = session.content_type != ContentType.RAID
            if session.content_type == ContentType.RAID:
                raid = find_raid_by_dungeon_id(session.dungeon.id)
                if raid:
                    entry_check = await check_raid_entry(user, raid.raid_id)
                    if not entry_check.allowed:
                        await interaction.followup.send(
                            f"⛔ 이번 주 레이드 입장 횟수를 모두 사용했습니다. "
                            f"({entry_check.max_entries}/{entry_check.max_entries})",
                            ephemeral=True,
                        )
                        return

                    voice_channel_id = getattr(getattr(interaction.user, "voice", None), "channel", None)
                    voice_channel_id = voice_channel_id.id if voice_channel_id else None

                    lobby = create_raid_lobby(
                        leader_id=interaction.user.id,
                        raid_id=raid.raid_id,
                        raid_name=raid.raid_name,
                        dungeon_id=raid.dungeon_id,
                        required_level=int(getattr(raid, "recommended_level", 1) or 1),
                        max_party_size=int(getattr(raid, "max_party_size", 3) or 3),
                        voice_channel_id=voice_channel_id,
                        timeout_seconds=60,
                    )

                    try:
                        lobby_embed = create_raid_lobby_embed(lobby)

                        # 리더 로비 UI
                        await interaction.followup.send(
                            "🐉 레이드 로비를 생성했습니다. 아래 UI에서 준비/시작을 진행하세요.",
                            embed=lobby_embed,
                            view=RaidLobbyView(lobby),
                            ephemeral=True,
                        )

                        # 같은 VC 멤버에게 초대 DM 전송
                        invited = 0
                        voice_state = getattr(interaction.user, "voice", None)
                        channel = getattr(voice_state, "channel", None)
                        if channel:
                            for member in channel.members:
                                if member.bot or member.id == interaction.user.id:
                                    continue
                                try:
                                    await member.send(
                                        embed=discord.Embed(
                                            title=f"🐉 레이드 초대 - {raid.raid_name}",
                                            description=(
                                                f"{interaction.user.display_name}님이 레이드 로비를 열었습니다.\n"
                                                f"권장 레벨: Lv.{raid.recommended_level}+\n"
                                                f"파티 정원: {raid.max_party_size}명"
                                            ),
                                            color=discord.Color.red(),
                                        ),
                                        view=RaidLobbyInviteView(lobby),
                                    )
                                    invited += 1
                                except Exception:
                                    continue

                        await interaction.followup.send(
                            f"📨 초대 전송: **{invited}명**\n"
                            "모든 참가자가 준비 완료하면 리더가 시작할 수 있습니다. "
                            "60초 뒤에는 자동 시작됩니다.",
                            ephemeral=True,
                        )

                        lobby_result = await wait_raid_lobby_result(lobby)
                        if lobby_result == "cancelled":
                            await interaction.followup.send("🛑 레이드 로비가 취소되어 입장을 종료합니다.", ephemeral=True)
                            return
                        if lobby_result == "timeout_auto_start":
                            await interaction.followup.send("⏱️ 로비 시간이 종료되어 현재 인원으로 자동 시작합니다.", ephemeral=True)

                        # 리더 입장권 차감 (참가자는 참가 시 이미 차감)
                        remaining, max_entries = await consume_raid_entry(user, raid.raid_id)
                        await interaction.followup.send(
                            f"🎫 리더 주간 레이드 입장권 차감: 남은 횟수 **{remaining}/{max_entries}**",
                            ephemeral=True,
                        )

                        # 로비 참가자(리더 제외) 세션 참가자로 편입
                        party_count = 1
                        for uid in list(lobby.participants.keys()):
                            if uid == interaction.user.id:
                                continue
                            participant = await find_account_by_discordid(uid)
                            if not participant:
                                continue

                            # 전투 준비
                            await SkillDeckService.load_deck_to_user(participant)
                            await load_ultimate_to_user(participant)
                            await EquipmentService.apply_equipment_stats(participant)
                            await HealingService.apply_natural_regen(participant)

                            session.participants[uid] = participant
                            session.contribution[uid] = 0
                            party_count += 1

                        await interaction.followup.send(
                            f"👥 레이드 파티 확정: **{party_count}/{raid.max_party_size}명**",
                            ephemeral=True,
                        )
                    finally:
                        close_raid_lobby(interaction.user.id)

                init_raid_session_state(session)
            await start_dungeon(session, interaction)

        finally:
            # 예외 발생 여부와 관계없이 세션 정리 보장
            await end_session(user_id=interaction.user.id)

    @app_commands.command(
        name="설명",
        description="아이템, 스킬, 몬스터 정보를 검색합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(이름="검색할 이름 (아이템/스킬/몬스터)")
    async def search_entry(self, interaction: discord.Interaction, 이름: str):
        """통합 검색 (아이템/스킬/몬스터)"""
        # 유저 정보 (도감 등록 여부 표시용)
        user = await find_account_by_discordid(interaction.user.id)

        try:
            _, embed = await CollectionService.search_entry(이름, user)
            await interaction.response.send_message(embed=embed)
        except EntryNotFoundError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="도감",
        description="수집한 아이템, 스킬, 몬스터 도감을 확인합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def collection(self, interaction: discord.Interaction):
        """도감 조회"""
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 도감 데이터 로드
        stats = await CollectionService.get_collection_stats(user)
        items = await CollectionService.get_collected_items(user)
        skills = await CollectionService.get_collected_skills(user)
        monsters = await CollectionService.get_collected_monsters(user)

        # View 생성
        view = CollectionView(
            discord_user=interaction.user,
            user=user,
            stats=stats,
            items=items,
            skills=skills,
            monsters=monsters
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="내정보",
        description="내 캐릭터 정보를 확인합니다 (스탯, 장비, 스킬)"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def my_info(self, interaction: discord.Interaction):
        """내 정보 조회"""
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 자연 회복 적용 (HP 정보 표시 전 자동 적용)
        await HealingService.apply_natural_regen(user)

        # 장비 정보 로드
        equipment = await UserEquipment.filter(user=user).prefetch_related(
            "inventory_item__item"
        )
        await EquipmentService.apply_equipment_stats(user)

        # 스킬 덱 로드
        skill_deck = await SkillDeckService.get_deck_as_list(user)

        # 세트 효과 요약 로드
        from service.item.set_detection_service import SetDetectionService
        set_summary = await SetDetectionService.get_set_summary(user)

        # View 생성
        view = UserInfoView(
            discord_user=interaction.user,
            user=user,
            equipment=list(equipment),
            skill_deck=skill_deck,
            set_summary=set_summary
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="덱",
        description="스킬 덱을 확인하고 편집합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def skill_deck(self, interaction: discord.Interaction):
        """스킬 덱 확인 및 편집"""
        # 전투 중 체크
        if is_in_combat(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ 전투 중에는 덱을 변경할 수 없습니다!",
                ephemeral=True
            )
            return

        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 현재 덱 로드
        current_deck = await SkillDeckService.get_deck_as_list(user)

        # 기존 유저 마이그레이션 (스킬 소유 데이터 생성)
        await SkillOwnershipService.migrate_existing_user(user, current_deck)

        # 현재 덱에 있는 스킬을 도감에 자동 등록 (기존 유저 호환)
        for skill_id in set(current_deck):
            if skill_id != 0:
                await CollectionService.register_skill(user, skill_id)

        # 보유 스킬 목록 (소유한 스킬만)
        owned_skills = await SkillOwnershipService.get_all_owned_skills(user)
        available_skills = [
            skill_cache_by_id[owned.skill_id]
            for owned in owned_skills
            if owned.skill_id in skill_cache_by_id
        ]

        # 스킬별 보유 수량 정보
        skill_quantities = {
            owned.skill_id: owned
            for owned in owned_skills
        }

        # 강타는 항상 사용 가능하도록 추가
        BASIC_ATTACK_SKILL_ID = SKILL_ID.BASIC_ATTACK_ID
        if BASIC_ATTACK_SKILL_ID in skill_cache_by_id:
            basic_skill = skill_cache_by_id[BASIC_ATTACK_SKILL_ID]
            if basic_skill not in available_skills:
                available_skills.insert(0, basic_skill)  # 맨 앞에 추가
            # skill_quantities에 없으면 무제한으로 추가
            if BASIC_ATTACK_SKILL_ID not in skill_quantities:
                # 더미 객체 생성 (무제한 수량)
                from models.user_owned_skill import UserOwnedSkill
                dummy_owned = UserOwnedSkill(
                    user=user,
                    skill_id=BASIC_ATTACK_SKILL_ID,
                    quantity=999,  # 무제한으로 간주
                    equipped_count=0
                )
                skill_quantities[BASIC_ATTACK_SKILL_ID] = dummy_owned

        if not available_skills:
            await interaction.response.send_message(
                "⚠️ 보유한 스킬이 없습니다.\n"
                "던전에서 스킬을 획득하거나, 상점에서 스킬을 구매하세요.",
                ephemeral=True
            )
            return

        # View 생성 및 초기화 (프리셋 로드)
        view = SkillDeckView(
            user=interaction.user,
            current_deck=current_deck,
            available_skills=available_skills,
            db_user=user,
            skill_quantities=skill_quantities
        )
        await view.initialize()

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

        # 사용자 응답 대기
        await view.wait()

        # 저장 처리
        if view.saved and view.changes_made:
            # 스킬 소유 수량 검증
            can_change, error_msg = await SkillOwnershipService.can_change_deck(
                user, current_deck, view.current_deck
            )
            if not can_change:
                await interaction.followup.send(
                    f"⚠️ 덱 저장 실패: {error_msg}",
                    ephemeral=True
                )
                return

            # 소유 수량 업데이트
            await SkillOwnershipService.apply_deck_change(
                user, current_deck, view.current_deck
            )

            # 덱 슬롯 저장
            for slot_index, skill_id in enumerate(view.current_deck):
                await SkillDeckService.set_skill(user, slot_index, skill_id)

            # 유저 객체에 덱 로드
            await SkillDeckService.load_deck_to_user(user)

    @requires_account()
    @app_commands.command(
        name="궁극기설정",
        description="궁극기 슬롯을 설정합니다 (수동/자동은 스킬별 고정)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        skill_id="장착할 궁극기 스킬 ID (해제: 0)"
    )
    async def configure_ultimate(
        self,
        interaction: discord.Interaction,
        skill_id: int | None = None,
    ):
        if is_in_combat(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ 전투 중에는 궁극기 설정을 변경할 수 없습니다.",
                ephemeral=True
            )
            return

        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        await load_ultimate_to_user(user)

        updated_fields = []

        if skill_id is not None:
            if skill_id != 0 and not is_ultimate_skill(skill_id):
                await interaction.response.send_message(
                    "⚠️ 궁극기 스킬 ID만 장착할 수 있습니다.",
                    ephemeral=True
                )
                return

            if skill_id != 0:
                owned_skills = await SkillOwnershipService.get_all_owned_skills(user)
                owned_ids = {owned.skill_id for owned in owned_skills}
                if skill_id not in owned_ids:
                    await interaction.response.send_message(
                        "⚠️ 보유하지 않은 궁극기는 장착할 수 없습니다.",
                        ephemeral=True
                    )
                    return

            ok = await set_ultimate_skill(user, skill_id)
            if not ok:
                await interaction.response.send_message(
                    "⚠️ 궁극기 슬롯 저장에 실패했습니다. (테이블 미생성 가능)",
                    ephemeral=True
                )
                return
            updated_fields.append(f"궁극기 슬롯: `{skill_id}`")

        await load_ultimate_to_user(user)
        mode_value = get_ultimate_mode_for_skill(user.equipped_ultimate_skill)
        mode_name = "수동" if mode_value == "manual" else "자동"

        if not updated_fields:
            msg = (
                "현재 궁극기 설정\n"
                f"- 슬롯: `{user.equipped_ultimate_skill}`\n"
                f"- 발동 정책: `{mode_name}` (스킬 고정)"
            )
        else:
            msg = (
                "궁극기 설정이 업데이트되었습니다.\n"
                + "\n".join(f"- {line}" for line in updated_fields)
                + f"\n\n현재 설정\n- 슬롯: `{user.equipped_ultimate_skill}`\n- 발동 정책: `{mode_name}` (스킬 고정)"
            )

        await interaction.response.send_message(msg, ephemeral=True)

    @requires_account()
    @app_commands.command(
        name="치유",
        description="[관리자] 대상의 HP를 완전히 회복합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="회복시킬 대상 (미지정시 자신)")
    async def heal(self, interaction: discord.Interaction, target: discord.Member = None):
        """관리자용 완전 회복"""
        # 관리자 체크 (Discord 관리자 또는 임시 어드민)
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "⚠️ 관리자만 사용할 수 있는 명령어입니다.",
                ephemeral=True
            )
            return

        # 대상 결정
        target_discord_id = target.id if target else interaction.user.id
        target_user: User = await find_account_by_discordid(target_discord_id)

        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        # 완전 회복 적용
        healed = await HealingService.full_heal(target_user)

        target_name = target.display_name if target else interaction.user.display_name

        embed = discord.Embed(
            title="💚 완전 회복",
            description=f"**{target_name}**의 HP가 완전히 회복되었습니다!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="회복량",
            value=f"+{healed} HP",
            inline=True
        )

        embed.add_field(
            name="현재 HP",
            value=f"{target_user.now_hp}/{target_user.hp}",
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @requires_account()
    @app_commands.command(
        name="스탯",
        description="스탯 포인트를 분배합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def stat_distribution(self, interaction: discord.Interaction):
        """스탯 분배"""
        # 전투 중 체크
        if is_in_combat(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ 전투 중에는 스탯을 분배할 수 없습니다!",
                ephemeral=True
            )
            return

        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 자연 회복 적용
        await HealingService.apply_natural_regen(user)

        # 스탯 분배 뷰 (5대 능력치 시스템)
        stat_view = StatDistributionView(
            discord_user=interaction.user,
            db_user=user
        )

        stat_embed = stat_view.create_embed()
        await interaction.response.send_message(embed=stat_embed, view=stat_view, ephemeral=True)
        stat_view.message = await interaction.original_response()

    @requires_account()
    @app_commands.command(
        name="인벤토리",
        description="보유한 아이템을 확인합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    async def inventory(self, interaction: discord.Interaction):
        """인벤토리 조회"""
        user: User = await find_account_by_discordid(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "등록된 계정이 없습니다. `/등록`을 먼저 해주세요.",
                ephemeral=True
            )
            return

        # 인벤토리 로드
        inventory = await InventoryService.get_inventory(user)

        # 스킬 로드
        from service.skill.skill_ownership_service import SkillOwnershipService
        owned_skills = await SkillOwnershipService.get_all_owned_skills(user)

        # View 생성
        view = InventoryView(
            user=interaction.user,
            db_user=user,
            inventory=list(inventory),
            owned_skills=owned_skills
        )

        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="채널정보", description="현재 음성 채널의 레벨, 경험치, MVP, 통계를 확인합니다")
    @requires_account()
    async def channel_info(self, interaction: discord.Interaction):
        """현재 음성 채널의 레벨, 경험치, MVP, 통계"""
        from service.voice_channel.voice_channel_service import voice_channel_service
        from service.voice_channel.channel_level_service import ChannelLevelService

        # Guard: 음성 채널 없음
        vc_id = voice_channel_service.get_user_channel(interaction.user.id)
        if not vc_id:
            await interaction.response.send_message(
                "❌ 음성 채널에 접속해주세요.",
                ephemeral=True
            )
            return

        # 채널 통계 조회
        stats = await ChannelLevelService.get_channel_stats(vc_id)

        if not stats:
            await interaction.response.send_message(
                "📊 아직 이 채널의 기록이 없습니다.",
                ephemeral=True
            )
            return

        # Embed 생성
        embed = discord.Embed(
            title=f"📊 채널 통계",
            description=f"레벨 **{stats.level}** (경험치: {stats.exp:,})",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="오늘의 기록",
            value=(
                f"⚔️ 전투: {stats.total_combats}회\n"
                f"💥 총 데미지: {stats.total_damage:,}"
            ),
            inline=False
        )

        if stats.mvp_user_id:
            try:
                mvp_user = await interaction.client.fetch_user(stats.mvp_user_id)
                embed.add_field(
                    name="🏆 오늘의 MVP",
                    value=f"{mvp_user.name} ({stats.mvp_damage:,} 데미지)",
                    inline=False
                )
            except:
                pass  # MVP 유저 조회 실패 시 무시

        # 채널 레벨 보너스
        bonus_pct = (stats.level - 1) * 5
        embed.add_field(
            name="💎 채널 레벨 보너스",
            value=f"+{bonus_pct}% 보상 (EXP, Gold)",
            inline=False
        )

        embed.set_footer(text=f"날짜: {stats.date}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DungeonCommand(bot))
