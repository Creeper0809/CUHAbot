"""
기여도 추적 (Contribution Tracker)

전투 중 각 참가자의 기여도를 추적하고 보상 분배 배율을 계산합니다.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from service.session import DungeonSession
    from models import User

logger = logging.getLogger(__name__)


def record_contribution(
    session: "DungeonSession",
    actor: "User",
    damage: int = 0,
    healing: int = 0
) -> None:
    """
    기여도 기록

    Args:
        session: 던전 세션
        actor: 행동한 엔티티
        damage: 입힌 데미지
        healing: 제공한 치유량
    """
    user_id = actor.discord_id

    # 기여도 점수 계산
    # - 데미지: 100% (1:1)
    # - 치유: 80% (0.8:1)
    # - 행동 보너스: 10점 (참여도)
    contribution_score = int(damage * 1.0 + healing * 0.8 + 10)

    # 누적
    if user_id not in session.contribution:
        session.contribution[user_id] = 0

    session.contribution[user_id] += contribution_score


def get_carry_penalty_multiplier(
    intervener_level: int,
    leader_level: int
) -> float:
    """
    캐리 방지 패널티 배율 계산

    파티 리더보다 레벨이 높은 난입자는 보상이 감소합니다.

    Args:
        intervener_level: 난입자 레벨
        leader_level: 파티 리더 레벨

    Returns:
        보상 배율 (0.0 ~ 1.0)
    """
    level_diff = intervener_level - leader_level

    if level_diff >= 15:
        return 0.0  # 보상 없음
    elif level_diff >= 10:
        return 0.05  # 5%
    elif level_diff >= 5:
        return 0.2  # 20%
    else:
        return 1.0  # 정상


async def distribute_rewards(
    session: "DungeonSession",
    total_exp: int,
    total_gold: int
) -> dict[int, dict[str, int]]:
    """
    기여도 비례 보상 분배

    Args:
        session: 던전 세션
        total_exp: 총 경험치
        total_gold: 총 골드

    Returns:
        참가자별 보상 {user_id: {"exp": int, "gold": int}}
    """
    from models import User

    rewards = {}

    # 총 기여도 계산
    total_contribution = sum(session.contribution.values())
    if total_contribution == 0:
        logger.warning("Total contribution is 0, using equal distribution")
        total_contribution = len(session.contribution)
        for user_id in session.contribution:
            session.contribution[user_id] = 1

    # 각 참가자에게 보상 분배
    for user_id, contrib in session.contribution.items():
        # 기본 보상 (기여도 비례)
        share = contrib / total_contribution
        base_exp = int(total_exp * share)
        base_gold = int(total_gold * share)

        # 캐리 방지 패널티 적용
        if user_id == session.user_id:
            # 파티 리더는 패널티 없음
            final_exp = base_exp
            final_gold = base_gold
        else:
            # 난입자는 레벨 차이에 따라 패널티
            participant = session.participants.get(user_id)
            if participant:
                penalty = get_carry_penalty_multiplier(
                    participant.level,
                    session.user.level
                )
                final_exp = int(base_exp * penalty)
                final_gold = int(base_gold * penalty)
            else:
                # 참가자 정보 없으면 정상 지급
                final_exp = base_exp
                final_gold = base_gold

        # 최소 보상 보장 (기여도가 5% 이상이면)
        if share >= 0.05:
            final_exp = max(final_exp, 1)
            final_gold = max(final_gold, 1)

        # 보상 지급
        try:
            # User 엔티티 가져오기
            if user_id == session.user_id:
                user = session.user
            else:
                user = session.participants.get(user_id)

            if not user:
                user = await User.get_or_none(discord_id=user_id)

            if user:
                # 경험치 및 골드 추가
                user.exp += final_exp
                user.gold += final_gold
                await user.save()

                rewards[user_id] = {"exp": final_exp, "gold": final_gold}

                logger.info(
                    f"Reward distributed: user={user_id}, "
                    f"exp={final_exp}, gold={final_gold}, share={share:.2%}"
                )
            else:
                logger.warning(f"User not found for reward distribution: {user_id}")
        except Exception as e:
            logger.error(f"Failed to distribute reward to {user_id}: {e}")

    return rewards
