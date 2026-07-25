-- Supabase PostgreSQL Schema for AI-Based Smart Event Photo Retrieval System

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_name TEXT NOT NULL,
    date TEXT NOT NULL,
    venue TEXT NOT NULL,
    description TEXT,
    qr_code_path TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS images (
    image_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events (event_id) ON DELETE CASCADE,
    image_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    upload_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS faces (
    face_id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES images (image_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES events (event_id) ON DELETE CASCADE,
    embedding JSONB, -- Not strictly required for Face++ since Face++ stores faces via FaceSet, but keeping for compatibility if needed. Actually we'll store face_token from Face++ here!
    face_token TEXT, -- Token returned by Face++
    bounding_box JSONB NOT NULL,
    confidence REAL NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_logs (
    search_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events (event_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    matched_images_count INTEGER NOT NULL,
    processing_time_ms REAL NOT NULL
);
