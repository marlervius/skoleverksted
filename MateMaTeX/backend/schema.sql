-- ============================================================================
-- MateMaTeX 2.0 — PostgreSQL Database Schema
-- ============================================================================
-- Designed for Supabase/Neon with Row Level Security (RLS).
-- Supports: users, generations, exercises, templates, folders, tags, sharing.
-- ============================================================================

-- Enable pgvector for semantic search on exercises
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS
-- ============================================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    school          TEXT DEFAULT '',
    role            TEXT NOT NULL DEFAULT 'teacher' CHECK (role IN ('teacher', 'admin', 'student')),
    avatar_url      TEXT DEFAULT '',
    preferences     JSONB NOT NULL DEFAULT '{}',
    -- Preferences includes: default_grade, default_language_level, theme, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);

-- ============================================================================
-- GENERATIONS (all AI-generated output with full metadata)
-- ============================================================================
CREATE TABLE generations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Request
    grade           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    material_type   TEXT NOT NULL DEFAULT 'arbeidsark',
    language_level  TEXT NOT NULL DEFAULT 'standard',
    difficulty      TEXT NOT NULL DEFAULT 'Middels',
    num_exercises   INT NOT NULL DEFAULT 10,
    extra_instructions TEXT DEFAULT '',
    content_options JSONB NOT NULL DEFAULT '{}',

    -- Output
    latex_body      TEXT NOT NULL DEFAULT '',
    full_document   TEXT NOT NULL DEFAULT '',
    pdf_url         TEXT DEFAULT '',
    word_url        TEXT DEFAULT '',

    -- Pipeline metadata
    pipeline_job_id TEXT DEFAULT '',
    pipeline_steps  JSONB NOT NULL DEFAULT '[]',
    total_tokens    INT NOT NULL DEFAULT 0,
    total_duration  REAL NOT NULL DEFAULT 0.0,
    math_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    math_claims_checked INT DEFAULT 0,
    math_claims_correct INT DEFAULT 0,
    latex_compiled  BOOLEAN NOT NULL DEFAULT FALSE,

    -- Organization
    folder_id       UUID REFERENCES folders(id) ON DELETE SET NULL,
    is_favorite     BOOLEAN NOT NULL DEFAULT FALSE,
    is_pinned       BOOLEAN NOT NULL DEFAULT FALSE,
    rating          INT CHECK (rating BETWEEN 1 AND 5),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generations_user ON generations (user_id);
CREATE INDEX idx_generations_topic ON generations (topic);
CREATE INDEX idx_generations_grade ON generations (grade);
CREATE INDEX idx_generations_created ON generations (created_at DESC);

-- ============================================================================
-- EXERCISES (atomic, reusable exercises with embedding vectors)
-- ============================================================================
CREATE TABLE exercises (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id   UUID REFERENCES generations(id) ON DELETE SET NULL,
    source_generation_id UUID REFERENCES generations(id) ON DELETE SET NULL,

    title           TEXT NOT NULL DEFAULT 'Oppgave',
    topic           TEXT NOT NULL,
    grade_level     TEXT NOT NULL,
    difficulty      TEXT NOT NULL DEFAULT 'middels' CHECK (difficulty IN ('lett', 'middels', 'vanskelig')),
    exercise_type   TEXT NOT NULL DEFAULT 'standard',

    latex_content   TEXT NOT NULL,
    solution        TEXT DEFAULT '',
    hints           JSONB NOT NULL DEFAULT '[]',
    keywords        TEXT[] DEFAULT '{}',

    -- Semantic search vector (768 dimensions for text-embedding-3-small)
    embedding       vector(768),

    -- Metadata
    competency_goals TEXT[] DEFAULT '{}',
    source          TEXT DEFAULT 'generated' CHECK (source IN ('generated', 'manual', 'imported')),
    use_count       INT NOT NULL DEFAULT 0,
    times_used      INT NOT NULL DEFAULT 0,
    user_rating     INT CHECK (user_rating BETWEEN 1 AND 5),

    -- Sub-structure
    has_figure      BOOLEAN NOT NULL DEFAULT FALSE,
    sub_parts       TEXT[] DEFAULT '{}',
    content_hash    TEXT DEFAULT '',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exercises_user ON exercises (user_id);
CREATE INDEX idx_exercises_topic ON exercises (topic);
CREATE INDEX idx_exercises_difficulty ON exercises (difficulty);
CREATE INDEX idx_exercises_embedding ON exercises USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- TEMPLATES (custom generation presets)
-- ============================================================================
CREATE TABLE templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    config          JSONB NOT NULL DEFAULT '{}',
    -- config includes: material_type, include_theory, num_exercises, etc.

    is_public       BOOLEAN NOT NULL DEFAULT FALSE,
    use_count       INT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_templates_user ON templates (user_id);
CREATE INDEX idx_templates_public ON templates (is_public) WHERE is_public = TRUE;

-- ============================================================================
-- FOLDERS (hierarchical organization)
-- ============================================================================
CREATE TABLE folders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES folders(id) ON DELETE CASCADE,

    name            TEXT NOT NULL,
    color           TEXT DEFAULT '#3b82f6',
    icon            TEXT DEFAULT '📁',
    sort_order      INT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_folders_user ON folders (user_id);
CREATE INDEX idx_folders_parent ON folders (parent_id);

-- ============================================================================
-- TAGS
-- ============================================================================
CREATE TABLE tags (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name            TEXT NOT NULL,
    color           TEXT DEFAULT '#6366f1',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, name)
);

CREATE INDEX idx_tags_user ON tags (user_id);

-- Junction table: generations ↔ tags
CREATE TABLE generation_tags (
    generation_id   UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    tag_id          UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (generation_id, tag_id)
);

-- Junction table: exercises ↔ tags
CREATE TABLE exercise_tags (
    exercise_id     UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    tag_id          UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (exercise_id, tag_id)
);

-- ============================================================================
-- SHARED LINKS (collaboration)
-- ============================================================================
CREATE TABLE shared_links (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_id   UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    created_by      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    token           TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(16), 'hex'),
    password_hash   TEXT DEFAULT NULL,  -- NULL = no password
    expires_at      TIMESTAMPTZ DEFAULT NULL,  -- NULL = never expires
    max_views       INT DEFAULT NULL,  -- NULL = unlimited
    view_count      INT NOT NULL DEFAULT 0,
    allow_download  BOOLEAN NOT NULL DEFAULT TRUE,
    allow_edit      BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shared_links_token ON shared_links (token);
CREATE INDEX idx_shared_links_generation ON shared_links (generation_id);

-- Comments on shared documents
CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_id   UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    content         TEXT NOT NULL,
    parent_id       UUID REFERENCES comments(id) ON DELETE CASCADE,  -- For threading

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_generation ON comments (generation_id);

-- ============================================================================
-- DOCUMENT VERSIONS (version history)
-- ============================================================================
CREATE TABLE document_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_id   UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,

    version_number  INT NOT NULL,
    latex_body      TEXT NOT NULL,
    change_summary  TEXT DEFAULT '',
    created_by      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (generation_id, version_number)
);

CREATE INDEX idx_versions_generation ON document_versions (generation_id);

-- ============================================================================
-- USAGE STATS (for dashboard)
-- ============================================================================
CREATE TABLE usage_stats (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    event_type      TEXT NOT NULL, -- 'generation', 'download', 'share', etc.
    metadata        JSONB NOT NULL DEFAULT '{}',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_user ON usage_stats (user_id);
CREATE INDEX idx_usage_type ON usage_stats (event_type);
CREATE INDEX idx_usage_date ON usage_stats (created_at);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_stats ENABLE ROW LEVEL SECURITY;

-- Users can only see/edit their own data
CREATE POLICY user_self ON users FOR ALL USING (id = auth.uid());
CREATE POLICY generation_owner ON generations FOR ALL USING (user_id = auth.uid());
CREATE POLICY exercise_owner ON exercises FOR ALL USING (user_id = auth.uid());
CREATE POLICY template_owner ON templates FOR ALL USING (user_id = auth.uid() OR is_public = TRUE);
CREATE POLICY folder_owner ON folders FOR ALL USING (user_id = auth.uid());
CREATE POLICY tag_owner ON tags FOR ALL USING (user_id = auth.uid());
CREATE POLICY shared_link_owner ON shared_links FOR ALL USING (created_by = auth.uid());
CREATE POLICY comment_owner ON comments FOR ALL USING (user_id = auth.uid());
CREATE POLICY version_access ON document_versions FOR ALL
    USING (generation_id IN (SELECT id FROM generations WHERE user_id = auth.uid()));
CREATE POLICY usage_owner ON usage_stats FOR ALL USING (user_id = auth.uid());

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER generations_updated_at BEFORE UPDATE ON generations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER exercises_updated_at BEFORE UPDATE ON exercises
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER templates_updated_at BEFORE UPDATE ON templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Semantic search function for exercises
CREATE OR REPLACE FUNCTION search_exercises(
    query_embedding vector(768),
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    topic TEXT,
    difficulty TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.title,
        e.topic,
        e.difficulty,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM exercises e
    WHERE 1 - (e.embedding <=> query_embedding) > match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
