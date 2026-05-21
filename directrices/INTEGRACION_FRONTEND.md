# QAVision — Mapeo de Integración y Reglas del Inspector Dinámico (Drawer)

Este documento detalla cómo interactúan las vistas globales con las bases de datos especializadas y cómo se debe comportar la UI.

## 1. Regla de Normalización en Consultas Paralelas (`Promise.all`)
Dado que cada módulo maneja campos de URL y fechas con nombres diferentes debido a su diseño independiente, el frontend en `mass_execution.html` debe realizar un mapeo explícito e inyectar de manera artificial propiedades estandarizadas para el listado principal, sin alterar el resto de las propiedades originales que serán consumidas por el panel de inspección.

Mapeo de nombres nativos a nombres estándar de la lista:
- **VRT (`pruebas_qa`):** `url_m: item.url_a` | `fecha: item.creado_el`
- **SEO (`seo_audits`):** `url_m: item.url` | `fecha: item.created_at`
- **Performance (`performance_audits`):** `url_m: item.url` | `fecha: item.created_at`
- **Links (`auditoria_links`):** `url_m: item.url_auditada` | `fecha: item.created_at`

## 2. Espejado de Dashboards en el Panel de Detalles (`#detail-drawer`)
Al presionar "INSPECT" o hacer foco en un registro del listado masivo, el contenedor `#drawer-dynamic-content` DEBE mutar estructuralmente para convertirse en una ventana espejo que copie de manera exacta los componentes visuales de sus dashboards individuales correspondientes. Está prohibido inyectar bloques genéricos de texto o volcados de JSON crudos.

### Contratos de Renderizado Obligatorios:

#### A. Si `modulo === 'vrt'`
Debe simular el reporte visual de `visual_regression.html`:
- Debe renderizar una card de clase `bg-tech` conteniendo la imagen `img_diff_url`.
- Debe exponer un contador con la clase dinámica correspondiente (`text-red-500` si `diferencias > 0`, de lo contrario `text-emerald-500`).

#### B. Si `modulo === 'seo'`
Debe simular el checklist y las hileras de auditoría de `seo.html`:
- Utiliza la estructura de contenedor de filas de clase `.check-row`.
- Cada fila debe contener un elemento `<span class="badge">` acompañado de las clases semánticas CSS `.status-error` y `.error` si los contadores (`imgs_sin_alt`, `inputs_sin_label`) son mayores a cero, o `.status-ok` y `.ok` si el resultado es limpio.

#### C. Si `modulo === 'perf'`
Debe simular el velocímetro / anillo de puntuación de `performance.html`:
- Debe calcular un Score simulado: Si `fcp_ms < 2500` y `lcp_ms < 2500`, hereda puntuación óptima con el anillo circular CSS perimetral pintado con la clase `border-emerald-500`. En caso de penalización de tiempos, transmuta inmediatamente a `border-red-500`.
- Las métricas individuales se exponen alineadas a la derecha aplicando las clases tipográficas `.good` o `.poor`.

#### D. Si `modulo === 'links'`
Debe simular la grilla relacional de `interaction_audit.html`:
- Debe deserializar de forma segura la columna `reporte` (manejando tanto strings JSON como objetos nativos parseados).
- Genera un mapeo interactivo iterando el array, donde cada hilera expone la URL del link y un badge rígido con las clases de estado exactas: `.status-ok` (`LIBRE`) o `.status-error` (`OBSTRUIDO`), heredando los fondos con transparencias (`rgba`) configurados en la hoja de estilos global.

## 3. Control de Estado del Drawer
- El Drawer se despliega removiendo la clase de Tailwind `translate-x-full`.
- El botón de cierre (`✕ CERRAR`) debe tener asignada de manera mandatoria e inline la función global `cerrarDrawer()`, la cual reintroduce la clase `translate-x-full` para asegurar la correcta ejecución del flujo de la interfaz sin depender de capturas de eventos flotantes que puedan quedar bloqueadas por la actualización asíncrona del DOM.
