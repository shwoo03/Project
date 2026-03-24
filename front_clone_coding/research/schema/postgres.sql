-- Future migration only.
-- Do not make normal local knowledge capture depend on PostgreSQL.
-- Promote to DB-backed storage only after the file-first workflow is no longer enough.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_sources (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_url TEXT,
  authors JSONB NOT NULL DEFAULT '[]'::jsonb,
  published_at DATE,
  topics JSONB NOT NULL DEFAULT '[]'::jsonb,
  summary TEXT NOT NULL DEFAULT '',
  implementation_hooks JSONB NOT NULL DEFAULT '[]'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_sections (
  id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
  section_label TEXT NOT NULL,
  content TEXT NOT NULL,
  content_embedding VECTOR(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS code_modules (
  id UUID PRIMARY KEY,
  module_ref TEXT NOT NULL UNIQUE,
  area TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learning_notes (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT 'design-note',
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  module_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  next_action TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS code_links (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL,
  learning_note_id UUID REFERENCES learning_notes(id) ON DELETE SET NULL,
  module_id UUID NOT NULL REFERENCES code_modules(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'draft',
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS experiments (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  hypothesis TEXT NOT NULL,
  dataset TEXT NOT NULL DEFAULT '',
  decision TEXT NOT NULL DEFAULT 'planned',
  metric_before JSONB NOT NULL DEFAULT '{}'::jsonb,
  metric_after JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT NOT NULL DEFAULT '',
  module_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_links JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_sources_source_type
  ON knowledge_sources (source_type);

CREATE INDEX IF NOT EXISTS idx_learning_notes_evidence
  ON learning_notes (evidence);

CREATE INDEX IF NOT EXISTS idx_code_modules_module_ref
  ON code_modules (module_ref);

CREATE INDEX IF NOT EXISTS idx_experiments_decision
  ON experiments (decision);

CREATE INDEX IF NOT EXISTS idx_source_sections_source_id
  ON source_sections (source_id);
