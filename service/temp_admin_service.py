"""
임시 어드민 관리 서비스

봇 실행 중에만 유효한 임시 관리자 권한을 관리합니다.
봇 재시작 시 모든 임시 권한이 초기화됩니다.
"""
import discord

# 임시 어드민 목록 (Discord User ID)
_temp_admins: set[int] = set()


def is_admin_or_temp(interaction: discord.Interaction) -> bool:
    """
    실제 Discord 관리자이거나 임시 어드민인지 확인

    Args:
        interaction: Discord Interaction 객체

    Returns:
        관리자 권한 여부
    """
    # 실제 Discord 관리자 권한 체크
    if interaction.user.guild_permissions.administrator:
        return True

    # 임시 어드민 체크
    return interaction.user.id in _temp_admins


def add_temp_admin(user_id: int) -> bool:
    """
    임시 어드민 추가

    Args:
        user_id: Discord User ID

    Returns:
        추가 성공 여부 (이미 존재하면 False)
    """
    if user_id in _temp_admins:
        return False
    _temp_admins.add(user_id)
    return True


def remove_temp_admin(user_id: int) -> bool:
    """
    임시 어드민 제거

    Args:
        user_id: Discord User ID

    Returns:
        제거 성공 여부 (존재하지 않으면 False)
    """
    if user_id not in _temp_admins:
        return False
    _temp_admins.discard(user_id)
    return True


def get_all_temp_admins() -> set[int]:
    """
    모든 임시 어드민 목록 조회

    Returns:
        임시 어드민 Discord User ID set
    """
    return _temp_admins.copy()


def is_temp_admin(user_id: int) -> bool:
    """
    임시 어드민 여부 확인

    Args:
        user_id: Discord User ID

    Returns:
        임시 어드민 여부
    """
    return user_id in _temp_admins
