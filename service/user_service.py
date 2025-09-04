import re
from datetime import datetime

import bcrypt
import discord
import requests

from models import User
from models.repos import exists_account_by_username


async def register_user(username: str, raw_password1: str, raw_password2: str, discord_id: int,gender : str) -> User:
    if await exists_account_by_username(username):
        raise Exception('존재하는 유저 이름입니다.')
    if raw_password1 != raw_password2:
        raise Exception('패스워드가 동일하지 않습니다.')
    if not is_valid_password(raw_password1):
        raise Exception("옳바르지 않은 패스워드 양식입니다.")
    if gender not in ['남성', '여성','male','female']:
        raise Exception("존재하지 않는 성별입니다.")
    if gender == '남성':
        gender = 'male'
    elif gender == '여성':
        gender = 'female'
    hashed = bcrypt.hashpw(raw_password1.encode(), bcrypt.gensalt()).decode()
    user = User(username=username,
                password=hashed,
                discord_id=discord_id,
                cuha_point=0,
                gender=gender,
                baekjoon_id="",
                created_at=datetime.now(),
                user_role="user")
    await user.save()
    return user

def is_valid_password(raw_password1: str) -> bool:

    if len(raw_password1) < 6:
        return False

    _PASSWORD_PATTERN = re.compile(
        r"^(?=.*[A-Z])"         # 대문자 최소 1개
        r"(?=.*\d)"             # 숫자 최소 1개
        r"(?=.*[!@#$%^&*.])"    # 특수문자(!@#$%^&*) 최소 1개
        r"[A-Za-z\d!@#$%^&*.]+$"
    )

    if not _PASSWORD_PATTERN.match(raw_password1):
        return False

    return True

class SolvedACError(Exception):
    pass

TIER_EMOJI_NAME = {
    1: "1_",  2: "2_",  3: "3_",  4: "4_",  5: "5_",
    6: "6_",  7: "7_",  8: "8_",  9: "9_", 10: "10",
    11: "11", 12: "12", 13: "13", 14: "14", 15: "15",
    16: "16", 17: "17", 18: "18", 19: "19", 20: "20",
    21: "21", 22: "22", 23: "23", 24: "24", 25: "25",
    26: "26", 27: "27", 28: "28", 29: "29", 30: "30",
    31: "31"
}

TIER_MAP = {
    1: 'Bronze V', 2: 'Bronze IV', 3: 'Bronze III', 4: 'Bronze II', 5: 'Bronze I',
    6: 'Silver V', 7: 'Silver IV', 8: 'Silver III', 9: 'Silver II', 10: 'Silver I',
    11: 'Gold V', 12: 'Gold IV', 13: 'Gold III', 14: 'Gold II', 15: 'Gold I',
    16: 'Platinum V', 17: 'Platinum IV', 18: 'Platinum III', 19: 'Platinum II', 20: 'Platinum I',
    21: 'Diamond V', 22: 'Diamond IV', 23: 'Diamond III', 24: 'Diamond II', 25: 'Diamond I',
    26: 'Ruby V', 27: 'Ruby IV', 28: 'Ruby III', 29: 'Ruby II', 30: 'Ruby I', 31: 'Master'
}

async def fetch_json(url, params=None):
    try:
        response = requests.get(url, params=params, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            return response.json()
        raise SolvedACError(f"API 요청 실패 (status {response.status_code})")
    except Exception as e:
        raise SolvedACError(f"API 요청 중 오류 발생: {e}")

async def get_profile_embed(handle: str, bot: discord.Client):
    data = await fetch_json("https://solved.ac/api/v3/user/show", {"handle": handle})
    tier_num = data.get("tier", 0)

    solved_items = await get_solved_items(handle)

    emoji_lines = []
    line = ""
    for i, item in enumerate(solved_items):
        level = item.get("level", 0)
        emoji_name = TIER_EMOJI_NAME.get(level)
        emoji = discord.utils.get(bot.emojis, name=emoji_name)
        emoji_tag = f"<:{emoji.name}:{emoji.id}>" if emoji else "❓"
        line += f"{emoji_tag} "

        if (i + 1) % 10 == 0:
            emoji_lines.append(line.strip())
            line = ""
    if line:
        emoji_lines.append(line.strip())

    emoji_block = "\n".join(emoji_lines)

    emoji_name = TIER_EMOJI_NAME.get(data.get("tier", 0))
    emoji = discord.utils.get(bot.emojis, name=emoji_name)

    embed = discord.Embed(
        title=f"📊 {data.get('handle')}님의 백준 프로필",
        description=(
            f"**티어:** {TIER_MAP.get(tier_num, 'Unknown')} <:{emoji.name}:{emoji.id}> \n"
            f"**클래스** {data.get('class', 'N/A')} {data.get("classDecoration") if data.get("classDecoration") is not None else ""} \n"
            f"**레이팅:** {data.get('rating', 'N/A')}\n"
            f"**랭킹:** {data.get('rank', 'N/A')}\n"
            f"**상위 50 문제:**\n{emoji_block}"
        )
    )
    embed.set_thumbnail(url=data.get("profileImageUrl"))

    return embed

async def get_solved_items(handle: str):
    url = f"https://solved.ac/api/v3/search/problem?query=solved_by%3A{handle}&sort=level&direction=desc"
    data = await fetch_json(url)
    return data.get("items", [])

def build_problem_embed(items, page: int, bot: discord.Client, handle: str) -> discord.Embed:
    start = (page - 2) * 10
    end = start + 10
    current_items = items[start:end]

    title_list = ""
    emoji_list = ""

    for item in current_items:
        name = item.get("titleKo", "제목없음")
        short_name = name[:15] + "..." if len(name) > 15 else name
        title_url = f"https://www.acmicpc.net/problem/{item['problemId']}"
        title_list += f"[{short_name}]({title_url})\n"

        level = item.get("level", 0)
        emoji_name = TIER_EMOJI_NAME.get(level)
        emoji = discord.utils.get(bot.emojis, name=emoji_name)
        emoji_tag = f"<:{emoji.name}:{emoji.id}>" if emoji else "❓"
        emoji_list += f"{emoji_tag}\n"

    embed = discord.Embed(
        title=f"📄 {handle}님의 푼 문제 목록 (페이지 {page})"
    )
    embed.add_field(name="문제 제목", value=title_list.strip(), inline=True)
    embed.add_field(name="티어", value=emoji_list.strip(), inline=True)
    return embed
