-- PostgreSQL Initialization Script for ABEKM
-- Extensions: pgvector, pg_trgm, textsearch_ko (Mecab), kor_search
-- Purpose: Multi-language (Korean + English) full-text search support

-- ============================================================
-- 1. Enable Required Extensions
-- ============================================================

-- pgvector: Vector similarity search for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_trgm: Trigram-based similarity search (useful for fuzzy matching)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- textsearch_ko: Korean morphological analysis (Mecab-based)
CREATE EXTENSION IF NOT EXISTS textsearch_ko;

-- kor_search: Korean-English synonym mapping and multilingual search
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS kor_search;
    RAISE NOTICE '✅ kor_search extension installed successfully';
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING '⚠️  kor_search extension not available: %', SQLERRM;
END
$$;

-- ============================================================
-- 2. Configure Text Search for Multilingual Support
-- ============================================================

-- Set default text search configuration to Korean (Mecab-based)
-- This applies to all text search operations in the database
ALTER DATABASE wkms SET default_text_search_config = 'public.korean';

-- Create multilingual text search configuration
-- This combines Korean morphological analysis with English stemming
DO $$
BEGIN
    -- Create Korean configuration (Mecab parser)
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'korean') THEN
        CREATE TEXT SEARCH CONFIGURATION public.korean (PARSER = mecabko);
        
        -- Map Korean morphemes to search tokens
        ALTER TEXT SEARCH CONFIGURATION public.korean
            ADD MAPPING FOR
                -- Content words (meaningful for search)
                NNG,      -- General noun
                NNP,      -- Proper noun
                NNB,      -- Dependent noun
                VV,       -- Verb
                VA,       -- Adjective
                MAG,      -- General adverb
                SL        -- Foreign word (English in Korean text)
            WITH korean_stem;
        
        -- Map other token types to 'simple' (no processing)
        ALTER TEXT SEARCH CONFIGURATION public.korean
            ADD MAPPING FOR
                XR,       -- Root
                IC,       -- Interjection
                MM,       -- Determiner
                MAJ,      -- Conjunctive adverb
                XSN, XSV, XSA  -- Suffix for nouns/verbs/adjectives
            WITH simple;
        
        RAISE NOTICE '✅ Korean text search configuration created (Mecab parser)';
    ELSE
        RAISE NOTICE '✅ Korean text search configuration already exists';
    END IF;
    
    -- Create English configuration for English-only documents
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'english_custom') THEN
        CREATE TEXT SEARCH CONFIGURATION public.english_custom (COPY = pg_catalog.english);
        RAISE NOTICE '✅ English text search configuration created';
    ELSE
        RAISE NOTICE '✅ English text search configuration already exists';
    END IF;
END
$$;

-- ============================================================
-- 3. Initialize kor_search Synonym Tables (if extension exists)
-- ============================================================

DO $$
BEGIN
    -- Check if kor_search is installed
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'kor_search') THEN
        
        -- Create or verify synonym tables
        -- kor_search_word_transform: Korean <-> English mappings
        -- kor_search_word_synonyms: Synonym groups
        
        -- Example: Add common tech terms (can be expanded via backend)
        -- INSERT INTO kor_search_word_transform (ko, en) VALUES
        --   ('삼성전자', 'samsung electronics'),
        --   ('엘지전자', 'lg electronics')
        -- ON CONFLICT DO NOTHING;
        
        RAISE NOTICE '✅ kor_search tables ready for synonym configuration';
    ELSE
        RAISE NOTICE 'ℹ️  kor_search not available, skipping synonym initialization';
    END IF;
END
$$;

-- ============================================================
-- 4. Create Helper Functions for Multilingual Search
-- ============================================================

-- Function: Detect if text contains Korean characters
CREATE OR REPLACE FUNCTION has_korean(text_input TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if text contains Hangul syllables (U+AC00 to U+D7AF)
    RETURN text_input ~ '[가-힣]';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function: Smart text search query builder
-- Automatically selects Korean or English configuration based on input
CREATE OR REPLACE FUNCTION smart_tsquery(query_text TEXT)
RETURNS tsquery AS $$
BEGIN
    IF has_korean(query_text) THEN
        -- Use Korean configuration for queries with Korean characters
        RETURN plainto_tsquery('korean', query_text);
    ELSE
        -- Use English configuration for English-only queries
        RETURN plainto_tsquery('english_custom', query_text);
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function: Multilingual tsvector generation
-- Combines both Korean and English indexing for mixed-language text
CREATE OR REPLACE FUNCTION multilang_tsvector(text_input TEXT)
RETURNS tsvector AS $$
DECLARE
    result tsvector;
BEGIN
    IF text_input IS NULL OR text_input = '' THEN
        RETURN ''::tsvector;
    END IF;
    
    -- Always index with Korean parser (handles both Korean and English)
    result := to_tsvector('korean', text_input);
    
    -- If text contains English, also index with English parser for better stemming
    IF text_input ~ '[a-zA-Z]{3,}' THEN
        result := result || to_tsvector('english_custom', text_input);
    END IF;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- 5. Verification and Logging
-- ============================================================

DO $$
DECLARE
    ext_count INTEGER;
    config_count INTEGER;
BEGIN
    -- Count installed extensions
    SELECT COUNT(*) INTO ext_count
    FROM pg_extension
    WHERE extname IN ('vector', 'pg_trgm', 'textsearch_ko', 'kor_search');
    
    -- Count text search configurations
    SELECT COUNT(*) INTO config_count
    FROM pg_ts_config
    WHERE cfgname IN ('korean', 'english_custom');
    
    RAISE NOTICE '==============================================';
    RAISE NOTICE '✅ ABEKM PostgreSQL Initialized Successfully';
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'Extensions installed: % / 4', ext_count;
    RAISE NOTICE '  - pgvector: Vector similarity search';
    RAISE NOTICE '  - pg_trgm: Trigram fuzzy matching';
    RAISE NOTICE '  - textsearch_ko: Korean morphological analysis (Mecab)';
    RAISE NOTICE '  - kor_search: Korean-English synonym mapping';
    RAISE NOTICE '';
    RAISE NOTICE 'Text search configurations: % / 2', config_count;
    RAISE NOTICE '  - korean: Mecab-based Korean parser';
    RAISE NOTICE '  - english_custom: English stemming';
    RAISE NOTICE '';
    RAISE NOTICE 'Helper functions created:';
    RAISE NOTICE '  - has_korean(text): Detect Korean characters';
    RAISE NOTICE '  - smart_tsquery(text): Auto-select parser';
    RAISE NOTICE '  - multilang_tsvector(text): Multilingual indexing';
    RAISE NOTICE '';
    RAISE NOTICE 'Default text search config: public.korean';
    RAISE NOTICE 'Ready for multilingual (Korean + English) search!';
    RAISE NOTICE '==============================================';
END
$$;
