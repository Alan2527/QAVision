CREATE TABLE pruebas_qa (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    batch_id TEXT,
    url_a TEXT,
    url_b TEXT,
    diferencias INT,
    img_a_url TEXT,
    img_b_url TEXT,
    img_diff_url TEXT,
    creado_el TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
