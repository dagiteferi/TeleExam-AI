CREATE TABLE IF NOT EXISTS departments (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT REFERENCES departments(id) ON DELETE CASCADE,
    course_name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    topic_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id BIGSERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    difficulty TEXT DEFAULT 'Medium',
    topic_id BIGINT REFERENCES topics(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS exams (
    id BIGSERIAL PRIMARY KEY,
    year INT NOT NULL,
    semester TEXT NOT NULL,
    course_id BIGINT REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_questions (
    exam_id BIGINT REFERENCES exams(id) ON DELETE CASCADE,
    question_id BIGINT REFERENCES questions(id) ON DELETE CASCADE,
    PRIMARY KEY (exam_id, question_id)
);


CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    pro_status BOOLEAN DEFAULT false,
    invited_by UUID,
    invites_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    exam_id BIGINT REFERENCES exams(id) ON DELETE SET NULL,
    current_index INT DEFAULT 0,
    answers JSONB DEFAULT '[]'::jsonb,
    mode TEXT NOT NULL,
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '2 hours'
);

CREATE TABLE IF NOT EXISTS results (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    exam_id BIGINT,
    score INT,
    total_questions INT,
    weak_topics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE results ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;


ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_questions ENABLE ROW LEVEL SECURITY;


CREATE POLICY "users_access_own_data" ON users
    FOR ALL USING (telegram_id = current_setting('app.current_telegram_id')::bigint);

CREATE POLICY "user_sessions_access_own" ON user_sessions
    FOR ALL USING (user_id = (SELECT id FROM users WHERE telegram_id = current_setting('app.current_telegram_id')::bigint));

CREATE POLICY "results_access_own" ON results
    FOR ALL USING (user_id = (SELECT id FROM users WHERE telegram_id = current_setting('app.current_telegram_id')::bigint));

CREATE POLICY "activity_log_access_own" ON activity_log
    FOR ALL USING (user_id = (SELECT id FROM users WHERE telegram_id = current_setting('app.current_telegram_id')::bigint));


CREATE POLICY "static_content_read" ON departments FOR SELECT USING (true);
CREATE POLICY "static_content_read" ON courses FOR SELECT USING (true);
CREATE POLICY "static_content_read" ON topics FOR SELECT USING (true);
CREATE POLICY "static_content_read" ON questions FOR SELECT USING (true);
CREATE POLICY "static_content_read" ON exams FOR SELECT USING (true);
CREATE POLICY "static_content_read" ON exam_questions FOR SELECT USING (true);


CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_results_user_id ON results(user_id);
CREATE INDEX idx_questions_topic_id ON questions(topic_id);