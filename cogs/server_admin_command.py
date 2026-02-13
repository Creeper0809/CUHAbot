import discord
from discord.ext import commands
from discord import app_commands

from bot import GUILD_IDS
from models import Item, Skill_Model, UserStatEnum
from models.repos.static_cache import load_static_data, get_static_cache_summary
from models.repos.users_repo import find_account_by_discordid
from service.item.inventory_service import InventoryService
from service.skill.skill_ownership_service import SkillOwnershipService
from service.player.user_service import UserService
from service.temp_admin_service import (
    is_admin_or_temp, add_temp_admin, remove_temp_admin,
    get_all_temp_admins
)
from exceptions import ItemNotFoundError, InventoryFullError, SkillNotFoundError

admin = app_commands.Group(
    name="admin",
    description="관리자 전용 명령어",
    guild_ids=GUILD_IDS
)

class ServerAdminCammand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="임시어드민",
        description="[관리자] 대상에게 임시 어드민 권한을 부여합니다 (봇 재시작 시 초기화)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="임시 어드민으로 지정할 대상")
    @commands.has_permissions(administrator=True)
    async def grant_temp_admin(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ):
        if not add_temp_admin(target.id):
            await interaction.response.send_message(
                f"⚠️ **{target.display_name}**은(는) 이미 임시 어드민입니다.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{target.display_name}**을(를) 임시 어드민으로 지정했습니다.\n"
            f"💡 봇 재시작 시 권한이 초기화됩니다.",
            ephemeral=True
        )

    @app_commands.command(
        name="임시어드민해제",
        description="[관리자] 대상의 임시 어드민 권한을 해제합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="임시 어드민 권한을 해제할 대상")
    @commands.has_permissions(administrator=True)
    async def revoke_temp_admin(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ):
        if not remove_temp_admin(target.id):
            await interaction.response.send_message(
                f"⚠️ **{target.display_name}**은(는) 임시 어드민이 아닙니다.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{target.display_name}**의 임시 어드민 권한을 해제했습니다.",
            ephemeral=True
        )

    @app_commands.command(
        name="임시어드민목록",
        description="[관리자] 현재 임시 어드민 목록을 확인합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @commands.has_permissions(administrator=True)
    async def list_temp_admins_cmd(self, interaction: discord.Interaction):
        temp_admins = get_all_temp_admins()
        if not temp_admins:
            await interaction.response.send_message(
                "📋 현재 임시 어드민이 없습니다.",
                ephemeral=True
            )
            return

        admin_list = []
        for user_id in temp_admins:
            user = interaction.guild.get_member(user_id)
            if user:
                admin_list.append(f"• {user.display_name} (`{user_id}`)")
            else:
                admin_list.append(f"• Unknown User (`{user_id}`)")

        await interaction.response.send_message(
            f"📋 **임시 어드민 목록** ({len(temp_admins)}명)\n" + "\n".join(admin_list),
            ephemeral=True
        )

    @app_commands.command(
        name="clear",
        description="채널에서 최근 메시지 n개를 삭제합니다."
    )
    @app_commands.describe(amount="삭제할 메시지 수 (1~100)")
    @commands.has_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if isinstance(interaction.channel, discord.DMChannel):
            deleted_count = 0
            async for msg in interaction.channel.history(limit=50):
                if msg.author == interaction.client.user:
                    try:
                        await msg.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        # 이미 삭제된 메시지는 무시
                        pass
            await interaction.response.send_message(
                f"{deleted_count}개의 메시지를 삭제했습니다.",
                ephemeral=True
            )
            return
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message("메시지 관리 권한이 필요합니다.", ephemeral=True)
            return

        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message("봇에 메시지 관리 권한이 없습니다.", ephemeral=True)
            return

        if amount < 1 or amount > 100:
            await interaction.response.send_message("1부터 100 사이의 수를 입력해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"{len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"메시지 삭제 실패: {e}", ephemeral=True)

    @app_commands.command(
        name="데베재캐시",
        description="DB 기준 모든 정적 데이터를 다시 캐시합니다"
    )
    @commands.has_permissions(administrator=True)
    async def re_cache(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await load_static_data()
        summary = get_static_cache_summary()
        lines = [
            "✅ 데이터베이스 기준 정적 데이터 재캐시 완료",
            f"- 던전: {summary['dungeons']}",
            f"- 몬스터: {summary['monsters']}",
            f"- 아이템: {summary['items']}",
            f"- 스킬: {summary['skills']}",
            f"- 스폰 던전 수: {summary['spawns_dungeons']}",
            f"- 장비 아이템: {summary['equipment_items']}",
            f"- 세트 매핑: {summary['set_memberships']}",
            f"- 상자 드랍 타입: {summary['box_drop_types']}",
            f"- 레이드: {summary['raids']}",
            f"- 레이드 타겟팅 룰: {summary['raid_targeting_rules']}",
            f"- 레이드 특수 액션: {summary['raid_special_actions']}",
            f"- 레이드 미니게임 그룹: {summary['raid_minigame_groups']}",
            f"- 레이드 전환 그룹: {summary['raid_transition_groups']}",
            f"- 레이드 파츠 그룹: {summary['raid_part_groups']}",
            f"- 레이드 기믹 그룹: {summary['raid_gimmick_groups']}",
            f"- 레이드 보스 스킬 그룹: {summary['raid_boss_skill_groups']}",
            f"- 레이드 미니게임 규칙: {summary['raid_minigame_rules']}",
        ]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="아이템지급",
        description="[관리자] 대상에게 아이템을 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        item_id="아이템 ID",
        quantity="수량",
        enhancement_level="강화 레벨 (기본 0)",
        grade="장비 등급 (미지정시 랜덤)"
    )
    @app_commands.choices(grade=[
        app_commands.Choice(name="D", value="D"),
        app_commands.Choice(name="C", value="C"),
        app_commands.Choice(name="B", value="B"),
        app_commands.Choice(name="A", value="A"),
        app_commands.Choice(name="S", value="S"),
        app_commands.Choice(name="SS", value="SS"),
        app_commands.Choice(name="SSS", value="SSS"),
        app_commands.Choice(name="신화", value="신화"),
    ])
    async def give_item(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int = 1,
        enhancement_level: int = 0,
        target: discord.Member = None,
        grade: app_commands.Choice[str] = None,
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        item = await Item.get_or_none(id=item_id)
        if not item:
            await interaction.response.send_message(
                "아이템을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        if quantity < 1:
            await interaction.response.send_message(
                "수량은 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        # 장비 아이템이면 등급 부여
        from resources.item_emoji import ItemType
        instance_grade = 0
        special_effects = None

        if item.type == ItemType.EQUIP:
            from config.grade import get_grade_name_map
            from service.item.grade_service import GradeService

            if grade:
                grade_name_map = get_grade_name_map()
                instance_grade = grade_name_map.get(grade.value, 0)
            else:
                instance_grade = GradeService.roll_grade("normal")

            special_effects = GradeService.roll_special_effects(instance_grade)

        try:
            await InventoryService.add_item(
                target_user,
                item_id=item_id,
                quantity=quantity,
                enhancement_level=enhancement_level,
                instance_grade=instance_grade,
                special_effects=special_effects,
            )
        except InventoryFullError:
            await interaction.response.send_message(
                "인벤토리가 가득 찼습니다.",
                ephemeral=True
            )
            return
        except ItemNotFoundError as e:
            await interaction.response.send_message(
                f"{e.message}",
                ephemeral=True
            )
            return

        target_name = target.display_name if target else interaction.user.display_name
        grade_text = ""
        if instance_grade > 0:
            from service.item.grade_service import GradeService
            grade_text = f" ({GradeService.get_grade_display(instance_grade)})"

        await interaction.response.send_message(
            f"✅ **{target_name}**에게 **{item.name}**{grade_text} x{quantity} 지급 완료",
            ephemeral=True
        )

    async def item_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[int]]:
        query = current.strip()
        if not query:
            items = await Item.all().order_by("id").limit(25)
        elif query.isdigit():
            items = await Item.filter(id__icontains=query).limit(25)
        else:
            items = await Item.filter(name__icontains=query).limit(25)

        choices = []
        for item in items:
            # 설명 추가 (100자 제한)
            desc = item.description or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."

            name = f"{item.id} - {item.name}"
            if desc:
                name += f" ({desc})"

            # Discord 제한: 100자
            if len(name) > 100:
                name = name[:97] + "..."

            choices.append(app_commands.Choice(name=name, value=item.id))

        return choices

    give_item.autocomplete("item_id")(item_id_autocomplete)

    @app_commands.command(
        name="스킬지급",
        description="[관리자] 대상에게 스킬을 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        skill_id="스킬 ID",
        quantity="수량"
    )
    async def give_skill(
        self,
        interaction: discord.Interaction,
        skill_id: int,
        quantity: int = 1,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        skill = await Skill_Model.get_or_none(id=skill_id)
        if not skill:
            await interaction.response.send_message(
                "스킬을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        if quantity < 1:
            await interaction.response.send_message(
                "수량은 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        try:
            await SkillOwnershipService.add_skill(
                target_user,
                skill_id=skill_id,
                quantity=quantity
            )
        except SkillNotFoundError as e:
            await interaction.response.send_message(
                f"스킬을 찾을 수 없습니다: {e}",
                ephemeral=True
            )
            return

        target_name = target.display_name if target else interaction.user.display_name
        await interaction.response.send_message(
            f"✅ **{target_name}**에게 **{skill.name}** x{quantity} 지급 완료",
            ephemeral=True
        )

    async def skill_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[int]]:
        query = current.strip()
        if not query:
            skills = await Skill_Model.all().order_by("id").limit(25)
        elif query.isdigit():
            # ID 검색
            skill_id_int = int(query)
            skills = await Skill_Model.filter(id__gte=skill_id_int).order_by("id").limit(25)
        else:
            # 이름 검색
            skills = await Skill_Model.filter(name__icontains=query).limit(25)

        choices = []
        for skill in skills:
            # 설명 추가 (100자 제한)
            desc = skill.description or ""
            if len(desc) > 35:
                desc = desc[:32] + "..."

            # 속성 추가
            attr = skill.attribute or "무속성"

            name = f"{skill.id} - {skill.name} [{attr}]"
            if desc:
                name += f" {desc}"

            # Discord 제한: 100자
            if len(name) > 100:
                name = name[:97] + "..."

            choices.append(app_commands.Choice(name=name, value=skill.id))

        return choices

    give_skill.autocomplete("skill_id")(skill_id_autocomplete)

    @app_commands.command(
        name="경험치지급",
        description="[관리자] 대상에게 경험치를 지급합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        target="지급 대상 (미지정시 자신)",
        amount="경험치 양"
    )
    async def give_exp(
        self,
        interaction: discord.Interaction,
        amount: int,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        if amount < 1:
            await interaction.response.send_message(
                "경험치는 1 이상이어야 합니다.",
                ephemeral=True
            )
            return

        # 경험치 추가 및 레벨업 처리 (RewardService 사용)
        from service.economy.reward_service import RewardService

        reward_result = await RewardService.apply_rewards(
            target_user,
            exp_gained=amount,
            gold_gained=0
        )

        target_name = target.display_name if target else interaction.user.display_name

        if reward_result.level_up:
            level_up = reward_result.level_up
            response = (
                f"✅ **{target_name}**에게 경험치 **+{amount:,}** 지급 완료\n"
                f"🎉 레벨업! **Lv.{level_up.old_level}** → **Lv.{level_up.new_level}** "
                f"(+{level_up.levels_gained})\n"
                f"📊 스탯 포인트 **+{level_up.stat_points_gained}**"
            )
        else:
            response = (
                f"✅ **{target_name}**에게 경험치 **+{amount:,}** 지급 완료\n"
                f"📈 현재 레벨: **Lv.{target_user.level}** "
                f"(총 경험치: {target_user.exp:,})"
            )

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(
        name="도감전체해금",
        description="[관리자] 대상의 도감을 전체 해금합니다"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(target="해금할 대상 (미지정시 자신)")
    async def unlock_all_collection(
        self,
        interaction: discord.Interaction,
        target: discord.Member = None
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        # 먼저 defer() 호출 (3초 타임아웃 방지)
        await interaction.response.defer(ephemeral=True)

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.followup.send(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        # 모든 아이템, 스킬, 몬스터 등록 (bulk insert)
        from models.repos.static_cache import item_cache, skill_cache_by_id, monster_cache_by_id
        from models.user_collection import UserCollection, CollectionType

        # 기존 도감 항목 조회 (중복 방지)
        existing_collections = await UserCollection.filter(user=target_user).all()
        existing_set = {
            (col.collection_type, col.target_id) for col in existing_collections
        }

        # 신규 도감 항목 준비
        new_collections = []

        # 아이템 추가
        for item_id in item_cache.keys():
            if (CollectionType.ITEM, item_id) not in existing_set:
                new_collections.append(
                    UserCollection(
                        user=target_user,
                        collection_type=CollectionType.ITEM,
                        target_id=item_id
                    )
                )

        item_count = len([c for c in new_collections if c.collection_type == CollectionType.ITEM])

        # 스킬 추가 (몬스터 스킬 제외, ID < 9000)
        for skill_id in skill_cache_by_id.keys():
            if skill_id < 9000:  # 몬스터 스킬 제외
                if (CollectionType.SKILL, skill_id) not in existing_set:
                    new_collections.append(
                        UserCollection(
                            user=target_user,
                            collection_type=CollectionType.SKILL,
                            target_id=skill_id
                        )
                    )

        skill_count = len([c for c in new_collections if c.collection_type == CollectionType.SKILL]) - item_count

        # 몬스터 추가
        for monster_id in monster_cache_by_id.keys():
            if (CollectionType.MONSTER, monster_id) not in existing_set:
                new_collections.append(
                    UserCollection(
                        user=target_user,
                        collection_type=CollectionType.MONSTER,
                        target_id=monster_id
                    )
                )

        monster_count = len(new_collections) - item_count - skill_count

        # 벌크 삽입
        if new_collections:
            await UserCollection.bulk_create(new_collections)

        target_name = target.display_name if target else interaction.user.display_name

        embed = discord.Embed(
            title="📚 도감 전체 해금 완료",
            description=f"**{target_name}**의 도감을 전체 해금했습니다!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🎒 아이템",
            value=f"{item_count}개 신규 등록",
            inline=True
        )

        embed.add_field(
            name="⚔️ 스킬",
            value=f"{skill_count}개 신규 등록",
            inline=True
        )

        embed.add_field(
            name="👹 몬스터",
            value=f"{monster_count}개 신규 등록",
            inline=True
        )

        total_count = item_count + skill_count + monster_count
        embed.set_footer(text=f"총 {total_count}개 항목 신규 등록")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="전투",
        description="[관리자] 특정 몬스터와 즉시 전투를 시작합니다 (디버그용)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        monster_id="전투할 몬스터 ID",
        target="전투 대상 (미지정시 자신)",
        field_effect="필드 효과 강제 설정 (선택사항)"
    )
    @app_commands.choices(field_effect=[
        app_commands.Choice(name="랜덤 (기본)", value="random"),
        app_commands.Choice(name="없음", value="none"),
        app_commands.Choice(name="🔥 화상 지대", value="burn_zone"),
        app_commands.Choice(name="❄️ 동결 지대", value="freeze_zone"),
        app_commands.Choice(name="⚡ 감전 지대", value="shock_zone"),
        app_commands.Choice(name="🌊 익사 타이머", value="drown_timer"),
        app_commands.Choice(name="🌀 차원 불안정", value="chaos_rift"),
        app_commands.Choice(name="⏰ 시간 왜곡", value="time_warp"),
        app_commands.Choice(name="🕳️ 공허의 잠식", value="void_erosion"),
        app_commands.Choice(name="💧 수압 효과", value="water_pressure"),
        app_commands.Choice(name="✨ 각성의 기운", value="awakening_aura"),
        app_commands.Choice(name="💀 고대의 저주", value="ancient_curse"),
    ])
    async def debug_combat(
        self,
        interaction: discord.Interaction,
        monster_id: int,
        target: discord.Member = None,
        field_effect: str = "random"
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        # 몬스터 확인
        from models.repos.static_cache import monster_cache_by_id
        if monster_id not in monster_cache_by_id:
            await interaction.response.send_message(
                f"❌ 몬스터 ID `{monster_id}`를 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        monster = monster_cache_by_id[monster_id].copy()

        # HP 확인
        if target_user.now_hp <= 0:
            target_user.now_hp = 1

        # 스킬 덱 로드
        from service.skill.skill_deck_service import SkillDeckService
        from service.item.equipment_service import EquipmentService
        await SkillDeckService.load_deck_to_user(target_user)
        await EquipmentService.apply_equipment_stats(target_user)

        # 전투/도망 선택 화면 표시
        from service.dungeon.encounter_processor import _ask_fight_or_flee

        monsters = [monster]
        will_fight = await _ask_fight_or_flee(interaction, monsters)

        if will_fight is None:
            await interaction.followup.send("아무 행동도 하지 않았습니다.", ephemeral=True)
            return

        if not will_fight:
            await interaction.followup.send("전투에서 도망쳤습니다!", ephemeral=True)
            return

        # 전투 컨텍스트 생성
        from service.dungeon.combat_context import CombatContext
        from service.dungeon.combat_executor import execute_combat_context
        from service.session import DungeonSession

        context = CombatContext.from_single(monster)

        # 필드 효과 설정
        if field_effect != "none":
            from service.dungeon.field_effects import (
                FieldEffectType, create_field_effect, roll_random_field_effect
            )

            if field_effect == "random":
                # 기본 30% 확률 적용
                import random
                from config import COMBAT
                if random.random() < COMBAT.FIELD_EFFECT_SPAWN_RATE:
                    context.field_effect = roll_random_field_effect()
            else:
                # 강제 필드 효과 적용
                effect_type = FieldEffectType(field_effect)
                context.field_effect = create_field_effect(effect_type)

        # 임시 세션 생성 (디버그 전투용)
        debug_session = DungeonSession(
            user_id=target_discord_id,
            user=target_user,
            dungeon=None,  # 디버그 전투는 던전 없음
            allow_intervention=False  # 디버그 전투는 난입 불가
        )

        # 전투 시작
        try:
            result = await execute_combat_context(debug_session, interaction, context)

            target_name = target.display_name if target else interaction.user.display_name

            # 전투 결과 메시지
            if result.victory:
                result_msg = f"✅ **{target_name}** 승리!\n"
                result_msg += f"💰 골드: {result.gold_reward}G\n"
                result_msg += f"⭐ 경험치: {result.exp_reward}\n"
                if result.level_up:
                    result_msg += f"🎉 레벨 업! **Lv.{result.new_level}**"
            else:
                result_msg = f"💀 **{target_name}** 패배...\n"
                result_msg += f"HP: {target_user.now_hp}/{target_user.get_stat()[UserStatEnum.HP]}"

            await interaction.followup.send(result_msg)
        except Exception as e:
            await interaction.followup.send(
                f"❌ 전투 실행 중 오류 발생: {e}",
                ephemeral=True
            )

    async def monster_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[int]]:
        from models.repos.static_cache import monster_cache_by_id

        query = current.strip().lower()
        monsters = list(monster_cache_by_id.values())

        if query:
            # ID 또는 이름으로 필터링
            if query.isdigit():
                # ID 검색
                query_id = int(query)
                monsters = [m for m in monsters if str(m.id).startswith(str(query_id))]
            else:
                # 이름 검색
                monsters = [m for m in monsters if query in m.name.lower()]

        # 최대 25개까지
        monsters = sorted(monsters, key=lambda m: m.id)[:25]

        choices = []
        for monster in monsters:
            # 속성 표시
            attr = getattr(monster, 'attribute', '무속성')
            hp = getattr(monster, 'hp', 0)

            name = f"{monster.id} - {monster.name} [{attr}] HP:{hp}"

            # Discord 제한: 100자
            if len(name) > 100:
                name = name[:97] + "..."

            choices.append(app_commands.Choice(name=name, value=monster.id))

        return choices

    debug_combat.autocomplete("monster_id")(monster_id_autocomplete)

    @app_commands.command(
        name="인카운터",
        description="[관리자] 특정 인카운터를 즉시 발생시킵니다 (디버그용)"
    )
    @app_commands.guilds(*GUILD_IDS)
    @app_commands.describe(
        encounter_type="발생시킬 인카운터 종류",
        target="대상 유저 (미지정시 자신)",
        chest_grade="보물상자 등급 (보물상자 인카운터 전용)",
        damage_percent="함정 피해 비율 (함정 인카운터 전용, 기본 10%)"
    )
    @app_commands.choices(encounter_type=[
        app_commands.Choice(name="📦 보물상자", value="treasure"),
        app_commands.Choice(name="⚠️ 함정", value="trap"),
        app_commands.Choice(name="✨ 랜덤 이벤트", value="event"),
        app_commands.Choice(name="🧙 NPC", value="npc"),
        app_commands.Choice(name="🚪 숨겨진 방", value="hidden_room"),
    ])
    @app_commands.choices(chest_grade=[
        app_commands.Choice(name="일반 상자", value="normal"),
        app_commands.Choice(name="은 상자", value="silver"),
        app_commands.Choice(name="금 상자", value="gold"),
    ])
    async def debug_encounter(
        self,
        interaction: discord.Interaction,
        encounter_type: str,
        target: discord.Member = None,
        chest_grade: str = "normal",
        damage_percent: float = 0.1
    ):
        # 권한 체크
        if not is_admin_or_temp(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target_discord_id = target.id if target else interaction.user.id
        target_user = await find_account_by_discordid(target_discord_id)
        if not target_user:
            await interaction.response.send_message(
                "대상 유저가 등록되어 있지 않습니다.",
                ephemeral=True
            )
            return

        # HP 확인
        if target_user.now_hp <= 0:
            target_user.now_hp = 1

        await interaction.response.defer()

        # 더미 세션 생성
        from service.session import DungeonSession, SessionType
        from models.repos.static_cache import dungeon_cache

        # 첫 번째 던전을 가져옴 (더미용)
        dummy_dungeon = list(dungeon_cache.values())[0] if dungeon_cache else None

        session = DungeonSession(
            user_id=target_user.discord_id,
            user=target_user,
            dungeon=dummy_dungeon,
            status=SessionType.EXPLORING
        )
        session.total_exp = 0
        session.total_gold = 0

        # 인카운터 생성 및 실행
        from service.dungeon.encounter_types import (
            TreasureEncounter, TrapEncounter, RandomEventEncounter,
            NPCEncounter, HiddenRoomEncounter
        )

        try:
            if encounter_type == "treasure":
                encounter = TreasureEncounter(chest_grade=chest_grade)
                emoji = "📦"
                type_name = f"{chest_grade.upper()} 보물상자"
            elif encounter_type == "trap":
                encounter = TrapEncounter(damage_percent=damage_percent)
                emoji = "⚠️"
                type_name = "함정"
            elif encounter_type == "event":
                encounter = RandomEventEncounter()
                emoji = "✨"
                type_name = "랜덤 이벤트"
            elif encounter_type == "npc":
                encounter = NPCEncounter()
                emoji = "🧙"
                type_name = "NPC"
            elif encounter_type == "hidden_room":
                encounter = HiddenRoomEncounter()
                emoji = "🚪"
                type_name = "숨겨진 방"
            else:
                await interaction.followup.send(
                    "❌ 잘못된 인카운터 타입입니다.",
                    ephemeral=True
                )
                return

            # 인카운터 실행
            result = await encounter.execute(session, interaction)

            target_name = target.display_name if target else interaction.user.display_name

            # 결과 임베드 생성
            embed = discord.Embed(
                title=f"{emoji} {type_name} 발생!",
                description=f"**{target_name}**에게 인카운터가 발생했습니다.",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="📜 결과",
                value=result.message,
                inline=False
            )

            # 획득 정보
            gains = []
            if result.exp_gained > 0:
                gains.append(f"⭐ 경험치: +{result.exp_gained}")
            if result.gold_gained > 0:
                gains.append(f"💰 골드: +{result.gold_gained}")
            if result.gold_gained < 0:
                gains.append(f"💸 골드: {result.gold_gained}")
            if result.damage_taken > 0:
                gains.append(f"❤️ HP: -{result.damage_taken}")
            if result.healing_received > 0:
                gains.append(f"💚 HP: +{result.healing_received}")
            if result.items_gained:
                items_text = ", ".join([f"**{item}**" for item in result.items_gained])
                gains.append(f"🎁 아이템: {items_text}")

            if gains:
                embed.add_field(
                    name="📊 변동 사항",
                    value="\n".join(gains),
                    inline=False
                )

            # 현재 상태
            from models import UserStatEnum
            user_stat = target_user.get_stat()
            max_hp = user_stat[UserStatEnum.HP]
            hp_pct = int((target_user.now_hp / max_hp) * 100) if max_hp > 0 else 0

            embed.add_field(
                name="👤 현재 상태",
                value=(
                    f"❤️ HP: **{target_user.now_hp}** / {max_hp} ({hp_pct}%)\n"
                    f"💰 골드: **{target_user.gold:,}**"
                ),
                inline=False
            )

            embed.set_footer(text=f"세션 누적: 💎 {session.total_exp} EXP | 💰 {session.total_gold} G")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            await interaction.followup.send(
                f"❌ 인카운터 실행 중 오류 발생:\n```\n{e}\n```\n\n상세:\n```\n{error_detail[:1000]}\n```",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerAdminCammand(bot))
