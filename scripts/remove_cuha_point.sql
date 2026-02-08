-- Remove cuha_point column from users table
-- 실행 방법: psql -U postgres -d postgres -f scripts/remove_cuha_point.sql

BEGIN;

-- cuha_point 컬럼 삭제 (gold 컬럼으로 통합됨)
ALTER TABLE users DROP COLUMN IF EXISTS cuha_point;

COMMIT;

SELECT 'cuha_point column removed successfully' AS status;
