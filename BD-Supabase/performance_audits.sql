CREATE TABLE performance_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    batch_id TEXT,
    url TEXT,
    fcp_ms INT,
    lcp_ms INT,
    peso_mb FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
