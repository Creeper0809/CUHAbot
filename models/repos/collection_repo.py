"""
UserCollection Repository

유저 도감 데이터 접근 레이어입니다.
"""
from typing import List, Optional

from models import User
from models.user_collection import UserCollection, CollectionType


async def get_user_collections(
    user: User,
    collection_type: Optional[CollectionType] = None
) -> List[UserCollection]:
    """
    유저 도감 조회

    Args:
        user: 대상 유저
        collection_type: 필터할 타입 (None이면 전체)

    Returns:
        UserCollection 목록
    """
    query = UserCollection.filter(user=user)
    if collection_type:
        query = query.filter(collection_type=collection_type)
    return await query.order_by("first_obtained_at")


async def has_collection(
    user: User,
    collection_type: CollectionType,
    target_id: int
) -> bool:
    """
    특정 항목이 도감에 등록되어 있는지 확인

    Args:
        user: 대상 유저
        collection_type: 타입
        target_id: 대상 ID

    Returns:
        등록 여부
    """
    return await UserCollection.filter(
        user=user,
        collection_type=collection_type,
        target_id=target_id
    ).exists()


async def add_collection(
    user: User,
    collection_type: CollectionType,
    target_id: int
) -> tuple[UserCollection, bool]:
    """
    도감에 항목 추가

    Args:
        user: 대상 유저
        collection_type: 타입
        target_id: 대상 ID

    Returns:
        (UserCollection 객체, 새로 추가되었는지 여부)
    """
    collection, created = await UserCollection.get_or_create(
        user=user,
        collection_type=collection_type,
        target_id=target_id
    )
    return collection, created


async def get_collection_count(
    user: User,
    collection_type: Optional[CollectionType] = None
) -> int:
    """
    도감 등록 수 조회

    Args:
        user: 대상 유저
        collection_type: 필터할 타입 (None이면 전체)

    Returns:
        등록된 항목 수
    """
    query = UserCollection.filter(user=user)
    if collection_type:
        query = query.filter(collection_type=collection_type)
    return await query.count()


async def get_collected_ids(
    user: User,
    collection_type: CollectionType
) -> List[int]:
    """
    특정 타입의 수집된 ID 목록 조회

    Args:
        user: 대상 유저
        collection_type: 타입

    Returns:
        수집된 target_id 목록
    """
    collections = await UserCollection.filter(
        user=user,
        collection_type=collection_type
    ).values_list("target_id", flat=True)
    return list(collections)
