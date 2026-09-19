/* ─────────────────────────────────────────────────────────────────────────────
   Self-contained SVG slippy map. No Leaflet, no tiles, no network.

   Renders a static basemap (built once from OpenStreetMap by build_basemap.py)
   as inline SVG paths, and overlays address pins in the same coordinate space.
   Pan, zoom, pinch, and popups are all handled here.

   World coordinates are the basemap's own units: the projection below must stay
   in step with make_projector() in build_basemap.py.
   ──────────────────────────────────────────────────────────────────────────── */

const SVG_NS = 'http://www.w3.org/2000/svg';

function createMap(container, basemap, opts = {}) {
  const [S, W, N, E] = basemap.bbox;
  const WORLD_W = basemap.width, WORLD_H = basemap.height;

  // ── Projection (mirror of the Python build step) ───────────────────────────
  const merc = (lat, lon) => [
    lon * Math.PI / 180,
    Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)),
  ];
  const [x0, y0] = merc(S, W);
  const [x1, y1] = merc(N, E);
  const sx = WORLD_W / (x1 - x0);
  const project = (lat, lon) => {
    const [x, y] = merc(lat, lon);
    return [(x - x0) * sx, (y1 - y) * sx];
  };

  // ── DOM ────────────────────────────────────────────────────────────────────
  container.classList.add('svgmap');
  container.innerHTML = `
    <svg class="svgmap-canvas" xmlns="${SVG_NS}">
      <g class="svgmap-world">
        <g class="svgmap-base"></g>
        <g class="svgmap-overlay"></g>
        <g class="svgmap-pins"></g>
        <g class="svgmap-labels"></g>
      </g>
    </svg>
    <div class="svgmap-popup" hidden></div>
    <div class="svgmap-zoom">
      <button class="svgmap-zoom-in"  aria-label="Zoom in">+</button>
      <button class="svgmap-zoom-out" aria-label="Zoom out">−</button>
    </div>
    <div class="svgmap-attrib">${basemap.attribution}</div>`;

  const svg      = container.querySelector('.svgmap-canvas');
  const gWorld   = container.querySelector('.svgmap-world');
  const gBase    = container.querySelector('.svgmap-base');
  const gOverlay = container.querySelector('.svgmap-overlay');
  const gPins    = container.querySelector('.svgmap-pins');
  const gLabels  = container.querySelector('.svgmap-labels');
  const popupEl  = container.querySelector('.svgmap-popup');

  // ── Basemap paths ──────────────────────────────────────────────────────────
  // Paint order matters: fills first, then casings, then road bodies, then rail.
  const ORDER = ['green', 'water', 'building', 'rail',
                 'path', 'road-service', 'road-minor', 'road-arterial', 'road-major'];
  for (const layer of ORDER) {
    const paths = basemap.layers[layer];
    if (!paths || !paths.length) continue;
    // One <path> per layer keeps the DOM small; these never need individual hits.
    const g = document.createElementNS(SVG_NS, 'g');
    g.setAttribute('class', 'lyr lyr-' + layer);
    if (layer.startsWith('road') || layer === 'rail' || layer === 'path') {
      const casing = document.createElementNS(SVG_NS, 'path');
      casing.setAttribute('class', 'casing');
      casing.setAttribute('d', paths.join(''));
      g.appendChild(casing);
    }
    const body = document.createElementNS(SVG_NS, 'path');
    body.setAttribute('class', 'body');
    body.setAttribute('d', paths.join(''));
    g.appendChild(body);
    gBase.appendChild(g);
  }

  // ── Street labels ──────────────────────────────────────────────────────────
  const labelEls = (basemap.labels || []).map(l => {
    const t = document.createElementNS(SVG_NS, 'text');
    t.setAttribute('class', 'svgmap-label r' + l.r);
    t.setAttribute('x', l.x);
    t.setAttribute('y', l.y);
    t.setAttribute('transform', `rotate(${l.a} ${l.x} ${l.y})`);
    t.textContent = l.t;
    gLabels.appendChild(t);
    return { el: t, rank: l.r };
  });

  // ── View transform ─────────────────────────────────────────────────────────
  let k = 1, tx = 0, ty = 0;              // screen = world * k + t
  let minK = 0.2, maxK = 24;
  let vw = 0, vh = 0;

  // Returns false while the container has no usable size — during initial layout,
  // and whenever the map is display:none (the Streetscapes tab). Callers must not
  // compute a view from a zero-sized box or every fit collapses to minK.
  function measure() {
    const r = container.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    vw = r.width; vh = r.height;
    svg.setAttribute('width', vw);
    svg.setAttribute('height', vh);
    // The whole world fitting on screen is as far out as anyone needs to go.
    minK = Math.min((vw - 48) / WORLD_W, (vh - 48) / WORLD_H) * 0.9;
    return true;
  }

  function apply() {
    gWorld.setAttribute('transform', `translate(${tx} ${ty}) scale(${k})`);
    // Counter-scale anything that must keep a constant screen size.
    container.style.setProperty('--k', k);
    // Pin radius is a screen measurement, so it has to undo the world scale.
    const pr = 5.5 / k;
    for (const p of pins.values()) {
      const r = p.big ? pr * 1.3 : pr;
      p.el.setAttribute('r', r);
      p.hit.setAttribute('r', Math.max(r * 2.1, 11 / k));   // comfortable tap target
    }
    for (const { el, rank } of labelEls) {
      el.style.display = (rank === 1 || k > (rank === 2 ? 1.6 : 3.2)) ? '' : 'none';
    }
    if (openPin) positionPopup(openPin);
    opts.onView && opts.onView(k);
  }

  function clamp() {
    k = Math.max(minK, Math.min(maxK, k));
    // Keep the world from being dragged entirely off screen.
    const w = WORLD_W * k, h = WORLD_H * k;
    const padX = Math.min(vw * 0.5, w * 0.5), padY = Math.min(vh * 0.5, h * 0.5);
    tx = Math.max(vw - w - padX, Math.min(padX, tx));
    ty = Math.max(vh - h - padY, Math.min(padY, ty));
  }

  function setView(nk, nx, ny) { k = nk; tx = nx; ty = ny; clamp(); apply(); }

  function fitWorldRect(rect, padding = 24, animate = false) {
    if (!measure()) { requestAnimationFrame(() => fitWorldRect(rect, padding, animate)); return; }
    const [ax, ay, bx, by] = rect;
    const w = Math.max(bx - ax, 1e-6), h = Math.max(by - ay, 1e-6);
    const target = Math.min((vw - padding * 2) / w, (vh - padding * 2) / h);
    const nk = Math.max(minK, Math.min(maxK, target));
    const nx = vw / 2 - (ax + bx) / 2 * nk;
    const ny = vh / 2 - (ay + by) / 2 * nk;
    animate ? animateTo(nk, nx, ny) : setView(nk, nx, ny);
  }

  let anim = null;
  function animateTo(nk, nx, ny, ms = 420) {
    cancelAnimationFrame(anim);
    const k0 = k, x0v = tx, y0v = ty, t0 = performance.now();
    const ease = u => u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    (function step(now) {
      const u = Math.min(1, (now - t0) / ms), e = ease(u);
      k = k0 + (nk - k0) * e; tx = x0v + (nx - x0v) * e; ty = y0v + (ny - y0v) * e;
      clamp(); apply();
      if (u < 1) anim = requestAnimationFrame(step);
    })(performance.now());
  }

  function zoomAbout(factor, cx, cy) {
    const nk = Math.max(minK, Math.min(maxK, k * factor));
    const r = nk / k;
    setView(nk, cx - (cx - tx) * r, cy - (cy - ty) * r);
  }

  // ── Interaction ────────────────────────────────────────────────────────────
  const pointers = new Map();
  let dragged = false, pinchStart = null;

  svg.addEventListener('pointerdown', e => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, ox: e.clientX, oy: e.clientY });
    dragged = false;
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { d: Math.hypot(a.x - b.x, a.y - b.y), k };
    }
  });

  svg.addEventListener('pointermove', e => {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const r = container.getBoundingClientRect();
      const cx = (a.x + b.x) / 2 - r.left, cy = (a.y + b.y) / 2 - r.top;
      zoomAbout((d / pinchStart.d) * pinchStart.k / k, cx, cy);
      dragged = true;
      return;
    }
    if (!dragged) {
      // Measured from where the press started, not per-event, so a slow drag still
      // registers and a shaky click does not. Below the threshold this stays a
      // click, and the pin under the cursor gets it.
      if (Math.hypot(e.clientX - p.ox, e.clientY - p.oy) < 4) return;
      dragged = true;
      // Capturing retargets the compatibility click event to the <svg>, so it can
      // only happen once we know this gesture is a drag.
      try { svg.setPointerCapture(e.pointerId); } catch (_) {}
    }
    tx += dx; ty += dy; clamp(); apply();
  });

  const endPointer = e => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = null;
  };
  svg.addEventListener('pointerup', endPointer);
  svg.addEventListener('pointercancel', endPointer);

  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const r = container.getBoundingClientRect();
    // Trackpads report small deltas continuously; normalise so both feel the same.
    const factor = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0022));
    zoomAbout(factor, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  svg.addEventListener('dblclick', e => {
    const r = container.getBoundingClientRect();
    zoomAbout(2, e.clientX - r.left, e.clientY - r.top);
  });

  container.querySelector('.svgmap-zoom-in').addEventListener('click', () => zoomAbout(1.7, vw / 2, vh / 2));
  container.querySelector('.svgmap-zoom-out').addEventListener('click', () => zoomAbout(1 / 1.7, vw / 2, vh / 2));

  // ── Pins ───────────────────────────────────────────────────────────────────
  let pins = new Map();       // key -> { el, wx, wy, data }
  let openPin = null;

  function clearPins() {
    gPins.textContent = '';
    pins = new Map();
    closePopup();
  }

  function addPin(key, lat, lon, { big = false, data = null, onClick } = {}) {
    const [wx, wy] = project(lat, lon);
    const g = document.createElementNS(SVG_NS, 'g');
    g.setAttribute('class', 'svgmap-pin-g');
    const hit = document.createElementNS(SVG_NS, 'circle');
    hit.setAttribute('class', 'svgmap-hit');
    hit.setAttribute('cx', wx); hit.setAttribute('cy', wy);
    const el = document.createElementNS(SVG_NS, 'circle');
    el.setAttribute('class', 'svgmap-pin' + (big ? ' big' : ''));
    el.setAttribute('cx', wx); el.setAttribute('cy', wy);
    g.append(hit, el);

    const rec = { g, el, hit, wx, wy, data, big };
    const r0 = (big ? 1.3 : 1) * 5.5 / k;
    el.setAttribute('r', r0);
    hit.setAttribute('r', Math.max(r0 * 2.1, 11 / k));

    g.addEventListener('click', ev => {
      ev.stopPropagation();
      if (dragged) return;              // a drag that ends on a pin is not a click
      onClick && onClick(rec);
    });
    gPins.appendChild(g);
    pins.set(key, rec);
    return rec;
  }

  function setPinState(key, state) {
    for (const q of pins.values()) q.el.classList.remove('active');
    if (key == null || state !== 'active') return;
    const p = pins.get(key);
    if (!p) return;
    p.el.classList.add('active');
    gPins.appendChild(p.g);    // draw the active pin above its neighbours
  }

  function pinsBounds() {
    if (!pins.size) return [0, 0, WORLD_W, WORLD_H];
    let ax = Infinity, ay = Infinity, bx = -Infinity, by = -Infinity;
    for (const p of pins.values()) {
      ax = Math.min(ax, p.wx); ay = Math.min(ay, p.wy);
      bx = Math.max(bx, p.wx); by = Math.max(by, p.wy);
    }
    return [ax, ay, bx, by];
  }

  // ── Popup ──────────────────────────────────────────────────────────────────
  function positionPopup(rec) {
    popupEl.style.left = (rec.wx * k + tx) + 'px';
    popupEl.style.top  = (rec.wy * k + ty) + 'px';
  }

  function openPopup(rec, node) {
    popupEl.textContent = '';
    popupEl.appendChild(node);
    popupEl.hidden = false;
    openPin = rec;
    positionPopup(rec);
  }

  function closePopup() {
    popupEl.hidden = true;
    popupEl.textContent = '';
    openPin = null;
  }

  svg.addEventListener('click', e => { if (!dragged && e.target === svg) closePopup(); });

  // ── Overlay shapes (the district boundary) ─────────────────────────────────
  function drawPolygon(latlngs, cls) {
    const d = latlngs.map(([la, lo], i) => {
      const [x, y] = project(la, lo);
      return (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }).join('') + 'Z';
    const p = document.createElementNS(SVG_NS, 'path');
    p.setAttribute('class', cls);
    p.setAttribute('d', d);
    gOverlay.appendChild(p);
    return p;
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  fitWorldRect([0, 0, WORLD_W, WORLD_H]);

  const ro = new ResizeObserver(() => {
    const o = { k, tx, ty };
    if (!measure()) return;
    k = o.k; tx = o.tx; ty = o.ty; clamp(); apply();
  });
  ro.observe(container);

  return {
    project, addPin, clearPins, setPinState, pinsBounds,
    openPopup, closePopup, drawPolygon, fitWorldRect,
    pinFor(key) { return pins.get(key) || null; },
    openPopupFor(key, node) {
      const rec = pins.get(key);
      if (rec) openPopup(rec, node);
    },
    flyToWorld(wx, wy, nk) {
      if (!measure()) return;
      animateTo(nk, vw / 2 - wx * nk, vh / 2 - wy * nk);
    },
    flyToLatLon(lat, lon, nk) {
      const [wx, wy] = project(lat, lon);
      this.flyToWorld(wx, wy, nk);
    },
    get zoom() { return k; },
    invalidate() { if (measure()) { clamp(); apply(); } },
  };
}

window.createMap = createMap;
