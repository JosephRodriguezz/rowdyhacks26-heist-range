/* engine.js: the player for the 14-scene motion demo.
 *
 * Reads the story from story.js (a snapshot of the v0 fixture), builds one image and one effects layer per
 * scene, and drives whichever scene modules registered themselves with MP.register(). A scene with no module,
 * or one that throws, simply shows its still. Nothing here is live: the source is always FIXTURE.
 *
 * URL options: ?t=SECONDS (paused snapshot), ?scene=N&lt=SECONDS (paused, N is 1-14), ?play=1 (autoplay),
 *              ?speed=0.5|1|2, ?reduced=1 (reduced motion).
 */
(function () {
  'use strict';
  var MP = window.MP, STORY = window.MP_STORY;
  var IMG_BASE = '../scenes-v2/';
  var ASPECT = MP.ASPECT, clamp = MP.clamp, CAM0 = MP.CAM0;

  function $(id) { return document.getElementById(id); }
  function fmt(t) { var m = Math.floor(t / 60), s = t - m * 60; return m + ':' + (s < 10 ? '0' : '') + s.toFixed(1); }

  /* --------------------------------------------------------------------- DOM */
  var stage = $('stage'), world = $('world'), fxc = $('fx'), fade = $('fade'), tag = $('sceneTag'),
      poster = $('poster'), playBtn = $('play'), replayBtn = $('replay'), chipsEl = $('chips'),
      speedSel = $('speed'), reducedBox = $('reduced'), timeEl = $('time'), segsEl = $('segments'),
      scrub = $('scrub'), endCard = $('endCard'), endReplay = $('endReplay'), errBanner = $('errBanner'),
      hud = { scene: $('hudScene'), phase: $('hudPhase'), actor: $('hudActor'), red: $('hudRed'), blue: $('hudBlue'), bank: $('hudBank'), alarm: $('hudAlarm') };
  MP.ctx = fxc.getContext('2d');

  /* ------------------------------------------------------------------- state */
  var t = 0, started = false, playing = false, speed = 1, reduced = false;
  var curIdx = -1, dragging = false, raf = 0, lastTs = 0, lastValueText = '';
  var TOTAL = STORY.total;

  /* ------------------------------------------------------------------ scenes */
  var SCENES = STORY.scenes.map(function (st) {
    var sc = {}, k;
    for (k in st) sc[k] = st[k];
    sc.def = MP.defs[st.id] || {};
    sc.glows = [];
    return sc;
  });

  // Run one scene hook with error isolation: a broken scene logs once and falls back to its still.
  function call(sc, name, a, b) {
    var f = sc.def[name];
    if (!f || sc.broken) return undefined;
    try { return f(sc, a, b); }
    catch (e) {
      sc.broken = true;
      sc.layer.style.visibility = 'hidden';
      console.error('[motion] scene ' + sc.num + ' (' + sc.id + ') ' + name + '() failed: ' + (e && e.message));
      errBanner.textContent = 'Effects error in scene ' + sc.num + ' (' + sc.id + '). See the browser console. The still is shown instead.';
      errBanner.hidden = false;
      return undefined;
    }
  }
  function sceneIndexAt(time) {
    for (var i = SCENES.length - 1; i > 0; i--) if (time >= SCENES[i].start) return i;
    return 0;
  }

  /* ------------------------------------------------------------ build the page */
  var chipBtns = [], segDivs = [];
  SCENES.forEach(function (sc, i) {
    var img = new Image();
    img.alt = sc.alt; img.draggable = false; img.decoding = 'async';
    img.addEventListener('error', function () { sc.missing = true; if (curIdx === i) refreshTag(); });
    img.src = IMG_BASE + sc.file;
    var layer = document.createElement('div');
    layer.className = 'fx-layer';
    world.insertBefore(img, fxc);
    world.insertBefore(layer, fxc);
    sc.img = img; sc.layer = layer;
    call(sc, 'setup', layer);

    var b = document.createElement('button');
    b.type = 'button'; b.textContent = sc.num; b.title = sc.label;
    b.setAttribute('aria-label', 'Jump to scene ' + sc.num + ', ' + sc.title);
    b.addEventListener('click', function () { seek(sc.start); });
    chipsEl.appendChild(b); chipBtns.push(b);

    var d = document.createElement('div');
    d.style.flex = sc.dur + ' 1 0';
    segsEl.appendChild(d); segDivs.push(d);
  });
  scrub.max = String(TOTAL);

  /* ------------------------------------------------------------------- render */
  function refreshTag() {
    var sc = SCENES[Math.max(curIdx, 0)];
    tag.textContent = started ? sc.label + (sc.missing ? ' · image missing' : '') : 'Ready · press Play';
  }

  function showScene(idx) {
    SCENES.forEach(function (sc, i) {
      sc.img.classList.toggle('on', i === idx);
      sc.layer.classList.toggle('on', i === idx);
    });
    chipBtns.forEach(function (b, i) {
      if (started && i === idx) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current');
    });
    segDivs.forEach(function (d, i) { d.classList.toggle('on', started && i <= idx); });
    var sc = SCENES[idx], dash = '—';
    hud.scene.textContent = started ? sc.label : 'Not started';
    hud.phase.textContent = started ? sc.phase : dash;
    hud.actor.textContent = started ? sc.actor : dash;
    hud.red.textContent = started ? sc.red : dash;
    hud.blue.textContent = started ? sc.blue : dash;
    hud.bank.textContent = started ? '● ' + sc.bank : dash;
    hud.bank.dataset.state = started ? sc.bank : '';
    hud.alarm.textContent = started ? (sc.alarm ? 'ON' : 'Off') : dash;
    hud.alarm.dataset.state = started && sc.alarm ? 'on' : '';
    curIdx = idx;
    refreshTag();
  }

  function resizeCanvas() {
    var w = stage.getBoundingClientRect().width, dpr = Math.min(window.devicePixelRatio || 1, 2);
    var pw = Math.max(2, Math.round(w * dpr)), ph = Math.max(2, Math.round(pw * ASPECT));
    if (fxc.width !== pw || fxc.height !== ph) { fxc.width = pw; fxc.height = ph; }
    MP.cw = pw;
  }

  function renderFrame() {
    var idx = started ? sceneIndexAt(t) : 0, sc = SCENES[idx], lt = started ? clamp(t - sc.start, 0, sc.dur) : 0, cam, j;
    var ctx = MP.ctx;
    MP.reduced = reduced;
    if (idx !== curIdx) showScene(idx);

    cam = (started && call(sc, 'cam', lt)) || CAM0;
    world.style.transformOrigin = cam[3] + '% ' + cam[4] + '%';
    world.style.transform = 'translate3d(' + cam[1].toFixed(3) + '%,' + cam[2].toFixed(3) + '%,0) scale(' + cam[0].toFixed(4) + ')';

    if (started) call(sc, 'dom', lt);
    else for (j = 0; j < sc.glows.length; j++) sc.glows[j].style.opacity = '0';

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, fxc.width, fxc.height);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.save();
    if (started) call(sc, 'draw', lt);
    ctx.restore();
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';

    // Dip in from dark at each cut, only while playing; a paused or scrubbed frame is always clean.
    var continuous = sc.id === 'alarm' || sc.id === 'rush' || sc.id === 'recovered' || sc.id === 'hydroplane';
    fade.style.opacity = (!reduced && !continuous && started && playing && lt < 0.45 ? 0.65 * (1 - lt / 0.45) : 0).toFixed(3);
    endCard.hidden = !(started && t >= TOTAL - 0.001);

    if (!dragging) scrub.value = String(t);
    timeEl.textContent = fmt(t) + ' / ' + fmt(TOTAL);
    var vt = started ? 'Scene ' + sc.num + ' of ' + SCENES.length + ', ' + Math.round(t) + ' of ' + Math.round(TOTAL) + ' seconds' : 'Not started';
    if (vt !== lastValueText) { lastValueText = vt; scrub.setAttribute('aria-valuetext', vt); }
  }

  /* ------------------------------------------------------------------ control */
  function markStarted() { if (!started) { started = true; poster.hidden = true; curIdx = -1; } }
  function atEnd() { return started && t >= TOTAL - 0.001; }
  function updatePlayButton() { playBtn.textContent = playing ? 'Pause' : atEnd() ? 'Play again' : 'Play'; }

  function tick(ts) {
    raf = 0;
    if (!playing) return;
    var dt = lastTs ? Math.min(0.1, (ts - lastTs) / 1000) : 0;
    lastTs = ts;
    t += dt * speed;
    if (t >= TOTAL) { t = TOTAL; setPlaying(false); return; }
    renderFrame();
    raf = requestAnimationFrame(tick);
  }
  function setPlaying(v) {
    playing = v; lastTs = 0;
    if (!playing && raf) { cancelAnimationFrame(raf); raf = 0; }
    if (playing && !raf) raf = requestAnimationFrame(tick);
    updatePlayButton();
    renderFrame();
  }
  function togglePlay() {
    if (!started) { markStarted(); t = 0; } else if (!playing && atEnd()) { t = 0; }
    setPlaying(!playing);
  }
  function replay() { markStarted(); t = 0; setPlaying(true); }
  function seek(v) { markStarted(); t = clamp(v, 0, TOTAL); updatePlayButton(); renderFrame(); }
  function stepScene(d) {
    var i = clamp((started ? sceneIndexAt(t) : 0) + d, 0, SCENES.length - 1);
    seek(SCENES[i].start);
  }

  playBtn.addEventListener('click', togglePlay);
  replayBtn.addEventListener('click', replay);
  endReplay.addEventListener('click', replay);
  poster.addEventListener('click', function () { togglePlay(); playBtn.focus(); });
  speedSel.addEventListener('change', function () { speed = parseFloat(speedSel.value) || 1; });
  reducedBox.addEventListener('change', function () { reduced = reducedBox.checked; renderFrame(); });
  scrub.addEventListener('pointerdown', function () { dragging = true; });
  window.addEventListener('pointerup', function () { dragging = false; });
  scrub.addEventListener('input', function () { seek(parseFloat(scrub.value) || 0); });
  document.addEventListener('visibilitychange', function () { if (document.hidden) setPlaying(false); lastTs = 0; });

  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var tg = e.target, tn = tg && tg.tagName, k = e.key;
    if (tn === 'SELECT' || tn === 'INPUT' || tn === 'TEXTAREA' || (tg && tg.isContentEditable)) return;
    if (k === ' ' || k === 'Spacebar') {
      if (tn === 'BUTTON' || tn === 'INPUT') return;            // native activation handles it
      e.preventDefault(); togglePlay();
    } else if (k === 'r' || k === 'R') { replay(); }
    else if (k >= '1' && k <= '9') { seek(SCENES[+k - 1].start); }
    else if (k === '[') { stepScene(-1); }
    else if (k === ']') { stepScene(1); }
    else if (k === 'ArrowLeft') { e.preventDefault(); seek(t - 1); }
    else if (k === 'ArrowRight') { e.preventDefault(); seek(t + 1); }
  });

  /* --------------------------------------------------------------------- init */
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  reduced = !!(mq && mq.matches);

  var qs = new URLSearchParams(window.location.search);
  if (qs.get('reduced') === '1') reduced = true;
  var qSpeed = parseFloat(qs.get('speed'));
  if (qSpeed > 0 && qSpeed <= 8) {
    speed = qSpeed;
    if (!speedSel.querySelector('option[value="' + qSpeed + '"]')) {
      var o = document.createElement('option');
      o.value = String(qSpeed); o.textContent = qSpeed + '×'; speedSel.appendChild(o);
    }
    speedSel.value = String(qSpeed);
  }
  reducedBox.checked = reduced;
  if (qs.has('scene')) {
    var sn = parseInt(qs.get('scene'), 10), sl = parseFloat(qs.get('lt'));
    if (sn >= 1 && sn <= SCENES.length) { markStarted(); t = SCENES[sn - 1].start + clamp(isFinite(sl) ? sl : 0, 0, SCENES[sn - 1].dur); }
  } else if (qs.has('t')) {
    var q = parseFloat(qs.get('t'));
    if (isFinite(q)) { markStarted(); t = clamp(q, 0, TOTAL); }
  }

  resizeCanvas();
  if (window.ResizeObserver) new ResizeObserver(function () { resizeCanvas(); renderFrame(); }).observe(stage);
  else window.addEventListener('resize', function () { resizeCanvas(); renderFrame(); });

  updatePlayButton();
  renderFrame();
  if (qs.get('play') === '1') { markStarted(); setPlaying(true); }
})();
