---

### 📄 Archivo 2: `DATABASE_SCHEMA.md` (Especificación de la Base de Datos)

```markdown
# QAVision — Especificación del Modelo de Datos (Supabase / PostgreSQL)

Este documento define la estructura rígida de las tablas en la base de datos de Supabase. Cualquier mutación sobre los modelos debe actualizarse aquí de manera obligatoria.

## 🔑 Estructura de Control Común
Todas las tablas implementan de forma mandatoria tres columnas de control:
- `id`: Identificador único autorregulado (`UUID PRIMARY KEY`).
- `user_id`: Identificador de sesión provisto por Supabase Auth (`TEXT`).
- `batch_id`: Identificador alfanumérico generado en frontend para agrupar ejecuciones en paralelo de la suite masiva (`TEXT`). Permite valores `NULL` si la prueba fue unitaria.

---

## 📊 Tablas Especializadas

### 1. `pruebas_qa` (Módulo Regresión Visual - VRT)
Almacena métricas de diferencias de píxeles capturados por el motor visual.
- `id` (UUID, PK, Default: `gen_random_uuid()`)
- `user_id` (TEXT, NOT NULL)
- `batch_id` (TEXT)
- `url_a` (TEXT) -> URL del entorno de Staging/Candidato.
- `url_b` (TEXT) -> URL del entorno de Producción/Base.
- `diferencias` (INT) -> Sumatoria de píxeles con discrepancia.
- `img_a_url` (TEXT) -> URL de la captura en Staging.
- `img_b_url` (TEXT) -> URL de la captura en Producción.
- `img_diff_url` (TEXT) -> URL de la máscara de diferencias generada.
- `creado_el` (TIMESTAMP WITH TIME ZONE, Default: `NOW()`)

### 2. `seo_audits` (Módulo SEO & Accesibilidad)
Persiste los datos de parsing estructural y auditoría del DOM.
- `id` (UUID, PK)
- `user_id` (TEXT, NOT NULL)
- `batch_id` (TEXT)
- `url` (TEXT)
- `title` (TEXT) -> Etiqueta Title encontrada.
- `title_len` (INT) -> Longitud de caracteres del título.
- `description` (TEXT) -> Meta descripción de la página.
- `desc_len` (INT)
- `h1_count` (INT) -> Cantidad de etiquetas H1 en el documento.
- `h1_text` (TEXT)
- `canonical` (TEXT) -> URL declarada en la etiqueta canonical.
- `robots` (TEXT)
- `imgs_sin_alt` (INT) -> Imágenes críticas que rompen la regla de accesibilidad (sin ALT).
- `total_imgs` (INT)
- `inputs_sin_label` (INT) -> Elementos Input huérfanos de etiquetas legibles.
- `botones_sin_etiqueta` (INT) -> Botones interactivos sin texto interno ni aria-label.
- `created_at` (TIMESTAMP WITH TIME ZONE, Default: `NOW()`)

### 3. `performance_audits` (Módulo Core Web Vitals)
Registra tiempos y métricas críticas de carga del navegador controladas por Playwright.
- `id` (UUID, PK)
- `user_id` (TEXT, NOT NULL)
- `batch_id` (TEXT)
- `url` (TEXT)
- `fcp_ms` (INT) -> Tiempos del First Contentful Paint.
- `lcp_ms` (INT) -> Tiempos del Largest Contentful Paint.
- `peso_mb` (FLOAT) -> Volumen total de datos transferidos por red.
- `created_at` (TIMESTAMP WITH TIME ZONE, Default: `NOW()`)

### 4. `auditoria_links` (Módulo Enlaces Rotos e Interactividad)
- `id` (UUID, PK)
- `user_id` (TEXT, NOT NULL)
- `batch_id` (TEXT)
- `url_auditada` (TEXT)
- `reporte` (JSONB) -> Estructura de tipo Array que contiene objetos serializados bajo el estricto contrato: `[{"url": "string", "obstruido": boolean}]`.
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT: NOW())
