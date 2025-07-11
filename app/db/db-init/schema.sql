-- 房間表
CREATE TABLE IF NOT EXISTS rooms (
    room_id VARCHAR(10) PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 使用者表
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- BOSS 類型配置表
CREATE TABLE IF NOT EXISTS boss_types (
    boss_name VARCHAR(50) PRIMARY KEY,
    min_respawn_minutes INTEGER NOT NULL,
    max_respawn_minutes INTEGER NOT NULL,
    description TEXT
);

-- BOSS 記錄表
CREATE TABLE IF NOT EXISTS boss_records (
    id BIGSERIAL PRIMARY KEY,
    room_id VARCHAR(10) NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    channel INTEGER NOT NULL CHECK (channel >= 1),
    boss_name VARCHAR(50) NOT NULL REFERENCES boss_types(boss_name),
    status VARCHAR(20) NOT NULL CHECK (status IN ('alive', 'killed', 'not_found')),
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    respawn_min_time TIMESTAMPTZ,
    respawn_max_time TIMESTAMPTZ,
    recorder_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    recorder_info JSONB
);

-- 房間活動用戶表
CREATE TABLE IF NOT EXISTS room_users (
    id BIGSERIAL PRIMARY KEY,
    room_id VARCHAR(10) NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    anonymous_session_id VARCHAR(100),
    joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_or_anonymous CHECK (user_id IS NOT NULL OR anonymous_session_id IS NOT NULL),
    UNIQUE (room_id, user_id),
    UNIQUE (room_id, anonymous_session_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_boss_records_recorder_id ON boss_records(recorder_id);
CREATE INDEX IF NOT EXISTS idx_boss_records_room_channel ON boss_records(room_id, channel);
CREATE INDEX IF NOT EXISTS idx_boss_records_room_boss ON boss_records(room_id, boss_name);
CREATE INDEX IF NOT EXISTS idx_boss_records_time ON boss_records(recorded_at);
CREATE INDEX IF NOT EXISTS idx_room_users_room_id ON room_users(room_id);
CREATE INDEX IF NOT EXISTS idx_room_users_user_id ON room_users(user_id);

-- 預設 BOSS 類型
INSERT INTO boss_types (boss_name, min_respawn_minutes, max_respawn_minutes, description) VALUES
('雪毛怪人', 45, 68, '冰原雪域'),
('黑輪王',780 , 1020, '西門町'),
('巴洛古', 405, 540, '維多利亞島'),
('肯得熊', 113, 128, '桃花仙境'),
('喵怪仙人', 150, 170, '桃花仙境'),
('仙人娃娃', 158, 180, '桃花仙境'),
('巨大深山人蔘', 60, 135, '桃花仙境'),
('九尾妖狐', 210, 570, '童話村'),
('書生幽靈', 150, 300, '童話村'),
('殭屍蘑菇王', 195, 225, '維多利亞島'),
('蘑菇王', 210, 240, '維多利亞島'),
('葛雷金剛', 270, 350, '地球防衛總部'),
('咕咕鐘', 68, 90, '玩具城'),
('艾利傑', 118, 128, '天空之城'),
('冥界幽靈', 45, 60, '維多利亞島'),
('沼澤巨鱷', 90, 105, '維多利亞島'),
('殭屍猴王', 38, 45, '維多利亞島'),
('樹妖王', 23, 30, '維多利亞島'),
('巨居蟹', 45, 60, '黃金海岸'),
('雪山魔女', 158, 180, '冰原雪域'),
('厄運死神', 45, 105, '冰原雪域'),
('紅寶王', 23, 30, '維多利亞島')
ON CONFLICT (boss_name) DO NOTHING;