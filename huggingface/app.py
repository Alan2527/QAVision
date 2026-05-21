from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
import asyncio
import traceback
from supabase import create_client, Client

app = FastAPI()

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = "https://xdufdcwvaxvcdcjgdvvt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhkdWZkY3d2YXh2Y2RjamdkdnZ0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODY1MTgyNywiZXhwIjoyMDk0MjI3ODI3fQ.wnWOCbnheZLpXeXpgLBsCnvHvsbDXW8I73UJZdIpRsM"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- MODELOS ---
class URLsParaComparar(BaseModel):
    url_a: str  # Staging
    url_b: str  # Producción
    user_id: str = None
    batch_id: str = None

class URLParaAuditar(BaseModel):
    url: str
    max_elementos: int = 50  # Configurable desde el frontend, máximo 200
    tipos: list[str] = ["a", "button", "role_button", "input_submit", "onclick"]
    # tipos disponibles: "a", "button", "role_button", "role_link", "input_submit", "onclick"
    user_id: str = None
    batch_id: str = None

# --- UTILITARIO PARA LIMPIAR URLs ---
def asegurar_http(url: str) -> str:
    """Agrega https:// si el usuario olvidó poner el protocolo."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url

# --- 1. FUNCIÓN GLOBAL DE LIMPIEZA DE EMERGENTES ---
async def limpiar_interfaz(page):
    """
    Elimina obstáculos visuales por COMPORTAMIENTO, no por selectores específicos.
    Detecta modales/overlays por z-index alto + posición fija, sin depender de clases
    o IDs de ningún proveedor en particular (OneTrust, Didomi, etc.).
    """
    await page.evaluate("""() => {
        // Detectar overlays por comportamiento: position fixed/absolute + z-index alto + cubre pantalla
        document.querySelectorAll('*').forEach(el => {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const zIndex = parseInt(s.zIndex) || 0;
            const esFijo = s.position === 'fixed' || s.position === 'absolute' || s.position === 'sticky';
            const cubrePantalla = r.width > window.innerWidth * 0.3 && r.height > 50;
            const esVisible = s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';

            // Si tiene z-index alto, es fijo, cubre una porción de pantalla y es visible → es un obstáculo
            if (esFijo && zIndex > 100 && cubrePantalla && esVisible) {
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
                el.style.setProperty('opacity', '0', 'important');
                el.style.setProperty('pointer-events', 'none', 'important');
            }
        });

        // Rehabilitar scroll — algunos modales lo bloquean en body/html
        document.body.style.setProperty('overflow', 'auto', 'important');
        document.documentElement.style.setProperty('overflow', 'auto', 'important');
    }""")

# --- 2. FUNCIÓN DE SCROLL PROGRESIVO PARA LAZY LOADING ---
async def ejecutar_scroll_completo(page):
    """Fuerza la carga de todas las imágenes antes de la captura."""
    try:
        await page.evaluate("""async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 100;
                let timer = setInterval(() => {
                    let scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass  # Si la página navegó durante el scroll, continuar igual
    # Espera inteligente: aguarda que la red se calme, pero con timeout corto.
    # Si los trackers la mantienen activa (TN, MercadoLibre, etc.), continúa después de 8s sin colgar.
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass  # Timeout esperado en sitios con trackers — continuamos igual

    await asyncio.sleep(1)  # Buffer mínimo para el renderizado visual final


# --- 3. BLOQUEO DE RECURSOS INNECESARIOS PARA VRT ---
async def bloquear_recursos_innecesarios(page):
    """
    Bloquea trackers, ads y analytics ANTES de navegar.
    Objetivo: que networkidle llegue rápido y la página cargue limpia para VRT.
    Lo que importa son los divs, contenedores y estilos del DOM — no los ads.
    """
    # Solo bloqueamos trackers puros (no visuales) — las ad networks visuales
    # se permiten para que los contenedores carguen y el layout sea fiel al original.
    # El CSS de marcar_ads_bloqueados se encarga de enmascarar su contenido.
    dominios_bloqueados = [
        "google-analytics.com", "googletagmanager.com", "googletagservices.com",
        "scorecardresearch.com", "chartbeat.com", "facebook.net",
        "hotjar.com", "segment.com", "mixpanel.com", "amplitude.com",
        "newrelic.com", "datadog-browser-agent.com", "clarity.ms"
    ]

    async def interceptar(route):
        if any(dominio in route.request.url for dominio in dominios_bloqueados):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", interceptar)


# --- ESTILOS DE PLACEHOLDER PARA ADS BLOQUEADOS ---
# Selectores globales basados en atributos estándar de la industria publicitaria,
# sin hardcodear nombres de proveedores específicos.
AD_PLACEHOLDER_CSS = """
    /* Estándar IAB: ins.adsbygoogle, elementos con data-ad-* */
    ins.adsbygoogle,
    [data-ad-slot], [data-ad-unit], [data-ad-client],
    [data-ad], [data-ads], [data-advertisement],
    /* Contenedores GPT estándar (Google Publisher Tags) */
    [id^="div-gpt-ad"], [id^="google_ads_iframe"],
    /* iframes de terceros cargados como ads (src con parámetros publicitarios estándar) */
    iframe[src*="/ads/"], iframe[src*="ad_type="], iframe[src*="adunit"],
    iframe[src*="banner"], iframe[src*="sponsore"] {
        background: repeating-linear-gradient(
            45deg, #0f172a, #0f172a 10px, #1e293b 10px, #1e293b 20px
        ) !important;
        border: 1px dashed #374151 !important;
        overflow: hidden !important;
        position: relative !important;
        /* NO tocamos width/height — respetamos el espacio original del layout */
    }
    /* Texto indicador */
    ins.adsbygoogle::after, [data-ad-slot]::after,
    [id^="div-gpt-ad"]::after {
        content: "[ AD ]" !important;
        color: #4b5563 !important;
        font-size: 10px !important;
        font-family: monospace !important;
        letter-spacing: 1px !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        pointer-events: none !important;
    }
    /* Colapsar iframes completamente vacíos */
    iframe:not([src]), iframe[src=""], iframe[src="about:blank"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
"""

async def marcar_ads_bloqueados(page):
    """
    Enmascara los contenedores de ads con patrón rayado, respetando su tamaño original.
    Así el layout de la captura es fiel al sitio real.
    """
    await page.add_style_tag(content=AD_PLACEHOLDER_CSS)

# --- 4. MÓDULO VRT QUIRÚRGICO ---
# Recibe páginas ya navegadas y listas, y los paths únicos generados por el endpoint.
async def ejecutar_vrt_quirurgico(page_staging, page_prod, staging_path, diff_path):
    """
    Recibe páginas ya navegadas y listas. Extrae el ADN del DOM,
    compara atributos y genera el reporte gráfico de diferencias.
    """
    img_original = Image.open(staging_path).convert("RGB")
    margen = 60
    ancho_nuevo = img_original.width + (margen * 2)
    alto_nuevo = img_original.height + (margen * 2)

    img_canvas = Image.new("RGB", (ancho_nuevo, alto_nuevo), (15, 23, 42))
    img_canvas.paste(img_original, (margen, margen))
    draw = ImageDraw.Draw(img_canvas)

    js_extract = """
    () => {
        return Array.from(document.querySelectorAll('*'))
            .filter(el => el.className && typeof el.className === 'string' && el.className.includes('qa-'))
            .map(el => {
                const s = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return {
                    className: el.className.split(' ').find(c => c.includes('qa-')),
                    tag: el.tagName,
                    text: el.innerText.trim(),
                    x: r.x, y: r.y, w: r.width, h: r.height,
                    color: s.color, bg: s.backgroundColor,
                    font: s.fontFamily, size: s.fontSize
                };
            });
    }
    """

    elementos_staging = await page_staging.evaluate(js_extract)
    elementos_prod = await page_prod.evaluate(js_extract)

    dict_prod = {item['className']: item for item in elementos_prod}
    dict_staging = {item['className']: item for item in elementos_staging}
    errores = 0

    # FASE 1: Producción vs Staging (Validaciones Detalladas)
    for pProd in elementos_prod:
        pStaging = dict_staging.get(pProd['className'])
        x_p = pProd['x'] + margen
        y_p = pProd['y'] + margen

        if not pStaging:
            draw.rectangle([x_p, y_p, x_p + pProd['w'], y_p + pProd['h']], outline="#ff3333", width=3)
            draw.text((x_p, y_p - 20), "MISSING", fill="#ff3333")
            errores += 1
        else:
            diffs = []
            es_contenedor = pProd['tag'] in ['FOOTER', 'MAIN', 'SECTION', 'NAV', 'DIV']

            if not es_contenedor and pStaging['text'] != pProd['text']: diffs.append("TXT-CHG")
            if pStaging['size'] != pProd['size']: diffs.append("FONT-SZ")
            if pStaging['color'] != pProd['color']: diffs.append("COLOR")
            if pStaging['bg'] != pProd['bg']: diffs.append("BG-COLOR")
            if pStaging['w'] != pProd['w'] or pStaging['h'] != pProd['h']: diffs.append("SIZE")
            if pStaging['x'] != pProd['x'] or pStaging['y'] != pProd['y']: diffs.append("POS")

            if diffs:
                draw.rectangle([x_p, y_p, x_p + pProd['w'], y_p + pProd['h']], outline="#ff3333", width=3)
                draw.text((x_p, y_p - 20), "/".join(diffs), fill="#ff3333")
                errores += 1

    # FASE 2: Elementos Nuevos en Staging
    for pStaging in elementos_staging:
        if pStaging['className'] not in dict_prod:
            x_s = pStaging['x'] + margen
            y_s = pStaging['y'] + margen
            draw.rectangle([x_s, y_s, x_s + pStaging['w'], y_s + pStaging['h']], outline="#33ff33", width=3)
            draw.text((x_s, y_s - 20), "NEW-ELEM", fill="#33ff33")
            errores += 1

    img_canvas.save(diff_path)
    return errores

# --- 5. ENDPOINT COMPARAR (VRT) ---
@app.post("/api/comparar")
async def api_comparar(datos: URLsParaComparar):
    id_p = str(uuid.uuid4())
    url_a_segura = asegurar_http(datos.url_a)
    url_b_segura = asegurar_http(datos.url_b)

    # MEJORA 1: paths temporales con UUID — evita colisiones si dos requests corren en paralelo
    path_a = f"/tmp/{id_p}_a.png"
    path_b = f"/tmp/{id_p}_b.png"
    path_d = f"/tmp/{id_p}_d.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})

            # FIX CRÍTICO: domcontentloaded en lugar de "load" para no colgar en sitios pesados
            page_staging = await context.new_page()
            await bloquear_recursos_innecesarios(page_staging)  # Bloquea trackers antes de navegar
            await page_staging.goto(url_a_segura, wait_until="domcontentloaded", timeout=90000)
            await marcar_ads_bloqueados(page_staging)  # Marca visualmente los espacios de ads
            await ejecutar_scroll_completo(page_staging)
            await limpiar_interfaz(page_staging)
            await page_staging.screenshot(path=path_a, full_page=True)

            # FIX CRÍTICO: domcontentloaded en lugar de "load"
            page_prod = await context.new_page()
            await bloquear_recursos_innecesarios(page_prod)  # Bloquea trackers antes de navegar
            await page_prod.goto(url_b_segura, wait_until="domcontentloaded", timeout=90000)
            await marcar_ads_bloqueados(page_prod)  # Marca visualmente los espacios de ads
            await ejecutar_scroll_completo(page_prod)
            await limpiar_interfaz(page_prod)
            await page_prod.screenshot(path=path_b, full_page=True)

            # Pasamos las páginas vivas a VRT — sin abrir un segundo browser
            cant = await ejecutar_vrt_quirurgico(page_staging, page_prod, path_a, path_d)

            await browser.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en motor VRT: {str(e)}")

    # MEJORA 2: subir_imagen es async — no bloquea el Event Loop
    u_a = await subir_imagen(path_a, f"{id_p}_a.png")
    u_b = await subir_imagen(path_b, f"{id_p}_b.png")
    u_d = await subir_imagen(path_d, f"{id_p}_d.png") if cant > 0 else None

    # MEJORA 3: timeout en Supabase — evita cuelgues si el servicio no responde
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                lambda: supabase.table("pruebas_qa").insert({
                    "url_a": url_a_segura,
                    "url_b": url_b_segura,
                    "diferencias": cant,
                    "img_a_url": str(u_a),
                    "img_b_url": str(u_b),
                    "img_diff_url": str(u_d) if u_d else None,
                    "user_id": datos.user_id,
                    "batch_id": datos.batch_id
                }).execute()
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Supabase no respondió al guardar el reporte VRT.")

    return {"status": "success", "diferencias": cant}

# --- 6. ENDPOINT AUDITAR LINKS ---
@app.post("/api/auditar-links")
async def api_auditar_links(datos: URLParaAuditar):
    url_segura = asegurar_http(datos.url)

    # MEJORA 1: path temporal con UUID
    id_a = str(uuid.uuid4())

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': 1280, 'height': 800})

            # FIX CRÍTICO: domcontentloaded en lugar de "load"
            await bloquear_recursos_innecesarios(page)  # Bloquea trackers antes de navegar
            await page.goto(url_segura, wait_until="domcontentloaded", timeout=90000)
            await marcar_ads_bloqueados(page)  # Marca visualmente los espacios de ads
            await ejecutar_scroll_completo(page)
            await limpiar_interfaz(page)

            # Construir selector dinámico según los tipos elegidos desde el frontend
            mapa_selectores = {
                "a":             "a",
                "button":        "button",
                "role_button":   "[role='button']",
                "role_link":     "[role='link']",
                "input_submit":  "input[type='submit']",
                "onclick":       "[onclick]",
            }
            partes = [mapa_selectores[t] for t in datos.tipos if t in mapa_selectores]
            selector = ", ".join(partes) if partes else "a, button, [role='button']"
            elementos = await page.query_selector_all(selector)

            # Aplicar límite configurable con cap de seguridad en 200
            limite = min(datos.max_elementos, 200)
            reporte = []
            for el in elementos[:limite]:
              try:
                texto = await el.inner_text()
                href = await el.get_attribute("href")

                # PASO 1: Detectar carrusel y activar slide — evaluate() es síncrono en Playwright,
                # los awaits deben estar en Python, no dentro del bloque JS.
                en_carrusel = await el.evaluate("""(node) => {
                    const buscarContenedor = (el) => {
                        let parent = el.parentElement;
                        while (parent && parent !== document.body) {
                            const s = window.getComputedStyle(parent);
                            if (s.overflowX === 'hidden' || s.overflowX === 'clip') {
                                const pr = parent.getBoundingClientRect();
                                const nr = el.getBoundingClientRect();
                                if (nr.right < pr.left || nr.left > pr.right) return parent;
                            }
                            parent = parent.parentElement;
                        }
                        return null;
                    };
                    const buscarBoton = (contenedor) => {
                        const palabras = ['next', 'siguiente', 'right', 'adelante', 'forward'];
                        const scope = contenedor.parentElement || contenedor;
                        const botones = Array.from(scope.querySelectorAll('button, [role="button"], [aria-label]'));
                        return botones.find(btn => {
                            const label = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
                            return palabras.some(p => label.includes(p));
                        }) || null;
                    };
                    const contenedor = buscarContenedor(node);
                    if (contenedor) {
                        const btn = buscarBoton(contenedor);
                        if (btn) {
                            // Solo clickear si es un button real, no un <a> que pueda navegar
                            const tag = btn.tagName.toLowerCase();
                            const href = btn.getAttribute('href');
                            if (tag === 'button' || (tag === 'a' && (!href || href === '#'))) {
                                btn.click();
                            } else {
                                // Fallback seguro: scroll directo
                                contenedor.scrollBy({ left: 300, behavior: 'instant' });
                            }
                        } else {
                            contenedor.scrollBy({ left: 300, behavior: 'instant' });
                        }
                        return true;
                    }
                    return false;
                }""")

                # PASO 2: scrollIntoView directo sobre el elemento.
                # Funciona para carruseles con scroll-snap, overflow oculto y scroll vertical.
                # El browser mueve exactamente lo necesario respetando el snap del contenedor.
                await el.evaluate("""(node) => {
                    node.scrollIntoView({ block: 'center', inline: 'center' });
                }""")
                # Esperar que la transición CSS termine (carrusel o scroll vertical)
                await asyncio.sleep(0.5)

                # PASO 2.5: Si el elemento está oculto y está en un carrusel,
                # navegar hacia adelante (máx 20 clicks) hasta que se active
                esta_oculto = await el.evaluate("""(node) => {
                    const s = window.getComputedStyle(node);
                    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return true;
                    const cls = (node.className && typeof node.className === 'string') ? node.className : '';
                    if (/\bhidden\b|\binvisible\b|\bdisabled\b/i.test(cls)) return true;
                    if (node.hasAttribute('disabled') || node.getAttribute('aria-hidden') === 'true') return true;
                    return false;
                }""")

                if esta_oculto:
                    # Intentar activar el elemento navegando el carrusel hacia adelante
                    activado = False
                    for _ in range(20):
                        # Buscar botón "siguiente" en el contexto del carrusel padre
                        clickeado = await el.evaluate("""(node) => {
                            const palabras = ['next', 'siguiente', 'right', 'adelante', 'forward'];
                            let parent = node.parentElement;
                            while (parent && parent !== document.body) {
                                const botones = Array.from(parent.querySelectorAll('button, [role="button"]'));
                                const btnNext = botones.find(b => {
                                    const label = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
                                    const cls = (b.className && typeof b.className === 'string') ? b.className : '';
                                    return palabras.some(p => label.includes(p) || cls.includes(p));
                                });
                                if (btnNext) { btnNext.click(); return true; }
                                parent = parent.parentElement;
                            }
                            return false;
                        }""")
                        if not clickeado:
                            break
                        await asyncio.sleep(0.3)
                        # Verificar si el elemento ya se activó
                        activado = await el.evaluate("""(node) => {
                            const s = window.getComputedStyle(node);
                            if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                            const cls = (node.className && typeof node.className === 'string') ? node.className : '';
                            if (/\bhidden\b|\binvisible\b/i.test(cls)) return false;
                            return true;
                        }""")
                        if activado:
                            await asyncio.sleep(0.3)  # Esperar que la transición termine
                            break

                    if not activado:
                        # No se pudo activar después de 20 clicks — saltar elemento
                        reporte.append({
                            "texto": texto.strip() or nombre if 'nombre' in dir() else "Sin texto",
                            "tipo": await el.evaluate("e => e.tagName"),
                            "href": href or "Acción JS",
                            "obstruido": False,
                            "motivo_obstruccion": None,
                            "status": 200,
                            "nota": "No evaluado — elemento no alcanzable en carrusel"
                        })
                        continue

                # PASO 3: Evaluar obstrucción con 5 puntos (síncrono, sin awaits en JS)
                obstruido = await el.evaluate("""(node) => {
                    const r = node.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) return true;

                    // Verificar que el elemento siga visible antes de evaluar
                    const s = window.getComputedStyle(node);
                    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                    const cls = (node.className && typeof node.className === 'string') ? node.className : '';
                    if (/\bhidden\b|\binvisible\b|\bdisabled\b/i.test(cls)) return false;
                    if (node.hasAttribute('disabled') || node.getAttribute('aria-hidden') === 'true') return false;

                    const cx = r.left + r.width / 2;
                    const cy = r.top + r.height / 2;

                    if (cx < 0 || cy < 0 || cx > window.innerWidth || cy > window.innerHeight) {
                        return false;
                    }

                    const puntos = [
                        [cx, cy],
                        [r.left + r.width * 0.25, r.top + r.height * 0.25],
                        [r.left + r.width * 0.75, r.top + r.height * 0.25],
                        [r.left + r.width * 0.25, r.top + r.height * 0.75],
                        [r.left + r.width * 0.75, r.top + r.height * 0.75],
                    ];

                    const esMiDescendiente = (found) => {
                        let ancestor = found;
                        while (ancestor) {
                            if (ancestor === node) return true;
                            ancestor = ancestor.parentElement;
                        }
                        return false;
                    };

                    // Verificar si el elemento que tapa es un componente de layout legítimo
                    // (scroller horizontal, ticker de noticias, header sticky del sitio)
                    // Estos no son obstrucciones reales — el elemento sigue siendo clickeable
                    const esLayoutLegitimo = (found) => {
                        if (!found) return false;
                        const s = window.getComputedStyle(found);
                        // Si el elemento que tapa es un contenedor de scroll horizontal
                        // y el nodo auditado está DENTRO de él, no es obstrucción
                        if (s.overflowX === 'scroll' || s.overflowX === 'auto') return true;
                        // Si el que tapa es ancestro del nodo auditado, no es obstrucción
                        if (found.contains(node)) return true;
                        return false;
                    };

                    const algunoLibre = puntos.some(([px, py]) => {
                        const found = document.elementFromPoint(px, py);
                        if (!found) return false;
                        if (esMiDescendiente(found)) return true;
                        if (esLayoutLegitimo(found)) return true;
                        return false;
                    });

                    return !algunoLibre;
                }""")


                # Enriquecer el nombre del elemento si no tiene texto visible
                # Buscar aria-label, title, alt de imagen hija, o descripción del SVG
                nombre = texto.strip()
                if not nombre:
                    nombre = await el.evaluate("""(node) => {
                        // 1. aria-label directo
                        if (node.getAttribute('aria-label')) return node.getAttribute('aria-label');
                        // 2. title directo
                        if (node.getAttribute('title')) return node.getAttribute('title');
                        // 3. alt de imagen hija
                        const img = node.querySelector('img[alt]');
                        if (img && img.getAttribute('alt')) return '🖼 ' + img.getAttribute('alt');
                        // 4. aria-label de hijo
                        const ariaChild = node.querySelector('[aria-label]');
                        if (ariaChild) return ariaChild.getAttribute('aria-label');
                        // 5. title de hijo SVG
                        const svgTitle = node.querySelector('svg title');
                        if (svgTitle && svgTitle.textContent) return '⬡ ' + svgTitle.textContent;
                        // 6. Describir por rol/tipo
                        // Mostrar id o class del elemento para identificarlo en el DOM
                        const id = node.getAttribute('id');
                        if (id) return `#${id}`;
                        const cls = node.className && typeof node.className === 'string'
                            ? node.className.trim().split(/ +/).slice(0, 3).join(' ')
                            : '';
                        if (cls) return `.${cls.split(' ').join('.')}`;
                        const tag = node.tagName.toLowerCase();
                        const role = node.getAttribute('role') || '';
                        if (tag === 'button' || role === 'button') return '[button]';
                        if (tag === 'a') return '[a]';
                        return `[${tag}]`;
                    }""")

                # Obtener motivo de obstrucción si está obstruido
                # Re-evaluar con lógica más estricta: ignorar elementos sticky/scroll
                # que no bloquean realmente el click (falsos positivos de tickeres y barras)
                motivo = None
                if obstruido:
                    resultado = await el.evaluate("""(node) => {
                        const puntos = [];
                        const r = node.getBoundingClientRect();
                        const cx = r.left + r.width / 2;
                        const cy = r.top + r.height / 2;
                        puntos.push([cx, cy],
                            [r.left + r.width * 0.25, r.top + r.height * 0.25],
                            [r.left + r.width * 0.75, r.top + r.height * 0.75]);

                        const esMiDescendiente = (found) => {
                            let a = found;
                            while (a) { if (a === node) return true; a = a.parentElement; }
                            return false;
                        };

                        for (const [px, py] of puntos) {
                            const found = document.elementFromPoint(px, py);
                            if (!found || esMiDescendiente(found)) continue;

                            const s = window.getComputedStyle(found);
                            const pos = s.position;

                            // Ignorar elementos sticky/scroll — no bloquean clicks reales
                            // (tickeres, barras de noticias, scrollers horizontales)
                            if (pos === 'sticky') continue;
                            const overflow = s.overflow + s.overflowX + s.overflowY;
                            if (overflow.includes('scroll') || overflow.includes('auto')) continue;

                            // Es un obstructor real
                            const tag = found.tagName.toLowerCase();
                            const id = found.getAttribute('id') ? `#${found.getAttribute('id')}` : '';
                            const cls = found.className && typeof found.className === 'string'
                                ? `.${found.className.trim().split(/ +/).slice(0,2).join('.')}`
                                : '';
                            const selector = id || cls || tag;
                            const zFound = parseInt(s.zIndex) || 0;
                            if (pos === 'fixed') return `Overlay fijo: ${selector}`;
                            if (zFound > 100) return `Z-index alto (${zFound}): ${selector}`;
                            return `Cubierto por: <${tag}> ${selector}`;
                        }
                        // Todos los puntos pasaron — no es obstrucción real
                        return '__NO_OBSTRUIDO__';
                    }""")

                    if resultado == '__NO_OBSTRUIDO__':
                        obstruido = False  # Corregir el falso positivo
                        motivo = None
                        # Actualizar el último append del reporte
                    else:
                        motivo = resultado

                reporte.append({
                    "texto": nombre,
                    "tipo": await el.evaluate("e => e.tagName"),
                    "href": href or "Acción JS",
                    "obstruido": obstruido,
                    "motivo_obstruccion": motivo,
                    "status": 200
                })
              except Exception:
                # Si el elemento quedó inválido (navegación SPA, prefetch, etc.), saltear
                pass

            # FIX: limpiar rutas pendientes antes de cerrar para evitar TargetClosedError
            await page.unroute_all(behavior="ignoreErrors")
            await browser.close()

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR en auditar-links:\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=f"Error en auditoría de links: {str(e)}")

    # MEJORA 2 + 3: insert async con timeout
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                lambda: supabase.table("auditoria_links").insert({
                    "url_auditada": url_segura,
                    "reporte": reporte,
                    "user_id": datos.user_id,
                    "batch_id": datos.batch_id
                }).execute()
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Supabase no respondió al guardar la auditoría.")

    return {"status": "success", "reporte": reporte}

# --- 7. UTILITARIOS ---
# MEJORA 2: subir_imagen ahora es async — usa asyncio.to_thread para no bloquear el Event Loop
async def subir_imagen(ruta, nombre):
    if not os.path.exists(ruta):
        return None

    def _subir():
        with open(ruta, 'rb') as f:
            supabase.storage.from_("vrt-images").upload(
                path=nombre,
                file=f.read(),
                file_options={"content-type": "image/png"}
            )
        return supabase.storage.from_("vrt-images").get_public_url(nombre)

    return await asyncio.to_thread(_subir)

# --- 8. MODELOS MÓDULOS 3 y 4 ---
class URLParaPerformance(BaseModel):
    url: str
    user_id: str = None
    batch_id: str = None

class URLParaSEO(BaseModel):
    url: str
    user_id: str = None
    batch_id: str = None

# --- 9. ENDPOINT CORE WEB VITALS (MÓDULO 3) ---
@app.post("/api/performance")
async def api_performance(datos: URLParaPerformance):
    url_segura = asegurar_http(datos.url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()

            # Capturar métricas de red
            recursos = []
            page.on("response", lambda r: recursos.append(r))

            await bloquear_recursos_innecesarios(page)

            # FIX LCP: registrar el PerformanceObserver ANTES de navegar
            # así captura las entradas de largest-contentful-paint durante la carga
            await page.add_init_script("""
                window.__lcp_value = null;
                window.__cls_value = 0;
                try {
                    new PerformanceObserver((list) => {
                        const entries = list.getEntries();
                        window.__lcp_value = entries[entries.length - 1].startTime;
                    }).observe({ type: 'largest-contentful-paint', buffered: true });

                    new PerformanceObserver((list) => {
                        for (const entry of list.getEntries()) {
                            if (!entry.hadRecentInput) window.__cls_value += entry.value;
                        }
                    }).observe({ type: 'layout-shift', buffered: true });
                } catch(e) {}
            """)

            start_time = asyncio.get_event_loop().time()
            await page.goto(url_segura, wait_until="domcontentloaded", timeout=90000)

            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            # Dar tiempo al observer de LCP para capturar el elemento final
            await asyncio.sleep(1)

            end_time = asyncio.get_event_loop().time()
            tiempo_carga_ms = round((end_time - start_time) * 1000)

            # Obtener métricas de Performance API del browser
            metricas = await page.evaluate("""() => {
                const nav = performance.getEntriesByType('navigation')[0];
                const paint = performance.getEntriesByType('paint');
                const fcp = paint.find(p => p.name === 'first-contentful-paint');

                // LCP desde el observer registrado antes de navegar
                const lcp = window.__lcp_value ? Math.round(window.__lcp_value) : null;

                // CLS desde el observer (hadRecentInput ya filtrado)
                const cls = Math.round((window.__cls_value || 0) * 1000) / 1000;

                // TTI aproximado: tiempo hasta que el hilo principal queda libre
                const longTasks = performance.getEntriesByType('longtask');
                const tti = longTasks.length
                    ? Math.max(...longTasks.map(t => t.startTime + t.duration))
                    : (nav ? nav.domInteractive : null);

                return {
                    fcp: fcp ? Math.round(fcp.startTime) : null,
                    lcp,
                    cls,
                    tti: tti ? Math.round(tti) : null,
                    dom_interactive: nav ? Math.round(nav.domInteractive) : null,
                    dom_complete: nav ? Math.round(nav.domComplete) : null,
                    transfer_size: nav ? nav.transferSize : null,
                };
            }""")

            # Peso total de recursos transferidos
            peso_total_bytes = metricas.get("transfer_size") or 0
            peso_total_mb = round(peso_total_bytes / (1024 * 1024), 2)

            await page.unroute_all(behavior="ignoreErrors")
            await browser.close()

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR en performance:\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=f"Error en auditoría de performance: {str(e)}")

    resultado = {
        "url": url_segura,
        "user_id": datos.user_id,
        "batch_id": datos.batch_id,
        "tiempo_carga_ms": tiempo_carga_ms,
        "fcp_ms": metricas.get("fcp"),
        "lcp_ms": metricas.get("lcp"),
        "cls": metricas.get("cls"),
        "tti_ms": metricas.get("tti"),
        "peso_mb": peso_total_mb,
        "dom_interactive_ms": metricas.get("dom_interactive"),
        "dom_complete_ms": metricas.get("dom_complete"),
    }

    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                lambda: supabase.table("performance_audits").insert(resultado).execute()
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Supabase no respondió al guardar performance.")

    return {"status": "success", "resultado": resultado}


# --- 10. ENDPOINT SEO & ACCESIBILIDAD (MÓDULO 4) ---
@app.post("/api/seo")
async def api_seo(datos: URLParaSEO):
    url_segura = asegurar_http(datos.url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': 1280, 'height': 800})
            await bloquear_recursos_innecesarios(page)
            await page.goto(url_segura, wait_until="domcontentloaded", timeout=90000)

            seo = await page.evaluate("""() => {
                const getMeta = (name) => {
                    const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                    return el ? el.getAttribute('content') : null;
                };

                // Title
                const title = document.title || null;
                const titleLen = title ? title.length : 0;

                // Meta description
                const description = getMeta('description');
                const descLen = description ? description.length : 0;

                // H1
                const h1s = Array.from(document.querySelectorAll('h1'));
                const h1Count = h1s.length;
                const h1Text = h1s.length ? h1s[0].innerText.trim() : null;

                // Canonical
                const canonical = document.querySelector('link[rel="canonical"]');
                const canonicalUrl = canonical ? canonical.getAttribute('href') : null;

                // Meta robots
                const robots = getMeta('robots');

                // Open Graph
                const ogTitle = getMeta('og:title');
                const ogDescription = getMeta('og:description');
                const ogImage = getMeta('og:image');

                // Imágenes sin alt
                const imgs = Array.from(document.querySelectorAll('img'));
                const imgsSinAlt = imgs.filter(img => !img.getAttribute('alt') || img.getAttribute('alt').trim() === '').length;
                const totalImgs = imgs.length;

                // Inputs sin label
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])'));
                const inputsSinLabel = inputs.filter(input => {
                    const id = input.getAttribute('id');
                    const hasLabel = id && document.querySelector(`label[for="${id}"]`);
                    const hasAria = input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
                    return !hasLabel && !hasAria;
                }).length;

                // Botones sin aria-label ni texto
                const botones = Array.from(document.querySelectorAll('button, [role="button"]'));
                const botonesSinEtiqueta = botones.filter(btn => {
                    const text = btn.innerText ? btn.innerText.trim() : '';
                    const aria = btn.getAttribute('aria-label') || btn.getAttribute('title') || '';
                    return !text && !aria;
                }).length;

                return {
                    title, title_len: titleLen,
                    description, desc_len: descLen,
                    h1_count: h1Count, h1_text: h1Text,
                    canonical: canonicalUrl,
                    robots,
                    og_title: ogTitle, og_description: ogDescription, og_image: ogImage,
                    imgs_sin_alt: imgsSinAlt, total_imgs: totalImgs,
                    inputs_sin_label: inputsSinLabel,
                    botones_sin_etiqueta: botonesSinEtiqueta,
                };
            }""")

            await page.unroute_all(behavior="ignoreErrors")
            await browser.close()

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR en seo:\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=f"Error en auditoría SEO: {str(e)}")

    resultado = {"url": url_segura, "user_id": datos.user_id, "batch_id": datos.batch_id, **seo}

    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                lambda: supabase.table("seo_audits").insert(resultado).execute()
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Supabase no respondió al guardar SEO.")

    return {"status": "success", "resultado": resultado}
