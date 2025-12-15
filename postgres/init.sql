-- PostgreSQL Initialization Script for ABEKM
-- Extensions: pgvector, pg_trgm, textsearch_ko, kor_search

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS textsearch_ko;

-- kor_search extension (may fail if not properly installed, but we'll try)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS kor_search;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'kor_search extension not available, skipping...';
END
$$;

-- Set default text search configuration to Korean (Mecab-based)
ALTER DATABASE wkms SET default_text_search_config = 'public.korean';

-- Create custom text search configuration if needed
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'korean'
    ) THEN
        -- If korean config doesn't exist, create it
        CREATE TEXT SEARCH CONFIGURATION public.korean ( COPY = pg_catalog.simple );
    END IF;
END
$$;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'ABEKM PostgreSQL initialized successfully';
    RAISE NOTICE 'Extensions: vector, pg_trgm, textsearch_ko';
    RAISE NOTICE 'Default text search: public.korean (Mecab)';
    RAISE NOTICE '==============================================';
END
$$;
