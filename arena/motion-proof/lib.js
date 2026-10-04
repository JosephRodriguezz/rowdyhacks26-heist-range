/* lib.js: shared helpers for the 14-scene motion demo.
 *
 * Classic script (works from file://). Exposes window.MP. Scene files call MP.register({...}).
 * Everything here is a pure function of time: no Math.random, no Date, nothing carried between frames.
 * Seeded generators (MP.rng) make particles identical on every run, seek and replay.
 *
 * Canvas coordinates are "stage widths": x runs 0..1 across the stage, y runs 0..MP.ASPECT down it.
 * DOM coordinates are percent of the stage. MP.rectU(left, top, right, bottom) converts % to canvas units.
 */
(function () {
  'use strict';
  var MP = window.MP = window.MP || {};
  var TAU = Math.PI * 2;

  MP.TAU = TAU;
  MP.ASPECT = 941 / 1672;        // stage height / width (the approved art is 1672x941)
  MP.G = 1.5;                    // particle gravity, stage-widths per second squared
  MP.reduced = false;            // set by the engine; read it every frame
  MP.cw = 2;                     // canvas width in pixels; set by the engine
  MP.ctx = null;                 // the particle canvas 2D context; set by the engine
  MP.defs = {};
  MP.register = function (def) { MP.defs[def.id] = def; };

  /* ---------------------------------------------------------------- math */
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function easeInOut(x) { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); }
  function easeOut(x) { x = clamp(x, 0, 1); return 1 - (1 - x) * (1 - x); }
  function easeIn(x) { x = clamp(x, 0, 1); return x * x; }
  function smooth(a, b, v) { return easeInOut((v - a) / (b - a)); }
  MP.clamp = clamp; MP.easeInOut = easeInOut; MP.easeOut = easeOut; MP.easeIn = easeIn; MP.smooth = smooth;
  MP.lerp = function (a, b, k) { return a + (b - a) * k; };
  MP.wrap = function (v, lo, hi) { var s = hi - lo; return lo + (((v - lo) % s) + s) % s; };
  // Smooth pseudo-flicker in [0,1]; every component stays under 3 Hz.
  MP.flick = function (t) {
    return 0.5 + 0.5 * (0.5 * Math.sin(TAU * 1.1 * t + 0.6) + 0.3 * Math.sin(TAU * 2.3 * t + 2.1) + 0.2 * Math.sin(TAU * 2.4 * t + 4.2));
  };
  // Soft square wave in [0,1]. hz is capped at 2.5 so nothing built on it can flash faster than that.
  MP.pulse = function (t, hz, duty, soft) {
    hz = Math.min(hz, 2.5);
    duty = duty == null ? 0.5 : duty; soft = soft == null ? 0.15 : soft;
    var p = ((t * hz) % 1 + 1) % 1;
    return clamp(smooth(0, soft, p) - smooth(duty, duty + soft, p), 0, 1);
  };
  MP.rng = function (a) {       // mulberry32: same seed, same sequence, every time
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  // Advance a stream by n draws. Used when scenes share one seeded layout and must not reshuffle each other.
  MP.skip = function (r, n) { while (n-- > 0) r(); };
  // Percent-of-stage rectangle to canvas units (stage widths).
  MP.rectU = function (left, top, right, bottom) {
    return { x0: left / 100, x1: right / 100, y0: top / 100 * MP.ASPECT, y1: bottom / 100 * MP.ASPECT };
  };

  /* ----------------------------------------------------------------- DOM */
  MP.add = function (parent, className, cssText) {
    var d = document.createElement('div');
    if (className) d.className = className;
    if (cssText) d.style.cssText = cssText;
    parent.appendChild(d);
    return d;
  };
  // Absolutely positioned box; rect is {left, top, width, height} in % of the stage.
  MP.box = function (layer, rect, className, extraCss) {
    return MP.add(layer, className, 'left:' + rect.left + '%;top:' + rect.top + '%;width:' + rect.width + '%;height:' + rect.height + '%' + (extraCss ? ';' + extraCss : ''));
  };
  // Inject a scene's own CSS once (scenes never edit index.html).
  MP.css = (function () {
    var done = {};
    return function (key, text) {
      if (done[key]) return;
      done[key] = true;
      var s = document.createElement('style');
      s.textContent = text;
      document.head.appendChild(s);
    };
  })();
  // Soft light blob: x,y in % of the stage, w,h in cqw, blended with `screen`. Registered on sc.glows so the
  // engine can switch it off on the pre-play frame.
  MP.glow = function (sc, layer, x, y, w, h, rgb) {
    var g = document.createElement('div');
    g.className = 'glow';
    g.style.left = x + '%'; g.style.top = y + '%';
    g.style.width = w + 'cqw'; g.style.height = h + 'cqw';
    g.style.background = 'radial-gradient(closest-side, rgba(' + rgb + ',1), rgba(' + rgb + ',0.45) 40%, rgba(' + rgb + ',0) 100%)';
    layer.appendChild(g);
    sc.glows.push(g);
    return g;
  };
  MP.put = function (el, op, scale) {
    el.style.opacity = clamp(op, 0, 1).toFixed(3);
    el.style.transform = 'translate(-50%,-50%) scale(' + (scale || 1).toFixed(3) + ')';
  };

  /* -------------------------------------------------------------- camera */
  var CAM0 = [1, 0, 0, 50, 50];   // scale, translateX %, translateY %, origin X %, origin Y %
  MP.CAM0 = CAM0;
  /* MP.cam({...}) returns the scene's cam(sc, lt). Reduced motion always returns a still camera.
   *   push   scale added over the whole scene (0.06 = 6 % closer); negative pulls back
   *   ease   'inOut' (default), 'out', 'in' or 'linear' for the push
   *   ox, oy origin of the push, % of the stage
   *   pan    {x, y} total translate in % over the scene (eased)
   *   sway   {ax, ay, fx, fy, py} gentle handheld drift: ax/ay amplitude %, fx/fy Hz, py phase
   *   shake  {t0, amp, decay, kick, kickDecay} impact at t0 s: shake amplitude % decaying over `decay` s,
   *          plus a scale kick that relaxes over `kickDecay` s
   */
  MP.cam = function (spec) {
    var ease = { inOut: easeInOut, out: easeOut, 'in': easeIn, linear: function (x) { return clamp(x, 0, 1); } }[spec.ease || 'inOut'];
    return function (sc, lt) {
      if (MP.reduced) return CAM0;
      var k = ease(lt / sc.dur), s = 1 + (spec.push || 0) * k, tx = 0, ty = 0, w = spec.sway, sh = spec.shake;
      if (spec.pan) { var pk = easeInOut(lt / sc.dur); tx += spec.pan.x * pk; ty += spec.pan.y * pk; }
      if (w) { tx += w.ax * Math.sin(TAU * w.fx * lt); ty += w.ay * Math.sin(TAU * w.fy * lt + (w.py || 0)); }
      if (sh) {
        var tp = lt - sh.t0;
        if (tp > 0) {
          var A = sh.amp * Math.exp(-tp / sh.decay);
          tx += A * (Math.sin(TAU * 13 * tp) + 0.5 * Math.sin(TAU * 23 * tp + 1.3));
          ty += A * 0.8 * (Math.sin(TAU * 11 * tp + 0.7) + 0.5 * Math.sin(TAU * 29 * tp));
          s += (sh.kick || 0) * Math.exp(-tp / (sh.kickDecay || 0.28));
        }
      }
      return [s, tx, ty, spec.ox == null ? 50 : spec.ox, spec.oy == null ? 50 : spec.oy];
    };
  };

  /* ------------------------------------------------------ police / alarm */
  var RED = '255,40,50', BLUE = '50,110,255';
  MP.RED = RED; MP.BLUE = BLUE;
  /* MP.lightbar(sc, layer, spec): alternating red/blue emergency lights built from glows.
   *   spec.hz      alternation rate, capped at 2.5 (default 2.2)
   *   spec.lights  [{x, y, w, h, rgb, phase, max}]  x,y % of stage, w,h cqw, phase 0 or 0.5 (cycles), max opacity 0..1
   * Returns {update(lt, level)}. level 0..1 scales everything (use it to fade the lights in or out).
   * Reduced motion: a steady dim wash, no alternation.                                                       */
  MP.lightbar = function (sc, layer, spec) {
    var hz = Math.min(spec.hz || 2.2, 2.5);
    var items = spec.lights.map(function (l) {
      return { el: MP.glow(sc, layer, l.x, l.y, l.w, l.h || l.w, l.rgb || RED), phase: l.phase || 0, max: l.max == null ? 0.6 : l.max };
    });
    return {
      update: function (lt, level) {
        level = level == null ? 1 : level;
        for (var i = 0; i < items.length; i++) {
          var it = items[i], k = MP.reduced ? 0.35 : MP.pulse(lt + it.phase / hz, hz, 0.5, 0.2);
          MP.put(it.el, level * it.max * k, 0.9 + 0.2 * k);
        }
      }
    };
  };
  /* MP.beacon(sc, layer, spec): rotating alarm beacon. spec {x, y, w, rgb}; x,y % of stage, w cqw.
   * Returns {update(lt, level)}. The beam sweeps at under one turn per second. Reduced motion: steady glow. */
  MP.beacon = function (sc, layer, spec) {
    var rgb = spec.rgb || RED, w = spec.w;
    var core = MP.glow(sc, layer, spec.x, spec.y, w, w, rgb);
    var beam = MP.add(layer, 'beam',
      'position:absolute;left:' + spec.x + '%;top:' + spec.y + '%;width:' + (w * 3) + 'cqw;height:' + (w * 3) + 'cqw;margin:' + (-w * 1.5) + 'cqw 0 0 ' + (-w * 1.5) + 'cqw;' +
      'border-radius:50%;mix-blend-mode:screen;opacity:0;pointer-events:none;' +
      'background:conic-gradient(from 0deg,rgba(' + rgb + ',0) 0deg,rgba(' + rgb + ',.55) 22deg,rgba(' + rgb + ',0) 52deg,rgba(' + rgb + ',0) 360deg);' +
      '-webkit-mask-image:radial-gradient(circle,#000 15%,transparent 70%);mask-image:radial-gradient(circle,#000 15%,transparent 70%)');
    return {
      update: function (lt, level) {
        level = level == null ? 1 : level;
        if (MP.reduced) { MP.put(core, 0.5 * level, 1); beam.style.opacity = '0'; return; }
        MP.put(core, level * (0.5 + 0.4 * (0.5 + 0.5 * Math.sin(TAU * 1.1 * lt))), 1);
        beam.style.opacity = (0.8 * level).toFixed(3);
        beam.style.transform = 'rotate(' + ((lt * 300) % 360).toFixed(1) + 'deg)';
      }
    };
  };

  /* ------------------------------------------------------ screen overlays */
  // Typed code feed. rect {left,top,width,height} %. opts {theme:'red'|'blue', title (trusted constant HTML), css, maxLines}.
  // update(lt, lines, cps): lines is [{t, s}], t = seconds into the scene when that line starts typing.
  MP.codeScreen = function (layer, rect, opts) {
    opts = opts || {};
    var el = MP.box(layer, rect, 'screen code ' + (opts.theme || 'red'), opts.css || '');
    if (opts.title) { var h = document.createElement('strong'); h.innerHTML = opts.title; el.appendChild(h); }
    var pre = document.createElement('pre'); el.appendChild(pre);
    if (opts.font) pre.style.font = opts.font;
    if (opts.color) pre.style.color = opts.color;
    var last = null;
    return {
      el: el,
      update: function (lt, lines, cps) {
        cps = cps || 30;
        var out = [], i, n;
        for (i = 0; i < lines.length; i++) {
          n = clamp(Math.floor((lt - lines[i].t) * cps), 0, lines[i].s.length);
          if (n > 0) out.push(lines[i].s.slice(0, n));
        }
        if (opts.maxLines && out.length > opts.maxLines) out = out.slice(-opts.maxLines);
        var text = out.join('\n');
        if (text !== last) { last = text; pre.textContent = text; }
        el.classList.toggle('caret-on', MP.reduced || Math.floor(lt * 3.2) % 2 === 0);
      }
    };
  };

  // The synthetic Bank Lab website shown on the large display. All text is a constant: no real data.
  var SITE_HTML =
    '<div class="site-top"><span class="site-logo">RH</span><span class="site-name">Bank Lab</span><span class="pill">ONLINE</span>' +
    '<span class="site-nav"><span>Accounts</span><span>Transfers</span><span>Cards</span><span>Support</span></span></div>' +
    '<div class="site-body">' +
      '<div class="site-hero"><div class="site-h">Welcome back</div>' +
        '<div class="site-sub">Demo portal · synthetic accounts</div>' +
        '<div class="site-field">Username</div><div class="site-field">••••••••</div>' +
        '<div class="site-btn">Sign in</div></div>' +
      '<div class="site-panel"><div class="site-ph">Recent activity</div>' +
        '<div class="site-row"><span>Payroll deposit</span><span>+$2,400.00</span></div>' +
        '<div class="site-row"><span>Utilities</span><span>−$86.12</span></div>' +
        '<div class="site-row"><span>Savings transfer</span><span>−$500.00</span></div>' +
        '<div class="site-loading"><span class="spinner"></span><span class="site-notice">Slow response — retrying…</span></div></div>' +
    '</div>' +
    '<div class="site-foot"><span>Response time <b class="rt ok">112 ms</b></span><span>Target: bank-lab-demo</span>' +
    '<span class="site-fx">FIXTURE · SIMULATED TRAFFIC</span></div>';

  /* MP.siteScreen(layer, rect) returns {el, set(state)}. state fields (all optional):
   *   ms        response time in milliseconds (text and colour follow it)
   *   spinner   0..1 opacity of the loading spinner (it spins by `spin` degrees)
   *   notice    0..1 opacity of the "Slow response" line
   *   rows      array of 3 opacities for the activity rows
   *   pill      'ONLINE' (default) or 'OFFLINE'
   *   glitch    0..1 horizontal tear while it dies (a short, one-off effect)
   *   dark      0..1 black cover; at 1 the overlay hides itself so the art's own black screen shows       */
  MP.siteScreen = function (layer, rect) {
    var el = MP.box(layer, rect, 'screen site');
    el.innerHTML = SITE_HTML;
    var rt = el.querySelector('.rt'), spinner = el.querySelector('.spinner'), notice = el.querySelector('.site-notice');
    var rows = el.querySelectorAll('.site-row'), pill = el.querySelector('.pill'), body = el.querySelector('.site-body');
    var cover = MP.add(el, 'site-cover', 'position:absolute;inset:0;background:#000;opacity:0;pointer-events:none');
    return {
      el: el,
      set: function (s) {
        var i;
        if (s.ms != null) {
          var txt = s.ms < 1000 ? Math.round(s.ms) + ' ms' : (s.ms / 1000).toFixed(1) + ' s';
          if (rt.textContent !== txt) rt.textContent = txt;
          rt.className = 'rt ' + (s.ms < 400 ? 'ok' : s.ms < 1500 ? 'warn' : 'bad');
        }
        if (s.spinner != null) spinner.style.opacity = s.spinner.toFixed(3);
        if (s.spin != null) spinner.style.transform = 'rotate(' + (s.spin % 360).toFixed(1) + 'deg)';
        if (s.notice != null) notice.style.opacity = s.notice.toFixed(3);
        if (s.rows) for (i = 0; i < rows.length; i++) rows[i].style.opacity = s.rows[i].toFixed(3);
        if (s.pill) {
          if (pill.textContent !== s.pill) pill.textContent = s.pill;
          pill.style.background = s.pill === 'ONLINE' ? '' : '#c8102e';
        }
        if (s.glitch != null) body.style.transform = s.glitch > 0 ? 'translateX(' + (Math.sin(s.glitch * 97) * s.glitch * 1.4).toFixed(2) + 'cqw)' : '';
        if (s.dark != null) { cover.style.opacity = s.dark.toFixed(3); el.style.visibility = s.dark >= 1 ? 'hidden' : 'visible'; }
      }
    };
  };

  /* ------------------------------------------------------ canvas emitters */
  // Each emitter is built once in a scene's setup() and drawn every frame from draw(). Options mirror what
  // scenes 02-04 use. Pass `rng` (a shared MP.rng stream) or `seed`. They draw with MP.ctx at MP.cw pixels.
  var fx = MP.fx = {};
  function stream(o) { return o.rng || MP.rng(o.seed || 1); }
  function between(r, range) { return range[0] + r() * (range[1] - range[0]); }

  function poly(x, y, rad, n, rot, col, a) {
    var ctx = MP.ctx, cw = MP.cw;
    ctx.globalAlpha = a; ctx.fillStyle = col; ctx.beginPath();
    for (var k = 0; k < n; k++) {
      var an = rot + k * TAU / n, rr = rad * (k % 2 ? 0.62 : 1);
      var px = (x + Math.cos(an) * rr) * cw, py = (y + Math.sin(an) * rr) * cw;
      if (k) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    }
    ctx.closePath(); ctx.fill();
  }
  function star(x, y, size, a, col) {
    var ctx = MP.ctx, cw = MP.cw, px = x * cw, py = y * cw, s = size * cw;
    ctx.globalAlpha = a; ctx.fillStyle = col || 'rgb(255,246,220)';
    ctx.beginPath();
    ctx.moveTo(px - s, py); ctx.lineTo(px, py - s * 0.14); ctx.lineTo(px + s, py); ctx.lineTo(px, py + s * 0.14); ctx.closePath();
    ctx.moveTo(px, py - s); ctx.lineTo(px + s * 0.14, py); ctx.lineTo(px, py + s); ctx.lineTo(px - s * 0.14, py); ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = a * 0.5;
    ctx.beginPath(); ctx.arc(px, py, s * 0.22, 0, TAU); ctx.fill();
  }

  /* fx.debris: rubble thrown from an impact, falling and landing. draw(tp) with tp = seconds since the impact.
   *   n, x [lo,hi] and y [lo,hi] origin (x in widths, y as fraction of height), angle [lo,hi] degrees (-90 is up),
   *   speed, ground [lo,hi] landing line (fraction of height), tau drag, size [lo,hi], life [lo,hi], delay (max s)
   * Skipped entirely in reduced motion.                                                                           */
  fx.debris = function (o) {
    var r = stream(o), G = MP.G, A = MP.ASPECT, list = [], i;
    var pal = o.palette || ['#e6d3ac', '#d4c4a0', '#b9a98a', '#8f8576', '#3a2418', '#5a3822', '#f0dcb4'];
    var angle = o.angle || [-170, -20], speed = o.speed || [0.18, 0.80], yr = o.y || [0.52, 0.66], gr = o.ground || [0.84, 0.95];
    var xr = o.x || [0.60, 0.70], tau = o.tau || [0.9, 1.5], size = o.size || [0.003, 0.011], life = o.life || [2.0, 3.9], delay = o.delay == null ? 0.06 : o.delay;
    for (i = 0; i < o.n; i++) {
      var a = (angle[0] + r() * (angle[1] - angle[0])) * Math.PI / 180;
      var sp = speed[0] + r() * (speed[1] - speed[0]);
      var y0 = (yr[0] + r() * (yr[1] - yr[0])) * A;
      var gnd = (gr[0] + r() * (gr[1] - gr[0])) * A;
      var vy = Math.sin(a) * sp, disc = vy * vy - 2 * G * (y0 - gnd);
      list.push({
        x0: xr[0] + r() * (xr[1] - xr[0]), y0: y0, vx: Math.cos(a) * sp, vy: vy, gnd: gnd,
        tl: (-vy + Math.sqrt(disc)) / G, tau: tau[0] + r() * (tau[1] - tau[0]), n: 3 + Math.floor(r() * 3),
        rr: size[0] + Math.pow(r(), 2) * (size[1] - size[0]), rot0: r() * TAU, spin: (r() - 0.5) * 14,
        col: pal[Math.floor(r() * pal.length)], life: life[0] + r() * (life[1] - life[0]), delay: r() * delay
      });
    }
    return {
      draw: function (tp) {
        if (MP.reduced) return;
        for (var k = 0; k < list.length; k++) {
          var d = list[k], t = tp - d.delay;
          if (t < 0 || t > d.life) continue;
          var tt = Math.min(t, d.tl + 0.12);
          var x = d.x0 + d.vx * d.tau * (1 - Math.exp(-tt / d.tau));
          var y = t < d.tl ? d.y0 + d.vy * t + 0.5 * G * t * t : d.gnd;
          var al = t > d.life - 0.8 ? (d.life - t) / 0.8 : 1;
          poly(x, y, d.rr, d.n, d.rot0 + d.spin * Math.min(t, d.tl), d.col, al);
        }
      }
    };
  };

  /* fx.dust: soft expanding puffs of dust or smoke. draw(tp). Dimmer (x0.6) in reduced motion, never skipped.
   *   n, x [lo,hi], y [lo,hi] origin, rgb 'r,g,b', scale (size multiplier), alpha (opacity multiplier)          */
  fx.dust = function (o) {
    var r = stream(o), A = MP.ASPECT, list = [], i, rgb = o.rgb || '224,208,178', sc = o.scale || 1, am = o.alpha || 1;
    var xr = o.x || [0.58, 0.72], yr = o.y || [0.50, 0.66];
    for (i = 0; i < o.n; i++) {
      list.push({
        x0: xr[0] + r() * (xr[1] - xr[0]), y0: (yr[0] + r() * (yr[1] - yr[0])) * A,
        dx: (r() - 0.4) * 0.05, dy: -(0.015 + r() * 0.03),
        r0: (0.02 + r() * 0.025) * sc, gr: (0.025 + r() * 0.035) * sc, a0: (0.16 + r() * 0.2) * am, life: 2.6 + r() * 1.6, delay: r() * 0.25
      });
    }
    return {
      draw: function (tp) {
        var ctx = MP.ctx, cw = MP.cw;
        for (var k = 0; k < list.length; k++) {
          var d = list[k], t = tp - d.delay;
          if (t < 0 || t > d.life) continue;
          var rad = (d.r0 + d.gr * Math.pow(t, 0.75)) * cw;
          var a = d.a0 * (1 - Math.exp(-t / 0.12)) * (1 - t / d.life) * (MP.reduced ? 0.6 : 1);
          var cx = (d.x0 + d.dx * t) * cw, cy = (d.y0 + d.dy * t) * cw;
          var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
          g.addColorStop(0, 'rgba(' + rgb + ',' + a.toFixed(3) + ')');
          g.addColorStop(0.55, 'rgba(' + rgb + ',' + (a * 0.55).toFixed(3) + ')');
          g.addColorStop(1, 'rgba(' + rgb + ',0)');
          ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, TAU); ctx.fill();
        }
      }
    };
  };

  /* fx.sparks: short bright streaks thrown from a point. draw(tp). Skipped in reduced motion.
   *   n, x [lo,hi], y [lo,hi] origin, angle, speed, spread (max start delay s), life [lo,hi]                      */
  fx.sparks = function (o) {
    var r = stream(o), A = MP.ASPECT, G = MP.G, list = [], i;
    var angle = o.angle || [-160, -20], speed = o.speed || [0.35, 1.25], xr = o.x || [0.63, 0.70], yr = o.y || [0.55, 0.65], life = o.life || [0.35, 1.05];
    var spread = o.spread == null ? 0.4 : o.spread;
    for (i = 0; i < o.n; i++) {
      var a = (angle[0] + r() * (angle[1] - angle[0])) * Math.PI / 180, sp = speed[0] + r() * (speed[1] - speed[0]);
      list.push({ x0: xr[0] + r() * (xr[1] - xr[0]), y0: (yr[0] + r() * (yr[1] - yr[0])) * A, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, t0: r() * spread, life: life[0] + r() * (life[1] - life[0]) });
    }
    return {
      draw: function (tp) {
        if (MP.reduced) return;
        var ctx = MP.ctx, cw = MP.cw, G2 = G;
        ctx.globalCompositeOperation = 'lighter';
        ctx.lineWidth = Math.max(1, cw * 0.0014); ctx.lineCap = 'round';
        for (var k = 0; k < list.length; k++) {
          var s = list[k], t = tp - s.t0;
          if (t < 0 || t > s.life) continue;
          var x = s.x0 + s.vx * t, y = s.y0 + s.vy * t + 0.5 * G2 * t * t, vyNow = s.vy + G2 * t;
          ctx.globalAlpha = 1 - t / s.life;
          ctx.strokeStyle = 'rgb(255,' + (150 + Math.floor(80 * (1 - t / s.life))) + ',70)';
          ctx.beginPath(); ctx.moveTo(x * cw, y * cw); ctx.lineTo((x - s.vx * 0.03) * cw, (y - vyNow * 0.03) * cw); ctx.stroke();
        }
        ctx.globalCompositeOperation = 'source-over';
      }
    };
  };

  /* fx.rain: slanted rain streaks clipped to a box. draw(lt, mul) with mul an optional opacity multiplier.
   *   box {x0,x1,y0,y1} in canvas units (use MP.rectU), n, speed [lo,hi] widths/s, len [lo,hi], slant,
   *   alpha [lo,hi], width [lo,hi] px, rgb. Reduced motion slows it to 40 %.                                     */
  fx.rain = function (o) {
    var r = stream(o), b = o.box, list = [], i, slant = o.slant == null ? 0.22 : o.slant, rgb = o.rgb || '205,222,255';
    var speed = o.speed || [0.5, 1.0], len = o.len || [0.018, 0.048], alpha = o.alpha || [0.25, 0.6], wd = o.width || [1, 1.8];
    for (i = 0; i < o.n; i++) {
      list.push({ x: r(), sp: speed[0] + r() * (speed[1] - speed[0]), len: len[0] + r() * (len[1] - len[0]), ph: r(), a: alpha[0] + r() * (alpha[1] - alpha[0]), w: wd[0] + r() * (wd[1] - wd[0]) });
    }
    return {
      draw: function (lt, mul) {
        var ctx = MP.ctx, cw = MP.cw, k = MP.reduced ? 0.4 : 1, H = b.y1 - b.y0;
        ctx.save();
        ctx.beginPath(); ctx.rect(b.x0 * cw, b.y0 * cw, (b.x1 - b.x0) * cw, H * cw); ctx.clip();
        ctx.lineCap = 'round'; ctx.strokeStyle = 'rgb(' + rgb + ')';
        for (var q = 0; q < list.length; q++) {
          var s = list[q], P = H + s.len;
          var y = b.y0 + MP.wrap(s.ph * P + lt * s.sp * k, 0, P) - s.len;
          var x = b.x0 - 0.03 + s.x * (b.x1 - b.x0 + 0.06) + slant * (y - (b.y0 + b.y1) * 0.5);
          ctx.globalAlpha = s.a * (mul == null ? 1 : mul); ctx.lineWidth = s.w * Math.max(1, cw / 1100);
          ctx.beginPath(); ctx.moveTo((x - slant * s.len) * cw, (y - s.len) * cw); ctx.lineTo(x * cw, y * cw); ctx.stroke();
        }
        ctx.restore();
      }
    };
  };

  /* fx.glints: four-point sparkles that twinkle in place. draw(lt).
   *   regions [{n, x:[lo,hi], y:[lo,hi]}] (y as fraction of height), per [lo,hi] seconds, size [lo,hi], rgb         */
  fx.glints = function (o) {
    var r = stream(o), A = MP.ASPECT, list = [], per = o.per || [1.5, 3.5], size = o.size || [0.008, 0.020];
    o.regions.forEach(function (g) {
      for (var k = 0; k < g.n; k++) list.push({ x: g.x[0] + r() * (g.x[1] - g.x[0]), y: (g.y[0] + r() * (g.y[1] - g.y[0])) * A, per: per[0] + r() * (per[1] - per[0]), ph: r(), s: size[0] + r() * (size[1] - size[0]) });
    });
    return {
      draw: function (lt) {
        var ctx = MP.ctx;
        ctx.globalCompositeOperation = 'lighter';
        for (var k = 0; k < list.length; k++) {
          var g = list[k], b = Math.pow(Math.max(0, Math.sin(TAU * ((lt / g.per + g.ph) % 1))), 12);
          if (b < 0.02) continue;
          star(g.x, g.y, g.s * (0.6 + 0.6 * b), b * (MP.reduced ? 0.5 : 0.95), o.color);
        }
        ctx.globalCompositeOperation = 'source-over';
      }
    };
  };

  /* fx.motes: slow drifting dust motes lit by the room. draw(lt).
   *   n, x [lo,hi], y [lo,hi] (y as fraction of height), rgb, alpha multiplier                                      */
  fx.motes = function (o) {
    var r = stream(o), A = MP.ASPECT, list = [], xr = o.x || [0.04, 0.50], yr = o.y || [0.10, 0.90], am = o.alpha || 1, rgb = o.rgb || '255,225,170';
    for (var i = 0; i < o.n; i++) {
      list.push({ x0: xr[0] + r() * (xr[1] - xr[0]), y0: (yr[0] + r() * (yr[1] - yr[0])) * A, vx: (r() - 0.3) * 0.01, vy: -(0.004 + r() * 0.01), a: (0.2 + r() * 0.3) * am, r: 0.0016 + r() * 0.003, per: 2 + r() * 3, ph: r() });
    }
    var wx = [xr[0] - 0.02, xr[1] + 0.02], wy = [(yr[0] - 0.07) * A, (yr[1] + 0.05) * A];
    return {
      draw: function (lt) {
        var ctx = MP.ctx, cw = MP.cw;
        ctx.globalCompositeOperation = 'lighter';
        ctx.fillStyle = 'rgb(' + rgb + ')';
        for (var k = 0; k < list.length; k++) {
          var m = list[k], x = MP.wrap(m.x0 + m.vx * lt, wx[0], wx[1]), y = MP.wrap(m.y0 + m.vy * lt, wy[0], wy[1]);
          ctx.globalAlpha = m.a * (0.55 + 0.45 * Math.sin(TAU * (lt / m.per + m.ph)));
          ctx.beginPath(); ctx.arc(x * cw, y * cw, m.r * cw, 0, TAU); ctx.fill();
        }
        ctx.globalCompositeOperation = 'source-over';
      }
    };
  };

  /* fx.ripples: rings spreading on wet ground. draw(lt).
   *   box {x0,x1,y0,y1} canvas units (MP.rectU), n, rmax (widths), flat (ring height / width, default 0.3),
   *   period [lo,hi] s, alpha [lo,hi], rgb. Reduced motion halves the speed.                                        */
  fx.ripples = function (o) {
    var r = stream(o), b = o.box, list = [], per = o.period || [0.9, 1.7], al = o.alpha || [0.15, 0.4], rgb = o.rgb || '220,235,255';
    for (var i = 0; i < o.n; i++) list.push({ x: b.x0 + r() * (b.x1 - b.x0), y: b.y0 + r() * (b.y1 - b.y0), per: per[0] + r() * (per[1] - per[0]), ph: r(), a: al[0] + r() * (al[1] - al[0]) });
    var rmax = o.rmax || 0.035, flat = o.flat || 0.3;
    return {
      draw: function (lt) {
        var ctx = MP.ctx, cw = MP.cw, k = MP.reduced ? 0.5 : 1;
        ctx.lineWidth = Math.max(1, cw / 1300);
        ctx.strokeStyle = 'rgb(' + rgb + ')';
        for (var q = 0; q < list.length; q++) {
          var s = list[q], p = ((lt * k / s.per + s.ph) % 1 + 1) % 1;
          ctx.globalAlpha = s.a * Math.pow(1 - p, 1.5);
          ctx.beginPath(); ctx.ellipse(s.x * cw, s.y * cw, rmax * p * cw, rmax * p * flat * cw, 0, 0, TAU); ctx.stroke();
        }
      }
    };
  };

  /* fx.splash: a spray of water droplets thrown from a point. draw(tp), tp = seconds since it starts.
   *   n, x, y origin (x in widths, y as fraction of height), jitter, angle, speed, size [lo,hi], life [lo,hi], rgb
   * Skipped in reduced motion.                                                                                      */
  fx.splash = function (o) {
    var r = stream(o), A = MP.ASPECT, list = [], angle = o.angle || [-150, -30], speed = o.speed || [0.12, 0.45], size = o.size || [0.0015, 0.0035], life = o.life || [0.5, 1.1];
    var jit = o.jitter == null ? 0.01 : o.jitter, rgb = o.rgb || '210,230,255';
    for (var i = 0; i < o.n; i++) {
      var a = (angle[0] + r() * (angle[1] - angle[0])) * Math.PI / 180, sp = speed[0] + r() * (speed[1] - speed[0]);
      list.push({ x0: o.x + (r() - 0.5) * jit * 2, y0: o.y * A + (r() - 0.5) * jit, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, s: size[0] + r() * (size[1] - size[0]), life: life[0] + r() * (life[1] - life[0]), d: r() * (o.delay == null ? 0.12 : o.delay) });
    }
    return {
      draw: function (tp) {
        if (MP.reduced) return;
        var ctx = MP.ctx, cw = MP.cw;
        ctx.fillStyle = 'rgb(' + rgb + ')';
        for (var k = 0; k < list.length; k++) {
          var d = list[k], t = tp - d.d;
          if (t < 0 || t > d.life) continue;
          var x = d.x0 + d.vx * t, y = d.y0 + d.vy * t + 0.5 * MP.G * t * t;
          ctx.globalAlpha = (1 - t / d.life) * 0.9;
          ctx.beginPath(); ctx.arc(x * cw, y * cw, d.s * cw, 0, TAU); ctx.fill();
        }
      }
    };
  };

  MP.fx.star = star;   // for scene-specific sparkle drawing
})();
