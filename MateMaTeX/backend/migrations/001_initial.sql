-- ============================================================================
-- MateMaTeX 2.0 — Supabase Migration 001: Initial Schema
-- ============================================================================
-- Run in Supabase SQL Editor.
-- Prerequisites: Supabase project with Auth enabled.
-- ============================================================================

-- Extensions
create extension if not exists vector;
create extension if not exists pg_trgm;

-- ============================================================================
-- HELPER: Auto-update updated_at
-- ============================================================================
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ============================================================================
-- SCHOOLS (optional grouping for collaboration)
-- ============================================================================
create table schools (
    id              uuid default gen_random_uuid() primary key,
    name            text not null,
    domain          text default '',
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create trigger schools_updated_at before update on schools
    for each row execute function update_updated_at();

-- ============================================================================
-- PROFILES (extends auth.users — auto-created on signup)
-- ============================================================================
create table public.profiles (
    id                      uuid references auth.users on delete cascade primary key,
    full_name               text default '',
    school_id               uuid references schools(id) on delete set null,
    default_grade           text default '10. trinn',
    default_language_level  text default 'standard',
    preferred_model         text default 'gemini-2.0-flash',
    onboarding_completed    boolean default false,
    avatar_url              text default '',
    created_at              timestamptz default now(),
    updated_at              timestamptz default now()
);

create trigger profiles_updated_at before update on profiles
    for each row execute function update_updated_at();

-- Auto-create profile on auth signup
create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', ''));
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- ============================================================================
-- FOLDERS (hierarchical organization)
-- ============================================================================
create table folders (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,
    parent_id       uuid references folders(id) on delete cascade,

    name            text not null,
    color           text default '#3b82f6',
    icon            text default '📁',
    sort_order      int not null default 0,

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index idx_folders_user on folders (user_id);
create index idx_folders_parent on folders (parent_id);

create trigger folders_updated_at before update on folders
    for each row execute function update_updated_at();

-- ============================================================================
-- GENERATIONS
-- ============================================================================
create table generations (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,

    -- Request
    grade           text not null,
    topic           text not null,
    material_type   text not null default 'arbeidsark',
    language_level  text not null default 'standard',
    difficulty      text not null default 'Middels',
    num_exercises   int not null default 10,
    extra_instructions text default '',
    content_options jsonb not null default '{}',

    -- Output
    latex_body      text not null default '',
    full_document   text not null default '',
    pdf_url         text default '',
    word_url        text default '',

    -- Pipeline metadata
    pipeline_job_id text default '',
    pipeline_steps  jsonb not null default '[]',
    total_tokens    int not null default 0,
    total_duration  real not null default 0.0,
    math_verified   boolean not null default false,
    math_claims_checked int default 0,
    math_claims_correct int default 0,
    latex_compiled  boolean not null default false,

    -- Organization
    folder_id       uuid references folders(id) on delete set null,
    is_favorite     boolean not null default false,
    is_pinned       boolean not null default false,
    rating          int check (rating between 1 and 5),

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index idx_generations_user on generations (user_id);
create index idx_generations_topic on generations (topic);
create index idx_generations_grade on generations (grade);
create index idx_generations_created on generations (created_at desc);

create trigger generations_updated_at before update on generations
    for each row execute function update_updated_at();

-- ============================================================================
-- EXERCISES
-- ============================================================================
create table exercises (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,
    generation_id   uuid references generations(id) on delete set null,
    source_generation_id uuid references generations(id) on delete set null,

    title           text not null default 'Oppgave',
    topic           text not null default '',
    grade_level     text not null default '',
    difficulty      text not null default 'middels' check (difficulty in ('lett', 'middels', 'vanskelig')),
    exercise_type   text not null default 'standard',

    latex_content   text not null,
    solution        text default '',
    hints           jsonb not null default '[]',
    keywords        text[] default '{}',

    -- Semantic search
    embedding       vector(768),

    -- Metadata
    competency_goals text[] default '{}',
    source          text default 'generated' check (source in ('generated', 'manual', 'imported')),
    use_count       int not null default 0,
    times_used      int not null default 0,
    user_rating     int check (user_rating between 1 and 5),

    -- Sub-structure
    has_figure      boolean not null default false,
    sub_parts       text[] default '{}',
    content_hash    text default '',

    -- School publishing
    is_published    boolean not null default false,
    school_id       uuid references schools(id) on delete set null,

    -- Soft delete
    deleted_at      timestamptz default null,

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index idx_exercises_user on exercises (user_id);
create index idx_exercises_topic on exercises (topic);
create index idx_exercises_difficulty on exercises (difficulty);
create index idx_exercises_school on exercises (school_id) where is_published = true;
create index idx_exercises_embedding on exercises using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index idx_exercises_deleted on exercises (deleted_at) where deleted_at is null;

create trigger exercises_updated_at before update on exercises
    for each row execute function update_updated_at();

-- ============================================================================
-- TEMPLATES
-- ============================================================================
create table templates (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,

    name            text not null,
    description     text default '',
    config          jsonb not null default '{}',
    is_public       boolean not null default false,
    use_count       int not null default 0,

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index idx_templates_user on templates (user_id);
create index idx_templates_public on templates (is_public) where is_public = true;

create trigger templates_updated_at before update on templates
    for each row execute function update_updated_at();

-- ============================================================================
-- TAGS
-- ============================================================================
create table tags (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,
    name            text not null,
    color           text default '#6366f1',
    created_at      timestamptz default now(),
    unique (user_id, name)
);

create index idx_tags_user on tags (user_id);

create table generation_tags (
    generation_id   uuid not null references generations(id) on delete cascade,
    tag_id          uuid not null references tags(id) on delete cascade,
    primary key (generation_id, tag_id)
);

create table exercise_tags (
    exercise_id     uuid not null references exercises(id) on delete cascade,
    tag_id          uuid not null references tags(id) on delete cascade,
    primary key (exercise_id, tag_id)
);

-- ============================================================================
-- SHARED LINKS
-- ============================================================================
create table shared_links (
    id              uuid default gen_random_uuid() primary key,
    generation_id   uuid not null references generations(id) on delete cascade,
    created_by      uuid not null references auth.users(id) on delete cascade,

    token           text unique not null default encode(gen_random_bytes(16), 'hex'),
    password_hash   text default null,
    expires_at      timestamptz default null,
    max_views       int default null,
    view_count      int not null default 0,
    allow_download  boolean not null default true,
    allow_edit      boolean not null default false,

    created_at      timestamptz default now()
);

create index idx_shared_links_token on shared_links (token);
create index idx_shared_links_generation on shared_links (generation_id);

-- ============================================================================
-- COMMENTS
-- ============================================================================
create table comments (
    id              uuid default gen_random_uuid() primary key,
    generation_id   uuid not null references generations(id) on delete cascade,
    user_id         uuid not null references auth.users(id) on delete cascade,

    content         text not null,
    parent_id       uuid references comments(id) on delete cascade,

    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index idx_comments_generation on comments (generation_id);

create trigger comments_updated_at before update on comments
    for each row execute function update_updated_at();

-- ============================================================================
-- DOCUMENT VERSIONS
-- ============================================================================
create table document_versions (
    id              uuid default gen_random_uuid() primary key,
    generation_id   uuid not null references generations(id) on delete cascade,
    version_number  int not null,
    latex_body      text not null,
    change_summary  text default '',
    created_by      uuid not null references auth.users(id) on delete cascade,
    created_at      timestamptz default now(),
    unique (generation_id, version_number)
);

create index idx_versions_generation on document_versions (generation_id);

-- ============================================================================
-- USAGE STATS
-- ============================================================================
create table usage_stats (
    id              uuid default gen_random_uuid() primary key,
    user_id         uuid not null references auth.users(id) on delete cascade,
    event_type      text not null,
    metadata        jsonb not null default '{}',
    created_at      timestamptz default now()
);

create index idx_usage_user on usage_stats (user_id);
create index idx_usage_type on usage_stats (event_type);
create index idx_usage_date on usage_stats (created_at);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================
alter table profiles enable row level security;
alter table schools enable row level security;
alter table folders enable row level security;
alter table generations enable row level security;
alter table exercises enable row level security;
alter table templates enable row level security;
alter table tags enable row level security;
alter table generation_tags enable row level security;
alter table exercise_tags enable row level security;
alter table shared_links enable row level security;
alter table comments enable row level security;
alter table document_versions enable row level security;
alter table usage_stats enable row level security;

-- Profiles
create policy "Users read own profile" on profiles for select using (auth.uid() = id);
create policy "Users update own profile" on profiles for update using (auth.uid() = id);

-- Schools (read-only for members)
create policy "School members read school" on schools for select
    using (id in (select school_id from profiles where id = auth.uid()));

-- Folders
create policy "Users manage own folders" on folders for all using (auth.uid() = user_id);

-- Generations
create policy "Users see own generations" on generations for select using (auth.uid() = user_id);
create policy "Users insert own generations" on generations for insert with check (auth.uid() = user_id);
create policy "Users update own generations" on generations for update using (auth.uid() = user_id);
create policy "Users delete own generations" on generations for delete using (auth.uid() = user_id);

-- Exercises
create policy "Users see own exercises" on exercises for select
    using (auth.uid() = user_id and deleted_at is null);
create policy "Users see school exercises" on exercises for select
    using (
        is_published = true
        and school_id = (select school_id from profiles where id = auth.uid())
        and deleted_at is null
    );
create policy "Users insert own exercises" on exercises for insert with check (auth.uid() = user_id);
create policy "Users update own exercises" on exercises for update using (auth.uid() = user_id);
create policy "Users soft-delete own exercises" on exercises for delete using (auth.uid() = user_id);

-- Templates
create policy "Users manage own templates" on templates for all
    using (auth.uid() = user_id or is_public = true);
create policy "Users insert own templates" on templates for insert with check (auth.uid() = user_id);

-- Tags
create policy "Users manage own tags" on tags for all using (auth.uid() = user_id);

-- Tag junctions
create policy "Users manage own generation_tags" on generation_tags for all
    using (generation_id in (select id from generations where user_id = auth.uid()));
create policy "Users manage own exercise_tags" on exercise_tags for all
    using (exercise_id in (select id from exercises where user_id = auth.uid()));

-- Shared links
create policy "Owners manage shared links" on shared_links for all using (auth.uid() = created_by);
-- Public read via token (handled in app layer, not RLS)

-- Comments
create policy "Users see comments on own generations" on comments for select
    using (generation_id in (select id from generations where user_id = auth.uid()));
create policy "Users add comments" on comments for insert with check (auth.uid() = user_id);
create policy "Users update own comments" on comments for update using (auth.uid() = user_id);
create policy "Users delete own comments" on comments for delete using (auth.uid() = user_id);

-- Document versions
create policy "Users see own generation versions" on document_versions for all
    using (generation_id in (select id from generations where user_id = auth.uid()));

-- Usage stats
create policy "Users see own stats" on usage_stats for select using (auth.uid() = user_id);
create policy "Users insert own stats" on usage_stats for insert with check (auth.uid() = user_id);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Semantic search
create or replace function search_exercises(
    query_embedding vector(768),
    match_count int default 5,
    match_threshold float default 0.7
)
returns table (
    id uuid,
    title text,
    topic text,
    difficulty text,
    similarity float
) as $$
begin
    return query
    select
        e.id,
        e.title,
        e.topic,
        e.difficulty,
        1 - (e.embedding <=> query_embedding) as similarity
    from exercises e
    where 1 - (e.embedding <=> query_embedding) > match_threshold
      and e.deleted_at is null
    order by e.embedding <=> query_embedding
    limit match_count;
end;
$$ language plpgsql;
