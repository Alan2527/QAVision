# QAVision — Estándares de Frontend y Patrón "Mirror View"

Para garantizar la consistencia visual y de usabilidad del sistema, el diseño del frontend debe respetar estrictamente las pautas establecidas.

## 1. Patrón "Mirror View" (Espejo de Componentes)
El explorador masivo (`mass_execution.html`) procesa los registros concurrentes utilizando llamadas asíncronas paralelas mediante `Promise.all`. Cuando un analista hace clic en el botón de inspección de un lote, el panel lateral desplegable (`#detail-drawer`) **DEBE transmutar su interfaz** para comportarse como un espejo exacto del dashboard especializado de ese test.

### Reglas de Diseño de Componentes dentro del Drawer:

1. **VRT (Regresión Visual):** Debe emular a `visual_regression.html`. Muestra la card de comparación conteniendo exclusivamente la imagen del diff (`img_diff_url`), acompañada de un contador dinámico que hereda las clases `.text-red-500` (con errores) o `.text-green-500` (perfect match).
2. **SEO & Accesibilidad:** Debe emular a `seo.html`. Utiliza de forma mandatoria la estructura de bloques `.check-row`. Los indicadores de estado utilizan las clases CSS nativas `.status-error` / `.error` e Inyectan etiquetas legibles (OK / ERROR) basadas en los contadores numéricos de la base de datos.
3. **Core Web Vitals:** Debe emular a `performance.html`. Renderiza el anillo circular perimetral central (`#score-circle`). Si los tiempos de `fcp_ms` y `lcp_ms` se encuentran por debajo del umbral de penalización (< 2500ms), el perímetro se tiñe usando la clase `border-emerald-500` y calcula una puntuación óptima (Score: 90). De lo contrario, conmuta a `border-red-500`.
4. **Interaction Audit:** Debe emular a `interaction_audit.html`. Parsea de forma segura el payload binario o string de la columna `reporte`, generando una tabla interactiva donde cada hilera expone de forma clara si el link se encuentra `LIBRE` (Pintado con la clase `.status-ok`) o `OBSTRUIDO` (Pintado con la clase `.status-error`).

## 2. Gestión Segura del Ciclo de Vida del Drawer
Para evitar bloqueos e inconsistencias visuales provocadas por renderizados parciales en JavaScript:
- El despliegue del panel lateral se ejecuta removiendo la clase posicional de Tailwind `translate-x-full`.
- El botón de cierre (`✕ CLOSE`) debe llamar explícitamente y de manera inline a la función globalizada `cerrarDrawer()`. Esta función inyecta nuevamente la clase `translate-x-full` en el DOM, garantizando un flujo limpio y una tasa de respuesta del 100% ante eventos del ratón.
