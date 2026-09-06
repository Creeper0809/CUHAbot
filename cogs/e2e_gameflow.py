import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

from models import User
from models.repos import find_account_by_discordid
from models.repos import static_cache
from service.collection_service import CollectionService, EntryNotFoundError
from service.temp_admin_service import is_temp_admin, add_temp_admin
from models.user_collection import CollectionType
from models.repos import collection_repo
from service.item.inventory_service import InventoryService
from service.item.equipment_service import EquipmentService
from service.player.healing_service import HealingService
from service.skill.skill_deck_service import SkillDeckService
from service.skill.ultimate_service import load_ultimate_to_user
from service.minigame.minigame_manager import MinigameManager
from service.economy.reward_service import RewardService
from service.auction.auction_service import AuctionService
from models.auction_listing import AuctionType
from config.multiplayer import AUCTION
from resources.item_emoji import ItemType
from service.mail import MailService
from models.mail import MailType
from models import Item, Skill_Model
from service.dungeon.encounter_processor import _spawn_monster_group
from service.tower.tower_service import get_floor_monster
from service.tower.tower_reward_service import calculate_floor_reward
from service.raid.raid_minigame_service import get_minigame_choice_payloads
from service.session import DungeonSession
from models.repos.static_cache import raid_minigames_by_raid_id


logger = logging.getLogger(__name__)


def _e2e_enabled() -> bool:
    return os.getenv("E2E_ENABLED") == "TRUE"


class E2EGameFlow(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    class _DummyResponse:
        def __init__(self, ctx: commands.Context):
            self._ctx = ctx
            self._last_message = None
            self._last_modal = None

        async def send_message(self, content=None, **kwargs):
            kwargs.pop("ephemeral", None)
            kwargs.pop("wait", None)
            kwargs.pop("thinking", None)
            self._last_message = await self._ctx.send(content=content, **kwargs)
            return self._last_message

        async def defer(self, **kwargs):
            return None

        async def edit_message(self, **kwargs):
            if self._last_message:
                try:
                    await self._last_message.edit(**kwargs)
                except Exception:
                    pass

        async def send_modal(self, modal):
            self._last_modal = modal
            return None

    class _DummyFollowup:
        def __init__(self, ctx: commands.Context, response: "E2EGameFlow._DummyResponse"):
            self._ctx = ctx
            self._response = response

        async def send(self, content=None, **kwargs):
            kwargs.pop("ephemeral", None)
            kwargs.pop("wait", None)
            kwargs.pop("thinking", None)
            message = await self._ctx.send(content=content, **kwargs)
            self._response._last_message = message
            return message

    class _FakeInteraction:
        def __init__(self, ctx: commands.Context, message: discord.Message | None = None):
            self.user = ctx.author
            self.guild = ctx.guild
            self.guild_id = ctx.guild.id if ctx.guild else None
            self.channel = ctx.channel
            self.channel_id = ctx.channel.id if ctx.channel else None
            self.client = ctx.bot
            self.response = E2EGameFlow._DummyResponse(ctx)
            if message is not None:
                self.response._last_message = message
            self.followup = E2EGameFlow._DummyFollowup(ctx, self.response)

        async def original_response(self):
            return self.response._last_message

    def _make_interaction(self, ctx: commands.Context, message: discord.Message | None = None):
        return E2EGameFlow._FakeInteraction(ctx, message=message)

    async def _run_e2e(self, ctx: commands.Context):
        await ctx.send("[E2E] 게임 플로우 테스트 시작...")

        results = []
        errors = []

        # Optional: force temp admin for MCP-driven tests
        if os.getenv("E2E_FORCE_TEMP_ADMIN") == "TRUE":
            add_temp_admin(ctx.author.id)
            results.append("임시 어드민 강제 설정 (E2E_FORCE_TEMP_ADMIN)")

        # 1) 계정 보장
        user = await find_account_by_discordid(ctx.author.id)
        if user is None:
            user = User(discord_id=ctx.author.id, username=ctx.author.display_name)
            await user.save()
            results.append("계정 자동 생성")
        else:
            results.append("계정 확인")

        # 2) 기본 로드/회복
        try:
            await HealingService.apply_natural_regen(user)
            results.append("자연 회복 적용")
        except Exception as e:
            errors.append(f"자연 회복 실패: {e}")

        try:
            await EquipmentService.apply_equipment_stats(user)
            results.append("장비 스탯 적용")
        except Exception as e:
            errors.append(f"장비 스탯 적용 실패: {e}")

        # 3) 스킬 덱 로드
        try:
            await SkillDeckService.load_deck_to_user(user)
            deck_list = await SkillDeckService.get_deck_as_list(user)
            results.append(f"스킬 덱 로드 (슬롯 {len(deck_list)})")
        except Exception as e:
            errors.append(f"스킬 덱 로드 실패: {e}")

        try:
            await load_ultimate_to_user(user)
            results.append("궁극기 로드")
        except Exception as e:
            errors.append(f"궁극기 로드 실패: {e}")

        # 4) 인벤토리
        try:
            inventory = await InventoryService.get_inventory(user)
            results.append(f"인벤토리 조회 (아이템 {len(list(inventory))})")
        except Exception as e:
            errors.append(f"인벤토리 조회 실패: {e}")

        # 5) 도감 통계
        try:
            stats = await CollectionService.get_collection_stats(user)
            results.append(
                f"도감 통계 조회 (아이템 {stats.item_collected}/{stats.item_total}, "
                f"스킬 {stats.skill_collected}/{stats.skill_total}, "
                f"몬스터 {stats.monster_collected}/{stats.monster_total})"
            )
        except Exception as e:
            errors.append(f"도감 통계 조회 실패: {e}")

        # 6) 검색 (아이템/스킬/몬스터 중 하나 선택)
        try:
            name_candidate = None
            collection_type = None
            target_id = None

            if static_cache.item_cache:
                item = next(iter(static_cache.item_cache.values()))
                name_candidate = item.name
                collection_type = CollectionType.ITEM
                target_id = item.id
            else:
                for skill in static_cache.skill_cache_by_id.values():
                    if getattr(skill.skill_model, "player_obtainable", True):
                        name_candidate = skill.name
                        collection_type = CollectionType.SKILL
                        target_id = skill.id
                        break
                if not name_candidate and static_cache.monster_cache_by_id:
                    monster = next(iter(static_cache.monster_cache_by_id.values()))
                    name_candidate = monster.name
                    collection_type = CollectionType.MONSTER
                    target_id = monster.id

            if name_candidate and collection_type is not None and target_id is not None:
                # 도감 미등록이면 임시 어드민일 때만 등록
                if not await collection_repo.has_collection(user, collection_type, target_id):
                    if is_temp_admin(ctx.author.id):
                        await collection_repo.add_collection(user, collection_type, target_id)
                        results.append("도감 항목 임시 등록 (테스트용)")
                    else:
                        results.append("도감 검색 스킵 (미등록 + 임시 어드민 아님)")
                        name_candidate = None

            if name_candidate:
                _, embed = await CollectionService.search_entry(name_candidate, user)
                await ctx.send(f"[E2E] 도감 검색 테스트: `{name_candidate}`", embed=embed)
                results.append("도감 검색 성공")
            else:
                if not any("도감 검색 스킵" in r for r in results):
                    results.append("도감 검색 스킵 (캐시 비어있음)")
        except EntryNotFoundError as e:
            errors.append(f"도감 검색 실패: {e}")
        except Exception as e:
            errors.append(f"도감 검색 예외: {e}")

        # 요약 출력
        if errors:
            await ctx.send(
                "[E2E] 완료 (일부 실패)\n"
                + "- 성공\n"
                + "\n".join(f"  - {r}" for r in results)
                + "\n- 실패\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        else:
            await ctx.send(
                "[E2E] 완료 (성공)\n"
                + "- 성공\n"
                + "\n".join(f"  - {r}" for r in results)
            )

    async def _run_minigame_smoke(self, results: list, errors: list):
        try:
            games = MinigameManager.list_minigames()
            results.append(f"미니게임 목록 조회 ({len(games)}개)")
            if games:
                info = MinigameManager.get_minigame_info(games[0])
                if info:
                    results.append(f"미니게임 정보 조회 ({games[0]})")
                else:
                    errors.append(f"미니게임 정보 조회 실패: {games[0]}")
        except Exception as e:
            errors.append(f"미니게임 스모크 실패: {e}")

    async def _run_auction_smoke(self, user: User, results: list, errors: list):
        try:
            # Cleanup any existing active listings for this user
            try:
                existing = await AuctionService.get_my_listings(user)
                for listing in existing:
                    await AuctionService.cancel_listing(user, listing.id)
                if existing:
                    results.append(f"기존 경매 {len(existing)}건 정리")
            except Exception as e:
                errors.append(f"기존 경매 정리 실패: {e}")

            starting_price = AUCTION.MIN_LISTING_PRICE
            listing_fee = int(starting_price * AUCTION.LISTING_FEE_PERCENT)
            if user.gold < listing_fee:
                await RewardService.apply_rewards(user, exp_gained=0, gold_gained=listing_fee - user.gold + 1)
                results.append("경매 테스트용 골드 지급")

            item_candidate = None
            for item in static_cache.item_cache.values():
                if getattr(item, "type", None) != ItemType.EQUIP:
                    item_candidate = item
                    break
            if not item_candidate:
                item_candidate = next(iter(static_cache.item_cache.values()), None)

            if not item_candidate:
                errors.append("경매 스모크 실패: 아이템 캐시 비어있음")
                return

            inv_item = await InventoryService.add_item(user, item_candidate.id, quantity=1)
            results.append(f"경매용 아이템 지급 ({item_candidate.name})")

            listing = await AuctionService.create_listing(
                user=user,
                inventory_id=inv_item.id,
                auction_type=AuctionType.BID,
                starting_price=starting_price,
                buyout_price=None,
                duration_hours=1,
            )
            results.append(f"경매 등록 성공 (listing_id={listing.id})")

            await AuctionService.cancel_listing(user, listing.id)
            results.append(f"경매 취소 성공 (listing_id={listing.id})")

            await InventoryService.remove_item(user, item_candidate.id, quantity=1)
            results.append("경매 테스트 아이템 회수")
        except Exception as e:
            errors.append(f"경매 스모크 실패: {e}")

    async def _run_dungeon_spawn_smoke(self, results: list, errors: list):
        try:
            dungeon = next(iter(static_cache.dungeon_cache.values()), None)
            if not dungeon:
                errors.append("던전 스폰 스모크 실패: 던전 캐시 비어있음")
                return
            monsters = _spawn_monster_group(dungeon.id, progress=0.0)
            if not monsters:
                errors.append("던전 스폰 스모크 실패: 몬스터 그룹 없음")
                return
            results.append(f"던전 스폰 스모크 성공 ({dungeon.name}, {len(monsters)}마리)")
        except Exception as e:
            errors.append(f"던전 스폰 스모크 실패: {e}")

    async def _run_tower_smoke(self, results: list, errors: list):
        try:
            monster = await get_floor_monster(1)
            results.append(f"타워 몬스터 조회 성공 ({monster.name})")
            reward = calculate_floor_reward(1, is_boss=False)
            results.append(f"타워 보상 계산 성공 (exp={reward.exp}, gold={reward.gold}, coins={reward.tower_coins})")
        except Exception as e:
            errors.append(f"타워 스모크 실패: {e}")

    async def _run_raid_minigame_smoke(self, user: User, results: list, errors: list):
        try:
            if not raid_minigames_by_raid_id:
                results.append("레이드 미니게임 스모크 스킵 (레이드 캐시 비어있음)")
                return
            raid_id, minigames = next(iter(raid_minigames_by_raid_id.items()))
            if not minigames:
                results.append("레이드 미니게임 스모크 스킵 (미니게임 없음)")
                return
            mg = minigames[0]
            session = DungeonSession(user_id=user.discord_id, user=user)
            session.raid_id = raid_id
            session.raid_pending_minigame_id = int(mg.minigame_id)
            options, prompt = get_minigame_choice_payloads(session, round_number=1)
            results.append(f"레이드 미니게임 선택지 생성 성공 ({mg.minigame_name}, 옵션 {len(options)})")
            if not prompt:
                results.append("레이드 미니게임 프롬프트 비어있음 (비정상은 아님)")
        except Exception as e:
            errors.append(f"레이드 미니게임 스모크 실패: {e}")

    async def _run_user_commands_ui(self, ctx: commands.Context, user: User, results: list, errors: list):
        user_cog = self.bot.get_cog("UserCommand")
        if not user_cog:
            errors.append("UserCommand 코그 없음")
            return

        # 우편: 테스트용 우편 1건 생성
        try:
            test_mail = await MailService.send_mail(
                user_id=user.id,
                mail_type=MailType.SYSTEM,
                sender="E2E",
                title="E2E 테스트 우편",
                content="E2E 우편 테스트입니다.",
                reward_config={"exp": 5, "gold": 3},
                expire_days=1,
            )
            await user_cog.mail_list.callback(user_cog, self._make_interaction(ctx))
            await user_cog.mail_read.callback(user_cog, self._make_interaction(ctx), test_mail.id)
            await user_cog.mail_claim_all.callback(user_cog, self._make_interaction(ctx))
            results.append("우편 UI 테스트 완료")
        except Exception as e:
            errors.append(f"우편 UI 테스트 실패: {e}")

        # 업적
        try:
            await user_cog.achievement_list.callback(user_cog, self._make_interaction(ctx))
            await user_cog.achievement_list.callback(user_cog, self._make_interaction(ctx), "combat")
            results.append("업적 UI 테스트 완료")
        except Exception as e:
            errors.append(f"업적 UI 테스트 실패: {e}")

        # 랭킹
        try:
            await user_cog.ranking.callback(user_cog, self._make_interaction(ctx))
            results.append("랭킹 UI 테스트 완료")
        except Exception as e:
            errors.append(f"랭킹 UI 테스트 실패: {e}")

    async def _run_help_ui(self, ctx: commands.Context, results: list, errors: list):
        help_cog = self.bot.get_cog("HelpCommand")
        if not help_cog:
            errors.append("HelpCommand 코그 없음")
            return

        try:
            await help_cog.help_command.callback(help_cog, self._make_interaction(ctx))
            await help_cog.game_guide.callback(help_cog, self._make_interaction(ctx))
            results.append("도움말 UI 테스트 완료")
        except Exception as e:
            errors.append(f"도움말 UI 테스트 실패: {e}")

    async def _run_server_manage_ui(self, ctx: commands.Context, results: list, errors: list):
        manage_cog = self.bot.get_cog("ServerManageCommand")
        if not manage_cog:
            errors.append("ServerManageCommand 코그 없음")
            return

        try:
            await manage_cog.roll_dice.callback(manage_cog, self._make_interaction(ctx))
            await manage_cog.rsp.callback(manage_cog, self._make_interaction(ctx), "가위")
            results.append("유저 유틸 (dice/rsp) 테스트 완료")
        except Exception as e:
            errors.append(f"유저 유틸 테스트 실패: {e}")

    async def _run_minigame_ui(self, ctx: commands.Context, results: list, errors: list):
        minigame_cog = self.bot.get_cog("MinigameCommand")
        if not minigame_cog:
            errors.append("MinigameCommand 코그 없음")
            return

        try:
            await minigame_cog.list_minigames.callback(minigame_cog, self._make_interaction(ctx))
            results.append("미니게임 목록 UI 테스트 완료")
        except Exception as e:
            errors.append(f"미니게임 목록 UI 테스트 실패: {e}")

        for game_id in ("timing", "sequence", "reaction", "rps", "typing", "math", "memory"):
            try:
                choice = app_commands.Choice(name=game_id, value=game_id)
                await minigame_cog.test_minigame.callback(
                    minigame_cog,
                    self._make_interaction(ctx),
                    choice,
                    1,
                )
                results.append(f"미니게임 실행 테스트 완료 ({game_id})")
            except Exception as e:
                errors.append(f"미니게임 실행 실패 ({game_id}): {e}")

    async def _run_dungeon_command_ui(self, ctx: commands.Context, user: User, results: list, errors: list):
        dungeon_cog = self.bot.get_cog("DungeonCommand")
        if not dungeon_cog:
            errors.append("DungeonCommand 코그 없음")
            return

        # 검색용 이름 준비
        name_candidate = None
        if static_cache.item_cache:
            name_candidate = next(iter(static_cache.item_cache.values())).name
        elif static_cache.skill_cache_by_id:
            name_candidate = next(iter(static_cache.skill_cache_by_id.values())).name
        elif static_cache.monster_cache_by_id:
            name_candidate = next(iter(static_cache.monster_cache_by_id.values())).name

        try:
            if name_candidate:
                await dungeon_cog.search_entry.callback(
                    dungeon_cog, self._make_interaction(ctx), name_candidate
                )
                results.append("설명(검색) UI 테스트 완료")
            else:
                results.append("설명(검색) UI 테스트 스킵 (캐시 비어있음)")
        except Exception as e:
            errors.append(f"설명(검색) UI 테스트 실패: {e}")

        try:
            await dungeon_cog.collection.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("도감 UI 테스트 완료")
        except Exception as e:
            errors.append(f"도감 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.my_info.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("내정보 UI 테스트 완료")
        except Exception as e:
            errors.append(f"내정보 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.inventory.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("인벤토리 UI 테스트 완료")
        except Exception as e:
            errors.append(f"인벤토리 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.stat_distribution.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("스탯 UI 테스트 완료")
        except Exception as e:
            errors.append(f"스탯 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.skill_deck.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("스킬 덱 UI 테스트 완료")
        except Exception as e:
            errors.append(f"스킬 덱 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.configure_ultimate.callback(
                dungeon_cog, self._make_interaction(ctx), 0
            )
            results.append("궁극기 설정 UI 테스트 완료")
        except Exception as e:
            errors.append(f"궁극기 설정 UI 테스트 실패: {e}")

        try:
            await dungeon_cog.channel_info.callback(dungeon_cog, self._make_interaction(ctx))
            results.append("채널정보 UI 테스트 완료")
        except Exception as e:
            errors.append(f"채널정보 UI 테스트 실패: {e}")

    async def _run_auction_ui(self, ctx: commands.Context, results: list, errors: list):
        auction_cog = self.bot.get_cog("AuctionCommand")
        if not auction_cog:
            errors.append("AuctionCommand 코그 없음")
            return

        try:
            await auction_cog.auction.callback(auction_cog, self._make_interaction(ctx))
            results.append("경매 UI 테스트 완료")
        except Exception as e:
            errors.append(f"경매 UI 테스트 실패: {e}")

    async def _run_admin_smoke(self, ctx: commands.Context, user: User, results: list, errors: list):
        admin_cog = self.bot.get_cog("ServerAdminCammand")
        if not admin_cog:
            errors.append("ServerAdminCammand 코그 없음")
            return

        # 임시 어드민 보장
        add_temp_admin(ctx.author.id)

        try:
            await admin_cog.list_temp_admins_cmd.callback(admin_cog, self._make_interaction(ctx))
            results.append("임시 어드민 목록 테스트 완료")
        except Exception as e:
            errors.append(f"임시 어드민 목록 실패: {e}")

        try:
            await admin_cog.re_cache.callback(admin_cog, self._make_interaction(ctx))
            results.append("데베 재캐시 테스트 완료")
        except Exception as e:
            errors.append(f"데베 재캐시 실패: {e}")

        try:
            item = await Item.first()
            if item:
                await admin_cog.give_item.callback(
                    admin_cog, self._make_interaction(ctx), item.id, 1, 0, None, None
                )
                results.append(f"아이템 지급 테스트 완료 ({item.id})")
            else:
                results.append("아이템 지급 스킵 (아이템 없음)")
        except Exception as e:
            errors.append(f"아이템 지급 실패: {e}")

        try:
            skill = await Skill_Model.first()
            if skill:
                await admin_cog.give_skill.callback(
                    admin_cog, self._make_interaction(ctx), skill.id, 1, None
                )
                results.append(f"스킬 지급 테스트 완료 ({skill.id})")
            else:
                results.append("스킬 지급 스킵 (스킬 없음)")
        except Exception as e:
            errors.append(f"스킬 지급 실패: {e}")

        try:
            await admin_cog.give_exp.callback(admin_cog, self._make_interaction(ctx), 1, None)
            results.append("경험치 지급 테스트 완료")
        except Exception as e:
            errors.append(f"경험치 지급 실패: {e}")

        try:
            await admin_cog.unlock_all_collection.callback(admin_cog, self._make_interaction(ctx), None)
            results.append("도감 전체 해금 테스트 완료")
        except Exception as e:
            errors.append(f"도감 전체 해금 실패: {e}")

        try:
            monster = next(iter(static_cache.monster_cache_by_id.values()), None)
            if monster:
                await admin_cog.debug_combat.callback(
                    admin_cog, self._make_interaction(ctx), monster.id, None, "none"
                )
                results.append(f"전투 디버그 테스트 완료 ({monster.id})")
            else:
                results.append("전투 디버그 스킵 (몬스터 없음)")
        except Exception as e:
            errors.append(f"전투 디버그 실패: {e}")

        try:
            await admin_cog.debug_encounter.callback(
                admin_cog, self._make_interaction(ctx), "treasure", None, "normal", 0.1
            )
            results.append("인카운터 디버그 테스트 완료 (treasure)")
        except Exception as e:
            errors.append(f"인카운터 디버그 실패: {e}")

    @commands.command(name="e2e_gameflow")
    async def e2e_gameflow(self, ctx: commands.Context):
        """게임 플로우 스모크 E2E 테스트 (텍스트 명령)."""
        await self._run_e2e(ctx)

    @commands.command(name="e2e_dungeon_ui")
    async def e2e_dungeon_ui(self, ctx: commands.Context):
        """던전 UI 자동화 E2E 테스트."""
        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"
        os.environ["E2E_DUNGEON_MAX_STEPS"] = os.getenv("E2E_DUNGEON_MAX_STEPS") or "1"
        interaction = E2EGameFlow._FakeInteraction(ctx)
        cog = self.bot.get_cog("DungeonCommand")
        if not cog:
            await ctx.send("[E2E] DungeonCommand 코그를 찾지 못했습니다.")
            return
        await ctx.send("[E2E] 던전 UI 자동화 테스트 시작...")
        await cog.enter_dungeon.callback(cog, interaction)
        await ctx.send("[E2E] 던전 UI 자동화 테스트 완료")

    @commands.command(name="e2e_tower_ui")
    async def e2e_tower_ui(self, ctx: commands.Context):
        """타워 UI 자동화 E2E 테스트."""
        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"
        os.environ["E2E_TOWER_MAX_FLOORS"] = os.getenv("E2E_TOWER_MAX_FLOORS") or "1"
        interaction = E2EGameFlow._FakeInteraction(ctx)
        cog = self.bot.get_cog("TowerCommand")
        if not cog:
            await ctx.send("[E2E] TowerCommand 코그를 찾지 못했습니다.")
            return
        await ctx.send("[E2E] 타워 UI 자동화 테스트 시작...")
        await cog.weekly_tower.callback(cog, interaction)
        await ctx.send("[E2E] 타워 UI 자동화 테스트 완료")

    @commands.command(name="e2e_all")
    async def e2e_all(self, ctx: commands.Context):
        """게임 전체 스모크 E2E (텍스트 명령)."""
        await ctx.send("[E2E] 전체 테스트 시작...")

        results = []
        errors = []

        os.environ["E2E_UI_AUTOPILOT"] = "TRUE"

        if os.getenv("E2E_FORCE_TEMP_ADMIN") == "TRUE":
            add_temp_admin(ctx.author.id)
            results.append("임시 어드민 강제 설정 (E2E_FORCE_TEMP_ADMIN)")

        user = await find_account_by_discordid(ctx.author.id)
        if user is None:
            user = User(discord_id=ctx.author.id, username=ctx.author.display_name)
            await user.save()
            results.append("계정 자동 생성")
        else:
            results.append("계정 확인")

        await self._run_e2e(ctx)
        await self._run_dungeon_command_ui(ctx, user, results, errors)
        await self._run_user_commands_ui(ctx, user, results, errors)
        await self._run_help_ui(ctx, results, errors)
        await self._run_server_manage_ui(ctx, results, errors)
        await self._run_minigame_ui(ctx, results, errors)
        await self._run_auction_ui(ctx, results, errors)
        await self._run_admin_smoke(ctx, user, results, errors)
        await self._run_dungeon_spawn_smoke(results, errors)
        await self._run_tower_smoke(results, errors)
        await self._run_raid_minigame_smoke(user, results, errors)
        await self._run_minigame_smoke(results, errors)
        await self._run_auction_smoke(user, results, errors)
        await self.e2e_dungeon_ui(ctx)
        await self.e2e_tower_ui(ctx)

        if errors:
            await ctx.send(
                "[E2E] 전체 완료 (일부 실패)\n"
                + "- 성공\n"
                + "\n".join(f"  - {r}" for r in results)
                + "\n- 실패\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        else:
            await ctx.send(
                "[E2E] 전체 완료 (성공)\n"
                + "- 성공\n"
                + "\n".join(f"  - {r}" for r in results)
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not _e2e_enabled():
            return
        runtime = getattr(self.bot, "e2e_runtime", None)
        if runtime and await runtime.on_message(message):
            return
        if message.author is None:
            return
        if message.content not in ("!e2e_gameflow", "!e2e_all", "!e2e_dungeon_ui", "!e2e_tower_ui"):
            return
        # Allow only configured MCP bot id (so we can trigger via MCP)
        allowed_id = int(os.getenv("MCP_BOT_ID") or 0)
        if not message.author.bot or message.author.id != allowed_id:
            return
        ctx = await self.bot.get_context(message)
        if message.content == "!e2e_all":
            await self.e2e_all(ctx)
        elif message.content == "!e2e_dungeon_ui":
            await self.e2e_dungeon_ui(ctx)
        elif message.content == "!e2e_tower_ui":
            await self.e2e_tower_ui(ctx)
        else:
            await self._run_e2e(ctx)


async def setup(bot: commands.Bot):
    if not _e2e_enabled():
        logger.info("E2EGameFlow disabled (E2E_ENABLED != TRUE)")
        return
    await bot.add_cog(E2EGameFlow(bot))
