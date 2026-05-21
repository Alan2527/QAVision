CREATE TABLE auditoria_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    batch_id TEXT,
    url_auditada TEXT,
    reporte JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
