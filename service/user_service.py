import re
from datetime import datetime

import bcrypt
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
