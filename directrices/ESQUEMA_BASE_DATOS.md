# QAVision — Esquema Oficial de Base de Datos (Supabase)

Las IA no deben asumir nombres de columnas. A continuación se detallan las cuatro tablas especializadas del motor de pruebas. Todas las tablas contienen llaves foráneas implícitas de control: `id` (UUID como llave primaria), `user_id` (TEXT, mapeado con la autenticación de Supabase) y `batch_id` (TEXT, para agrupación de suites masivas).

### 1. Tabla: `pruebas_qa` (Módulo Regresión Visual - VRT)
Almacena capturas de layouts y diferencias de píxeles entre entornos.
- `id` (UUID, PK)
- `user_id` (TEXT)
- `batch_id` (TEXT)
- `url_a` (TEXT) -> Destino Staging / Candidato.
- `url_b` (TEXT) -> Destino Producción / Base de comparación.
- `diferencias` (INT) -> Cantidad de píxeles anómalos encontrados.
- `img_a_url` (TEXT)
- `img_b_url` (TEXT)
- `img_diff_url` (TEXT) -> Imagen resultante con el mapa de calor del diff.
- `creado_el` (TIMESTAMP WITH TIME ZONE, DEFAULT: NOW())

### 2. Tabla: `seo_audits` (Módulo SEO & Accesibilidad)
Guarda metadata estructural extraída mediante parsing DOM adaptado.
- `id` (UUID, PK)
- `user_id` (TEXT)
- `batch_id` (TEXT)
- `url` (TEXT)
- `title` (TEXT)
- `title_len` (INT)
- `description` (TEXT)
- `desc_len` (INT)
- `h1_count` (INT)
- `h1_text` (TEXT)
- `canonical` (TEXT)
- `robots` (TEXT)
- `imgs_sin_alt` (INT) -> Contador de imágenes críticas sin atributo alternativo.
- `total_imgs` (INT)
- `inputs_sin_label` (INT) -> Campos de formulario huérfanos de etiquetas.
- `botones_sin_etiqueta` (INT) -> Botones sin texto interno ni aria-label.
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT: NOW())

### 3. Tabla: `performance_audits` (Módulo Core Web Vitals)
Métricas de rendimiento e interactividad de carga de página.
- `id` (UUID, PK)
- `user_id` (TEXT)
- `batch_id` (TEXT)
- `url` (TEXT)
- `fcp_ms` (INT) -> First Contentful Paint en milisegundos.
- `lcp_ms` (INT) -> Largest Contentful Paint en milisegundos.
- `peso_mb` (FLOAT) -> Peso consolidado de la transferencia de red en Megabytes.
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT: NOW())

### 4. Tabla: `auditoria_links` (Módulo Interaction & Enlaces Rotos)
Estructura relacional compleja para verificación de respuestas de hipervínculos.
- `id` (UUID, PK)
- `user_id` (TEXT)
- `batch_id` (TEXT)
- `url_auditada` (TEXT)
- `reporte` (JSONB) -> Array estructurado de objetos. Cada objeto interno responde estrictamente a la estructura: `{"url": "string", "obstruido": boolean}`.
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT: NOW())
