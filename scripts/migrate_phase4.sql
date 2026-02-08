-- Phase 4 Migration Script
-- 실행 방법: psql -U [username] -d [database] -f scripts/migrate_phase4.sql

-- ============================================================================
-- 4A.1: 장비 레벨 제한
-- ============================================================================
ALTER TABLE equipment_item
ADD COLUMN IF NOT EXISTS require_level INTEGER DEFAULT 1;

COMMENT ON COLUMN equipment_item.require_level IS '장착 요구 레벨';

-- ============================================================================
-- 4A.4: 소모품 확장 (버프, 정화, 투척)
-- ============================================================================
ALTER TABLE consume_item
ADD COLUMN IF NOT EXISTS buff_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS buff_amount INTEGER,
ADD COLUMN IF NOT EXISTS buff_duration INTEGER,
ADD COLUMN IF NOT EXISTS cleanse_debuff BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS throwable_damage INTEGER;

COMMENT ON COLUMN consume_item.buff_type IS '버프 타입 (attack, defense, speed 등)';
COMMENT ON COLUMN consume_item.buff_amount IS '버프 수치';
COMMENT ON COLUMN consume_item.buff_duration IS '버프 지속 턴';
COMMENT ON COLUMN consume_item.cleanse_debuff IS '디버프 정화 여부';
COMMENT ON COLUMN consume_item.throwable_damage IS '투척 데미지 (전투 중 사용 가능)';

-- ============================================================================
-- 4B.1: 세트 아이템 시스템
-- ============================================================================

-- 세트 정의 테이블
CREATE TABLE IF NOT EXISTS set_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

COMMENT ON TABLE set_items IS '세트 아이템 정의 (드래곤 세트, 화염 세트 등)';

-- 세트 구성원 테이블 (어떤 장비가 어떤 세트에 속하는지)
CREATE TABLE IF NOT EXISTS set_item_members (
    id SERIAL PRIMARY KEY,
    set_item_id INTEGER NOT NULL REFERENCES set_items(id) ON DELETE CASCADE,
    equipment_item_id INTEGER NOT NULL REFERENCES equipment_item(id) ON DELETE CASCADE,
    UNIQUE(set_item_id, equipment_item_id)
);

COMMENT ON TABLE set_item_members IS '세트 구성원 (장비-세트 연결)';

-- 세트 효과 테이블
CREATE TABLE IF NOT EXISTS set_effects (
    id SERIAL PRIMARY KEY,
    set_item_id INTEGER NOT NULL REFERENCES set_items(id) ON DELETE CASCADE,
    pieces_required INTEGER NOT NULL,
    effect_description TEXT NOT NULL,
    effect_config JSONB NOT NULL,
    UNIQUE(set_item_id, pieces_required)
);

COMMENT ON TABLE set_effects IS '세트 효과 (2/3/4/5/6/8개 착용 시 보너스)';

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_set_members_set ON set_item_members(set_item_id);
CREATE INDEX IF NOT EXISTS idx_set_members_equipment ON set_item_members(equipment_item_id);
CREATE INDEX IF NOT EXISTS idx_set_effects_set ON set_effects(set_item_id);

-- ============================================================================
-- 완료 확인
-- ============================================================================
SELECT 'Migration completed successfully!' AS status;
