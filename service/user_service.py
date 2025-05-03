import re

import bcrypt
from db.models import User

async def register_user(username: str, raw_password1: str, raw_password2: str, discord_id: int) -> User:
    if not is_valid_password(raw_password1,raw_password2):
        raise ValueError("옳바르지 않은 패스워드 양식입니다. 다시 회원가입을 진행해주세요")
    hashed = bcrypt.hashpw(raw_password1.encode(), bcrypt.gensalt()).decode()
    user = User(username=username, password=hashed, discord_id=discord_id)
    await user.save()
    return user

def is_valid_password(raw_password1: str,raw_password2 : str) -> bool:
    if raw_password1 != raw_password2:
        return False

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
