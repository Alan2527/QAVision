# QAVision — Omni-Suite Automated Testing Manager

QAVision es un ecosistema avanzado de automatización y auditoría de calidad de software (QA) diseñado para ejecutar pruebas concurrentes y masivas sobre plataformas web. El sistema unifica cuatro módulos críticos de control bajo una única interfaz unificada, permitiendo aislar regresiones visuales, anomalías estructurales de SEO/Accesibilidad, degradaciones de rendimiento y enlaces rotos u obstruidos.

## 🚀 Arquitectura del Sistema

El ecosistema está desacoplado bajo una arquitectura cliente-servidor orientada a alta disponibilidad:

- **Frontend (Consola de Operaciones):** Interfaz estática de alta densidad optimizada en Pixel-Perfect Dark Mode. Construida con HTML5 nativo, Tailwind CSS (v3 via CDN), JavaScript asíncrono puro (Vanilla JS) y visualizaciones dinámicas mediante Chart.js.
- **Backend (Motor de Inferencia):** API REST asíncrona construida sobre FastAPI (Python 3.10+) y desplegada en Hugging Face Spaces. Utiliza Playwright Async para la manipulación e introspección del DOM de forma headless.
- **Capa de Persistencia:** Supabase (PostgreSQL) con control de sesiones asíncronas de usuarios y almacenamiento de payloads estructurados.

## 📂 Estructura del Repositorio

```microservices
├── app.py                        # Motor Backend (FastAPI + Playwright en Hugging Face)
├── requirements.txt              # Dependencias del servidor de ejecución Python
├── dashboard.html                # Panel de Control Central y Suite Manager Individual
├── mass_execution.html           # Explorador y Monitor de Ejecuciones Masivas (Batches)
├── visual_regression.html        # Dashboard Especializado: Regresión Visual (VRT)
├── seo.html                      # Dashboard Especializado: SEO Estructural & Accesibilidad
├── performance.html              # Dashboard Especializado: Core Web Vitals (Performance)
├── interaction_audit.html        # Dashboard Especializado: Interactividad y Enlaces Rotos
└── README.md                     # Documentación Maestra del Proyecto
