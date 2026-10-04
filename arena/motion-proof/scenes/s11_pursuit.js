/* Scene 11, "The chase, Blue rebuilds" (13.0 s). 11_blue_pursuit.png
 * Moves: the Blue feed typing on the big dash display (tilted onto the glass, wakes with one small dip), the cabin
 *        light bar (roof and dash strip, red and blue alternating at 2.2 Hz), the red car's tail lights and their
 *        road reflections breathing, dial glow, rain on the windscreen, sparkle on the wet road, driving sway and a
 *        slow push toward the red car.
 * Does not move: the red car, the officer and the dashboard (baked into the still).
 * Deliberately not animated: no alarm or beacon, no street-lamp strobing, and nothing on the display but the six
 *        fixture lines: no progress bar, percentage or success text ("health.check" stays pending until scene 12).
 *
 * Geometry, measured from the PNG (1672x941): the display glass is a trapezoid (left edge leans 6.4 degrees, top
 * and bottom slope 1.8 and 3.3 degrees), so the overlay gets a real perspective matrix, not a skew. Each edge was fitted
 * through 8 to 11 threshold crossings of the black bezel ring (residual 0.3 px; the top edge is slightly curved, 1.6 px).
 * Lights, tail lights and the check were located with tools\measure.ps1 and confirmed on zoomed crops. */
(function () {
  'use strict';
  var MP = window.MP;

  /* Scene 12 calls this definition's hooks at T=13+lt to share geometry and weather without duplication. */
  var DUR11 = 13.0;                          // scene 11 length: scene 12 runs its clocks from here (T = lt + DUR11)
  var VIEW = { total: 19.5, push: 0.06, ox: 60, oy: 20 };       // one push over scenes 11 and 12 (13.0 + 6.5 s); origin high so the roof lights stay in frame
  var SWAY = { ax: 0.09, ay: 0.12, fx: 0.31, fy: 0.83, py: 0.9 };   // driving sway: amplitude % of stage, Hz
  // Display glass on the dash, corners TL TR BR BL in art px, inset 1.4 px from the measured bezel edge.
  var GLASS = [[921.3, 578.4], [1600.5, 600.2], [1603.4, 822.8], [898.7, 782.0]];
  var BOX = { w: 41.4, h: 12.8 };            // overlay layout size in cqw (the glass at its average size); the matrix warps it onto GLASS
  var FEED_T = [0.8, 2.6, 4.6, 6.4, 8.2, 10.0];                // when each Blue line starts typing, s
  var CPS = 30;
  var TITLE = 'BLUE / SERVICE RECOVERY <span>FIXTURE</span>';
  var BAR_HZ = 2.2;                          // cabin light bar alternation, under the 2.5 Hz limit
  // Cabin light bar: x,y % of stage, w,h cqw, phase 0 or 0.5 cycle (red and blue alternate), max opacity (0.6 cap).
  var ROOF_LIGHTS = [                        // along the top of the windscreen
    { x: 42.31, y: 2.07, w: 10.5, h: 2.6, rgb: MP.RED, phase: 0, max: 0.55 },     // red pill, art (707.5, 19.5)
    { x: 60.44, y: 1.43, w: 9.5, h: 2.4, rgb: MP.BLUE, phase: 0.5, max: 0.6 },    // blue pill, art (1010.5, 13.5)
    { x: 93.30, y: 2.34, w: 14, h: 2.8, rgb: MP.RED, phase: 0, max: 0.5 },        // red bar at the right, art (1560, 22)
    { x: 14.06, y: 5.95, w: 7.5, h: 2.4, rgb: MP.BLUE, phase: 0.5, max: 0.5 }     // blue pill on the headliner, art (235, 56)
  ];
  var DASH_LIGHTS = [                        // the strip along the base of the windscreen
    { x: 42.22, y: 56.85, w: 4.6, h: 2.0, rgb: MP.BLUE, phase: 0.5, max: 0.55 },  // art (706, 535)
    { x: 44.86, y: 56.75, w: 5.2, h: 2.0, rgb: MP.RED, phase: 0, max: 0.5 },      // art (750, 534)
    { x: 75.84, y: 59.09, w: 8.6, h: 2.2, rgb: MP.BLUE, phase: 0.5, max: 0.55 },  // art (1268, 556)
    { x: 91.87, y: 58.77, w: 10.5, h: 2.4, rgb: MP.RED, phase: 0, max: 0.55 },    // art (1536, 553)
    { x: 98.21, y: 59.09, w: 6.0, h: 2.2, rgb: MP.BLUE, phase: 0.5, max: 0.5 }    // art (1642, 556)
  ];
  var TAIL = [[56.8, 40.65], [65.97, 40.65]];                  // red car's tail lights, % of stage (art 950,382.5 and 1103,382.5)
  var REFL = [[57.0, 52.8], [65.8, 53.1]];                     // their reflections on the wet road, % of stage
  var DIALS = [[436, 664, 74], [598, 665, 70]];                // instrument dials: art px centre and glow radius

  var CSS =
    '.screen.code.pd{transform-origin:0 0;border-radius:1cqw;padding:.7cqw 1.2cqw .4cqw;box-shadow:none;' +
      'background:linear-gradient(104deg,rgb(20,37,80) 0%,rgb(15,30,67) 52%,rgb(11,22,54) 100%)}' +
    '.screen.code.pd pre{font:1.12cqw/1.36 ui-monospace,"Cascadia Mono",Consolas,monospace;color:#a9dcff;text-shadow:0 0 .55cqw rgba(110,190,255,.45)}' +
    '.screen.code.pd strong{font:700 .92cqw/1.2 system-ui,"Segoe UI",sans-serif;letter-spacing:.08em;color:#7ccbff;border-bottom:.07cqw solid #345679;padding-bottom:.25cqw;margin-bottom:.45cqw}' +
    '.screen.code.pd strong span{font-size:.74cqw;font-weight:600;letter-spacing:.14em;color:#8aa6cc}' +
    '.screen.code.pd::after{background:repeating-linear-gradient(0deg,rgba(0,0,0,.05) 0 1px,transparent 1px 3px),linear-gradient(160deg,rgba(130,180,255,.08),transparent 36%)}' +
    '.pd-ref{position:absolute;inset:0;pointer-events:none;opacity:0}' +
    '.pd-refb{background:linear-gradient(112deg,rgba(70,130,255,.22),rgba(70,130,255,0) 44%)}' +
    '.pd-refr{background:linear-gradient(248deg,rgba(255,60,70,.18),rgba(255,60,70,0) 40%)}';

  // Windscreen glass in art px (the cap, the mirror and the dash are in front of it); rain is clipped to this.
  var WIND = [[470, 62], [1100, 46], [1672, 36], [1672, 546], [1000, 546], [700, 532], [560, 518], [470, 504]];
  var MIRROR = [712, 60, 304, 108, 34];      // rear-view mirror: x, y, w, h, corner radius (art px), cut out of the rain

  // Homography from the box (0,0)-(w,h) in px onto quad q (TL TR BR BL, px), as a CSS matrix3d.
  function homography(q, w, h) {
    var x0 = q[0][0], y0 = q[0][1], x1 = q[1][0], y1 = q[1][1], x2 = q[2][0], y2 = q[2][1], x3 = q[3][0], y3 = q[3][1];
    var dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3, dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
    var den = dx1 * dy2 - dx2 * dy1, g = (dx3 * dy2 - dx2 * dy3) / den, hh = (dx1 * dy3 - dx3 * dy1) / den;
    var a = x1 - x0 + g * x1, b = x3 - x0 + hh * x3, d = y1 - y0 + g * y1, e = y3 - y0 + hh * y3;
    return 'matrix3d(' + [a / w, d / w, 0, g / w, b / h, e / h, 0, hh / h, 0, 0, 1, 0, x0, y0, 0, 1].join(',') + ')';
  }
  // Keep the overlay on the glass at any stage width (the overlay is laid out in cqw, the matrix is in px).
  function place(g, sc) {
    var st = g.stage || (g.stage = sc.layer.closest('.stage') || sc.layer.parentNode);
    var w = st.getBoundingClientRect().width;
    if (!(w > 0) || w === g.w) return;
    var k = w / 1672;
    g.w = w;
    g.screen.el.style.transform = homography(GLASS.map(function (p) { return [p[0] * k, p[1] * k]; }), BOX.w * w / 100, BOX.h * w / 100);
  }
  // Display backlight 0..1: dark, up to 0.6, one small dip to 0.2, then steady. One dip, 0.8 s, on a dark panel.
  function wake(T) {
    if (MP.reduced) return MP.smooth(0.1, 0.7, T);
    if (T < 0.30) return 0.6 * MP.smooth(0.15, 0.30, T);
    if (T < 0.45) return 0.6;
    if (T < 0.60) return MP.lerp(0.6, 0.2, MP.smooth(0.45, 0.60, T));
    return MP.lerp(0.2, 1, MP.smooth(0.60, 0.80, T));
  }
  // Soft ellipse of light on the canvas, art px. Plain alpha, so use a colour brighter than what is under it.
  function blob(x, y, rx, ry, rgb, a) {
    if (a < 0.003) return;
    var ctx = MP.ctx, k = MP.cw / 1672, gr;
    ctx.save();
    ctx.translate(x * k, y * k); ctx.scale(1, ry / rx);
    gr = ctx.createRadialGradient(0, 0, 0, 0, 0, rx * k);
    gr.addColorStop(0, 'rgba(' + rgb + ',' + a.toFixed(3) + ')');
    gr.addColorStop(0.4, 'rgba(' + rgb + ',' + (a * 0.45).toFixed(3) + ')');
    gr.addColorStop(1, 'rgba(' + rgb + ',0)');
    ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(0, 0, rx * k, 0, MP.TAU); ctx.fill();
    ctx.restore();
  }
  // Run fn with the canvas clipped to the windscreen glass minus the mirror.
  function onGlass(fn) {
    var ctx = MP.ctx, k = MP.cw / 1672, i, m = MIRROR, x = m[0] * k, y = m[1] * k, w = m[2] * k, h = m[3] * k, rr = m[4] * k;
    ctx.save();
    ctx.beginPath();
    for (i = 0; i < WIND.length; i++) ctx[i ? 'lineTo' : 'moveTo'](WIND[i][0] * k, WIND[i][1] * k);
    ctx.closePath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr); ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr); ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
    ctx.clip('evenodd');
    fn();
    ctx.restore();
  }
  /* ===== end of shared block ===== */

  var T0 = 0;                                // scene 11: T = lt

  // Same seeds and order in scene 12, so the rain and the sparkle carry on unbroken across the cut.
  var r = MP.rng(20261011);
  var rain = MP.fx.rain({ rng: r, n: 34, box: MP.rectU(26, 3, 100, 58), speed: [0.55, 0.95], len: [0.014, 0.036], slant: 0.1, alpha: [0.18, 0.45] });
  var glints = MP.fx.glints({ rng: r, regions: [{ n: 7, x: [0.27, 0.95], y: [0.46, 0.565] }], size: [0.006, 0.013], per: [2.0, 4.2] });

  MP.register({
    id: 'pursuit',
    setup: function (sc, L) {
      var g = sc.g = {};
      MP.css('pursuit-display', CSS);
      g.bar = MP.lightbar(sc, L, { hz: BAR_HZ, lights: ROOF_LIGHTS.concat(DASH_LIGHTS) });
      g.tail = TAIL.map(function (p) { return MP.glow(sc, L, p[0], p[1], 3.6, 4.8, '255,45,45'); });
      g.refl = REFL.map(function (p) { return MP.glow(sc, L, p[0], p[1], 3.0, 6.2, '255,70,50'); });
      g.screen = MP.codeScreen(L, { left: 0, top: 0, width: BOX.w, height: BOX.h / MP.ASPECT },
        { theme: 'blue', title: TITLE, css: 'visibility:hidden' });
      g.screen.el.classList.add('pd');
      g.refB = MP.add(g.screen.el, 'pd-ref pd-refb');
      g.refR = MP.add(g.screen.el, 'pd-ref pd-refr');
      g.feed = sc.blueLines.map(function (s, i) { return { t: FEED_T[i], s: s }; });
    },
    cam: function (sc, lt) {
      if (MP.reduced) return MP.CAM0;
      var T = lt + T0, k = MP.easeInOut(T / VIEW.total);
      return [1 + VIEW.push * k, SWAY.ax * Math.sin(MP.TAU * SWAY.fx * T), SWAY.ay * Math.sin(MP.TAU * SWAY.fy * T + SWAY.py), VIEW.ox, VIEW.oy];
    },
    dom: function (sc, lt) {
      var g = sc.g, T = lt + T0, el = g.screen.el, level = MP.smooth(0, 0.9, T), op = wake(T), i, tb;
      place(g, sc);
      el.style.opacity = op.toFixed(3);
      el.style.visibility = op < 0.002 ? 'hidden' : 'visible';
      g.screen.update(T, g.feed, CPS);
      g.bar.update(T, level);
      // the glossy display picks up the flashes, faintly
      g.refB.style.opacity = (MP.reduced ? 0.1 : 0.75 * level * MP.pulse(T + 0.5 / BAR_HZ, BAR_HZ, 0.5, 0.2)).toFixed(3);
      g.refR.style.opacity = (MP.reduced ? 0.08 : 0.75 * level * MP.pulse(T, BAR_HZ, 0.5, 0.2)).toFixed(3);
      for (i = 0; i < 2; i++) {
        tb = 0.5 + 0.5 * Math.sin(MP.TAU * 0.75 * T + i * 0.35);
        MP.put(g.tail[i], 0.34 + 0.2 * tb, 1 + 0.05 * tb);
        MP.put(g.refl[i], 0.2 + 0.14 * tb, 1);
      }
    },
    draw: function (sc, lt) {
      var T = lt + T0, i, a;
      for (i = 0; i < DIALS.length; i++) {
        a = 0.13 + 0.05 * Math.sin(MP.TAU * 0.4 * T + i * 1.1);
        blob(DIALS[i][0], DIALS[i][1], DIALS[i][2], DIALS[i][2], '140,215,255', a);
      }
      glints.draw(T);
      onGlass(function () { rain.draw(T); });
    }
  });
})();
