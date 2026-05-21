# QAVision — Contexto de Arquitectura y Reglas del Sistema

Este documento define las reglas de oro arquitectónicas y de diseño del ecosistema QAVision. Cualquier modificación de código generada por la IA DEBE respetar estas directrices sin excepción.

## 1. Stack Tecnológico General
- **Backend:** FastAPI (Python 3.10+) ejecutado en Hugging Face Spaces. Utiliza Playwright Async para automatización de scraping y auditorías.
- **Base de Datos:** Supabase (PostgreSQL) con consultas asíncronas vía REST Client de JavaScript en frontend y `supabase-py` en backend.
- **Frontend:** Single Page / HTML estáticos puros potenciados con Tailwind CSS (CDN), Google Fonts (Inter, DM Sans, Syne) y Chart.js. No se utilizan frameworks reactivos (React/Vue/Angular).

## 2. Reglas Estrictas de Diseño Visual (Pixel-Perfect Dark)
El diseño del sistema responde a una estética cyberpunk minimalista y oscura de alta densidad de información. No se permiten mutaciones de colores arbitrarias.
- **Fondo Principal (Surface):** `#000000` (Negro absoluto).
- **Tarjetas Técnicas (Cards/Panels):** `#050505` con borde rígido de `1px solid #111827` (o `#1a1a1a` según el módulo). Clase Tailwind común: `bg-tech`.
- **Código de Colores de Estado Semántico:**
  - **Éxito / Libre / Pasó:** `#10b981` (Emerald-500) -> Clases: `.ok`, `.status-ok`, `.good`
  - **Advertencia:** `#f59e0b` (Amber-500) -> Clases: `.warn`
  - **Error / Obstruido / Falló:** `#ef4444` (Red-500) -> Clases: `.error`, `.status-error`, `.poor`
- **Tipografías:**
  - Títulos principales e isotipos: `'Syne'`, sans-serif (con pesos pesados / black e itálicas).
  - Texto e interfaz interactiva: `'Inter'` o `'DM Sans'`, sans-serif.
  - Datos numéricos y logs técnicos: `'DM Mono'`, monospace.

## 3. Directiva de Ejecuciones Masivas (Batches)
- El panel `mass_execution.html` actúa exclusivamente como un monitor de lotes (Batches). 
- **REGLA DE ORO:** Bajo ningún concepto se deben mostrar ejecuciones individuales en este panel. Toda consulta orientada a este módulo debe incluir de forma obligatoria el filtro `.not('batch_id', 'is', null)`.
- El frontend genera un identificador único alfanumérico mediante `crypto.randomUUID()` llamado `batch_id` en el momento de hacer clic en "Ejecutar Suite Completa". Este ID se propaga a través de los payloads JSON hacia la API de Python y se almacena de forma mandatoria en la base de datos para agrupar las ejecuciones en paralelo.
