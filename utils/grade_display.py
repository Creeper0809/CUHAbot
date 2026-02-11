"""
등급 표시 유틸리티

아이템/스킬 이름에 등급별 ANSI 색상을 추가합니다.
"""


def get_grade_ansi_color(grade_id: int) -> str:
    """
    등급 ID에 따른 ANSI 색상 코드 반환

    Args:
        grade_id: 등급 ID (1=D, 2=C, 3=B, 4=A, 5=S, 6=SS, 7=SSS, 8=Mythic)

    Returns:
        ANSI 색상 코드
    """
    ansi_colors = {
        1: "\u001b[0;37m",   # D등급 - 회색
        2: "\u001b[0;32m",   # C등급 - 녹색
        3: "\u001b[0;34m",   # B등급 - 파란색
        4: "\u001b[0;35m",   # A등급 - 보라색
        5: "\u001b[1;33m",   # S등급 - 밝은 노랑
        6: "\u001b[1;31m",   # SS등급 - 밝은 빨강
        7: "\u001b[1;35m",   # SSS등급 - 밝은 보라
        8: "\u001b[1;36m",   # 신화등급 - 밝은 청록
    }
    return ansi_colors.get(grade_id, "\u001b[0;37m")


def get_grade_emoji(grade_id: int) -> str:
    """
    등급 ID에 따른 이모지 반환 (레거시)

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
    아이템 이름에 등급 ANSI 색상 추가

    Args:
        name: 아이템 이름
        grade_id: 등급 ID (없으면 색상 없이 반환)

    Returns:
        포맷된 이름 (예: "[S] 전설의 검")
    """
    if grade_id:
        grade_name = get_grade_name(grade_id)
        return f"[{grade_name}] {name}"
    return name


def format_skill_name(name: str, grade_id: int = None) -> str:
    """
    스킬 이름에 등급 ANSI 색상 추가

    Args:
        name: 스킬 이름
        grade_id: 등급 ID (없으면 색상 없이 반환)

    Returns:
        포맷된 이름 (예: "[B] 화염구")
    """
    if grade_id:
        grade_name = get_grade_name(grade_id)
        return f"[{grade_name}] {name}"
    return name


def format_item_with_ansi(name: str, grade_id: int = None) -> str:
    """
    아이템 이름에 ANSI 색상 적용 (코드블록용)

    Args:
        name: 아이템 이름
        grade_id: 등급 ID (없으면 색상 없이 반환)

    Returns:
        ANSI 색상이 적용된 이름
    """
    if grade_id:
        color = get_grade_ansi_color(grade_id)
        grade = get_grade_name(grade_id)
        reset = "\u001b[0m"
        return f"{color}[{grade}] {name}{reset}"
    return name


def format_skill_with_ansi(name: str, grade_id: int = None) -> str:
    """
    스킬 이름에 ANSI 색상 적용 (코드블록용)

    Args:
        name: 스킬 이름
        grade_id: 등급 ID (없으면 색상 없이 반환)

    Returns:
        ANSI 색상이 적용된 이름
    """
    if grade_id:
        color = get_grade_ansi_color(grade_id)
        grade = get_grade_name(grade_id)
        reset = "\u001b[0m"
        return f"{color}[{grade}] {name}{reset}"
    return name


def format_item_with_grade_text(name: str, grade_id: int = None) -> str:
    """
    아이템 이름에 등급 텍스트 추가 (레거시)

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
    스킬 이름에 등급 텍스트 추가 (레거시)

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
