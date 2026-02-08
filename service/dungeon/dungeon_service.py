"""
던전 서비스 - 엔트리 포인트

실제 구현은 하위 모듈에 분리되어 있습니다:
- dungeon_loop.py: 메인 루프, 클리어/사망/귀환
- encounter_processor.py: 인카운터 처리, 몬스터 스폰
- combat_executor.py: 전투 실행, 행동 게이지
- reward_calculator.py: 보상 계산, 몬스터 타입 판별
- drop_handler.py: 아이템/스킬 드롭
- dungeon_ui.py: 전투/던전 임베드 생성
"""
from service.dungeon.dungeon_loop import start_dungeon

__all__ = ["start_dungeon"]
