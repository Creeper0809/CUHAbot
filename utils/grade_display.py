"""
등급 표시 유틸리티

아이템/스킬 이름에 등급별 색상 이모지를 추가합니다.
"""


def get_grade_emoji(grade_id: int) -> str:
    """
    등급 ID에 따른 이모지 반환

    Args:
        grade_id: 등급 ID (1=D, 2=C, 3=B, 4=A, 5=S, 6=SS, 7=SSS, 8=Mythic)

    Returns:
        등급 이모지
    """
    grade_emojis = {
        1: "⚪",  # D등급 - 회색
        2: "🟢",  # C등급 - 녹색
        3: "🔵",  # B등급 - 파란색
        4: "🟣",  # A등급 - 보라색
        5: "🟡",  # S등급 - 금색
        6: "🟠",  # SS등급 - 주황색
        7: "🔴",  # SSS등급 - 붉은색
        8: "💎",  # 신화등급 - 다이아몬드
    }
    return grade_emojis.get(grade_id, "⚫")


def get_grade_name(grade_id: int) -> str:
    """
    등급 ID에 따른 이름 반환

    Args:
        grade_id: 등급 ID (1=D, 2=C, 3=B, 4=A, 5=S, 6=SS, 7=SSS, 8=Mythic)

    Returns:
        등급 이름
    """
    grade_names = {
        1: "D",
        2: "C",
        3: "B",
        4: "A",
        5: "S",
        6: "SS",
        7: "SSS",
        8: "신화",
    }
    return grade_names.get(grade_id, "?")


def format_item_name(name: str, grade_id: int = None) -> str:
    """
    아이템 이름에 등급 이모지 추가

    Args:
        name: 아이템 이름
        grade_id: 등급 ID (없으면 이모지 없이 반환)

    Returns:
        포맷된 이름 (예: "🟣 전설의 검")
    """
    if grade_id:
        return f"{get_grade_emoji(grade_id)} {name}"
    return name


def format_skill_name(name: str, grade_id: int = None) -> str:
    """
    스킬 이름에 등급 이모지 추가

    Args:
        name: 스킬 이름
        grade_id: 등급 ID (없으면 이모지 없이 반환)

    Returns:
        포맷된 이름 (예: "🔵 화염구")
    """
    if grade_id:
        return f"{get_grade_emoji(grade_id)} {name}"
    return name


def format_item_with_grade_text(name: str, grade_id: int = None) -> str:
    """
    아이템 이름에 등급 텍스트 추가

    Args:
        name: 아이템 이름
        grade_id: 등급 ID (없으면 텍스트 없이 반환)

    Returns:
        포맷된 이름 (예: "🟣 전설의 검 [A]")
    """
    if grade_id:
        emoji = get_grade_emoji(grade_id)
        grade = get_grade_name(grade_id)
        return f"{emoji} {name} [{grade}]"
    return name


def format_skill_with_grade_text(name: str, grade_id: int = None) -> str:
    """
    스킬 이름에 등급 텍스트 추가

    Args:
        name: 스킬 이름
        grade_id: 등급 ID (없으면 텍스트 없이 반환)

    Returns:
        포맷된 이름 (예: "🔵 화염구 [B]")
    """
    if grade_id:
        emoji = get_grade_emoji(grade_id)
        grade = get_grade_name(grade_id)
        return f"{emoji} {name} [{grade}]"
    return name
