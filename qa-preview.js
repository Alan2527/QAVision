/* ============================================================
   QAVision — Componente de Preview / Escaneo (100% cliente)
   ------------------------------------------------------------
   Muestra un skeleton animado tipo "mini navegador" mientras corre
   el test (línea de escaneo verde + lupa que inspecciona + estados
   que ciclan), y al terminar hace fade a la captura REAL del sitio,
   en el MISMO alto de contenedor, con scroll manual y barra verde.

   No toca el backend: aparece al instante y no compite con el test.

   API:
     QAPreview.start(target, url)        -> arranca el skeleton
     QAPreview.finish(target, imageUrl)  -> fade a la imagen real (scroll manual)
     QAPreview.fail(target, mensaje)     -> estado de error
     QAPreview.markers(target, items)    -> dibuja recuadros (links) sobre la imagen
   donde `target` es un id (string) o el elemento contenedor.
   El contenedor define el alto (ej: <div id="qa-preview" style="height:380px"></div>).
   ============================================================ */
(function () {
  "use strict";

  var VERDE = "#10b981";
  var VERDE2 = "#34d399";

  // ---- Inyección de estilos (una sola vez) ----
  function asegurarCSS() {
    if (document.getElementById("qap-style")) return;
    var st = document.createElement("style");
    st.id = "qap-style";
    st.textContent = [
      ".qap-root{position:relative;width:100%;height:100%;background:#0d0d0d;border:1px solid #1a1a1a;border-radius:16px;overflow:hidden;font-family:ui-monospace,Menlo,Consolas,monospace;}",
      ".qap-chrome{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid #1a1a1a;background:#0a0a0a;}",
      ".qap-dot{width:10px;height:10px;border-radius:50%;display:inline-block;}",
      ".qap-url{margin-left:8px;color:rgba(255,255,255,.55);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}",
      ".qap-body{position:relative;width:100%;height:calc(100% - 35px);overflow:hidden;}",
      // Skeleton shimmer
      ".qap-sk{position:absolute;inset:0;padding:18px;display:flex;flex-direction:column;gap:14px;}",
      ".qap-block{border-radius:8px;background:linear-gradient(100deg,#141414 30%,#1f1f1f 50%,#141414 70%);background-size:200% 100%;animation:qap-shimmer 1.6s linear infinite;}",
      "@keyframes qap-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}",
      // Línea de escaneo
      ".qap-scan{position:absolute;left:0;right:0;height:2px;top:0;z-index:6;pointer-events:none;background:linear-gradient(90deg,transparent,"+VERDE+" 20%,"+VERDE2+" 50%,"+VERDE+" 80%,transparent);box-shadow:0 0 16px 3px rgba(16,185,129,.55);animation:qap-scan 2.6s ease-in-out infinite;}",
      "@keyframes qap-scan{0%{top:0;opacity:0}6%{opacity:1}94%{opacity:1}100%{top:100%;opacity:0}}",
      // Lupa
      ".qap-lupa{position:absolute;z-index:7;width:46px;height:46px;pointer-events:none;animation:qap-lupa 4.2s ease-in-out infinite;filter:drop-shadow(0 0 6px rgba(16,185,129,.6));}",
      "@keyframes qap-lupa{0%{left:8%;top:10%}25%{left:62%;top:28%}50%{left:20%;top:58%}75%{left:70%;top:72%}100%{left:8%;top:10%}}",
      ".qap-lupa svg{width:100%;height:100%;}",
      ".qap-lupa-ring{animation:qap-pulse 1.2s ease-in-out infinite;transform-origin:center;}",
      "@keyframes qap-pulse{0%,100%{opacity:.6}50%{opacity:1}}",
      // Estado
      ".qap-status{position:absolute;left:0;right:0;bottom:0;z-index:7;padding:8px 12px;background:linear-gradient(0deg,rgba(0,0,0,.85),transparent);color:"+VERDE2+";font-size:11px;letter-spacing:.5px;}",
      ".qap-status .qap-blink{animation:qap-pulse 1s ease-in-out infinite;}",
      // Imagen real + scroll verde
      ".qap-scroll{position:absolute;inset:0;overflow-y:auto;overflow-x:hidden;background:#0d0d0d;opacity:0;transition:opacity .45s ease;scrollbar-width:thin;scrollbar-color:"+VERDE+" #0d0d0d;}",
      ".qap-scroll.qap-show{opacity:1;}",
      ".qap-scroll::-webkit-scrollbar{width:10px;}",
      ".qap-scroll::-webkit-scrollbar-thumb{background:"+VERDE+";border-radius:5px;}",
      ".qap-scroll::-webkit-scrollbar-thumb:hover{background:"+VERDE2+";}",
      ".qap-scroll::-webkit-scrollbar-track{background:#0d0d0d;}",
      ".qap-scroll img{display:block;width:100%;}",
      ".qap-canvas{position:absolute;top:0;left:0;pointer-events:none;}",
      ".qap-fade{transition:opacity .4s ease;}",
      ".qap-hide{opacity:0;}",
      ".qap-err{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;color:#f87171;font-size:12px;padding:20px;}"
    ].join("");
    document.head.appendChild(st);
  }

  function el(target) {
    return typeof target === "string" ? document.getElementById(target) : target;
  }

  var LUPA_SVG =
    '<svg viewBox="0 0 48 48" fill="none">' +
    '<circle class="qap-lupa-ring" cx="20" cy="20" r="13" stroke="' + VERDE2 + '" stroke-width="2.5"/>' +
    '<line x1="29" y1="29" x2="42" y2="42" stroke="' + VERDE2 + '" stroke-width="3" stroke-linecap="round"/>' +
    '<circle cx="20" cy="20" r="13" fill="' + VERDE + '" fill-opacity="0.06"/>' +
    "</svg>";

  function skeletonBlocks() {
    // Bloques que simulan un layout real (header, hero, grilla de tarjetas, líneas)
    return (
      '<div class="qap-block" style="height:34px;width:60%;"></div>' +
      '<div class="qap-block" style="height:90px;width:100%;"></div>' +
      '<div style="display:flex;gap:14px;">' +
        '<div class="qap-block" style="height:70px;flex:1;"></div>' +
        '<div class="qap-block" style="height:70px;flex:1;"></div>' +
        '<div class="qap-block" style="height:70px;flex:1;"></div>' +
      "</div>" +
      '<div class="qap-block" style="height:16px;width:90%;"></div>' +
      '<div class="qap-block" style="height:16px;width:80%;"></div>' +
      '<div class="qap-block" style="height:16px;width:85%;"></div>'
    );
  }

  var ESTADOS = ["Cargando página", "Escaneando elementos", "Analizando resultados", "Compilando reporte"];

  var QAPreview = {
    _timers: {},

    start: function (target, url) {
      asegurarCSS();
      var c = el(target);
      if (!c) return;
      this._clear(target);
      c.innerHTML =
        '<div class="qap-root">' +
          '<div class="qap-chrome">' +
            '<span class="qap-dot" style="background:#ff5f56"></span>' +
            '<span class="qap-dot" style="background:#ffbd2e"></span>' +
            '<span class="qap-dot" style="background:#27c93f"></span>' +
            '<span class="qap-url">' + (url ? String(url).replace(/</g, "&lt;") : "") + "</span>" +
          "</div>" +
          '<div class="qap-body">' +
            '<div class="qap-sk">' + skeletonBlocks() + "</div>" +
            '<div class="qap-scan"></div>' +
            '<div class="qap-lupa">' + LUPA_SVG + "</div>" +
            '<div class="qap-status"><span class="qap-blink">▮</span> <span class="qap-status-txt">Cargando página…</span></div>' +
          "</div>" +
        "</div>";
      // Ciclo de estados
      var i = 0;
      var txt = c.querySelector(".qap-status-txt");
      this._timers[this._key(target)] = setInterval(function () {
        i = (i + 1) % ESTADOS.length;
        if (txt) txt.textContent = ESTADOS[i] + "…";
      }, 1800);
    },

    finish: function (target, imageUrl) {
      var c = el(target);
      if (!c) return;
      this._clearTimer(target);
      if (!imageUrl) { this._stopAnim(c); return; }
      var body = c.querySelector(".qap-body");
      if (!body) { this.start(target, ""); body = c.querySelector(".qap-body"); }
      // Capa de imagen (scroll manual) que aparece con fade encima del skeleton
      var scroll = document.createElement("div");
      scroll.className = "qap-scroll";
      var img = document.createElement("img");
      img.alt = "Captura del sitio analizado";
      img.className = "qap-result-img";
      scroll.appendChild(img);
      body.appendChild(scroll);
      var sk = body.querySelector(".qap-sk");
      var scan = body.querySelector(".qap-scan");
      var lupa = body.querySelector(".qap-lupa");
      img.onload = function () {
        scroll.classList.add("qap-show");
        [sk, scan, lupa].forEach(function (n) { if (n) { n.classList.add("qap-fade", "qap-hide"); setTimeout(function () { if (n && n.parentNode) n.parentNode.removeChild(n); }, 450); } });
      };
      img.onerror = function () { scroll.classList.add("qap-show"); };
      img.src = imageUrl;
    },

    // Dibuja recuadros sobre la imagen del resultado (para Link Scanner).
    // items: [{x,y,w,h,color?,label?,id?}] en coordenadas de la imagen capturada.
    // Devuelve un mapa id->elemento para poder resaltar al clickear.
    markers: function (target, items) {
      var c = el(target);
      if (!c) return {};
      var scroll = c.querySelector(".qap-scroll");
      var img = c.querySelector(".qap-result-img");
      if (!scroll || !img) return {};
      var map = {};
      function dibujar() {
        var escala = img.clientWidth / (img.naturalWidth || img.clientWidth);
        var viejos = scroll.querySelectorAll(".qap-marker");
        viejos.forEach(function (v) { v.remove(); });
        (items || []).forEach(function (it, idx) {
          var box = document.createElement("div");
          box.className = "qap-marker";
          var color = it.color || "#f5c518"; // amarillo por defecto
          box.style.cssText =
            "position:absolute;border:2px solid " + color + ";border-radius:3px;" +
            "box-shadow:0 0 0 2px rgba(0,0,0,.25);pointer-events:none;z-index:4;" +
            "left:" + (it.x * escala) + "px;top:" + (it.y * escala) + "px;" +
            "width:" + (it.w * escala) + "px;height:" + (it.h * escala) + "px;" +
            "transition:box-shadow .15s ease,background .15s ease;";
          scroll.appendChild(box);
          map[it.id != null ? it.id : idx] = box;
        });
      }
      if (img.complete && img.naturalWidth) dibujar(); else img.addEventListener("load", dibujar, { once: true });
      window.addEventListener("resize", dibujar);
      return map;
    },

    // Resalta un recuadro y hace scroll hasta él (al clickear una fila del reporte)
    focusMarker: function (target, box) {
      var c = el(target);
      if (!c || !box) return;
      var scroll = c.querySelector(".qap-scroll");
      c.querySelectorAll(".qap-marker").forEach(function (m) {
        m.style.background = "transparent";
        m.style.boxShadow = "0 0 0 2px rgba(0,0,0,.25)";
      });
      box.style.background = "rgba(245,197,24,.18)";
      box.style.boxShadow = "0 0 16px 3px rgba(245,197,24,.6)";
      if (scroll) scroll.scrollTo({ top: Math.max(0, box.offsetTop - 60), behavior: "smooth" });
    },

    fail: function (target, mensaje) {
      var c = el(target);
      if (!c) return;
      this._clearTimer(target);
      var body = c.querySelector(".qap-body");
      if (body) {
        this._stopAnim(c);
        var e = document.createElement("div");
        e.className = "qap-err";
        e.textContent = "✕ " + (mensaje || "No se pudo completar el análisis.");
        body.appendChild(e);
      }
    },

    _stopAnim: function (c) {
      ["qap-scan", "qap-lupa", "qap-sk"].forEach(function (cl) {
        var n = c.querySelector("." + cl);
        if (n) n.style.animationPlayState = "paused";
      });
    },
    _key: function (target) { return typeof target === "string" ? target : (target.id || "qap"); },
    _clearTimer: function (target) { var k = this._key(target); if (this._timers[k]) { clearInterval(this._timers[k]); delete this._timers[k]; } },
    _clear: function (target) { this._clearTimer(target); }
  };

  window.QAPreview = QAPreview;
})();
