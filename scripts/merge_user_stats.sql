-- Merge user_stats into users table
-- 실행 방법: psql -U postgres -d postgres -f scripts/merge_user_stats.sql

BEGIN;

-- 1. users 테이블에 user_stats 필드 추가
ALTER TABLE users
ADD COLUMN IF NOT EXISTS bonus_hp INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_attack INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_ap_attack INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_ad_defense INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_ap_defense INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_speed INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS accuracy INTEGER DEFAULT 90,
ADD COLUMN IF NOT EXISTS evasion INTEGER DEFAULT 5,
ADD COLUMN IF NOT EXISTS critical_rate INTEGER DEFAULT 5,
ADD COLUMN IF NOT EXISTS critical_damage INTEGER DEFAULT 150,
ADD COLUMN IF NOT EXISTS gold BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_attendance DATE,
ADD COLUMN IF NOT EXISTS attendance_streak INTEGER DEFAULT 0;

-- 2. user_stats 데이터를 users로 이관
UPDATE users u
SET
    bonus_hp = COALESCE(s.bonus_hp, 0),
    bonus_attack = COALESCE(s.bonus_attack, 0),
    bonus_ap_attack = COALESCE(s.bonus_ap_attack, 0),
    bonus_ad_defense = COALESCE(s.bonus_ad_defense, 0),
    bonus_ap_defense = COALESCE(s.bonus_ap_defense, 0),
    bonus_speed = COALESCE(s.bonus_speed, 0),
    accuracy = COALESCE(s.accuracy, 90),
    evasion = COALESCE(s.evasion, 5),
    critical_rate = COALESCE(s.critical_rate, 5),
    critical_damage = COALESCE(s.critical_damage, 150),
    gold = COALESCE(s.gold, 0),
    last_attendance = s.last_attendance,
    attendance_streak = COALESCE(s.attendance_streak, 0),
    -- experience와 exp 통합 (user_stats.experience 우선)
    exp = COALESCE(s.experience, u.exp),
    -- stat_points 통합 (user_stats.stat_points 우선)
    stat_points = COALESCE(s.stat_points, u.stat_points)
FROM user_stats s
WHERE u.id = s.user_id;

-- 3. user_stats 테이블 삭제
DROP TABLE IF EXISTS user_stats CASCADE;

COMMIT;

SELECT 'Migration completed: user_stats merged into users' AS status;
