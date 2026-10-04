/* Scene 07, "Fill the bag" (4.5 s). 07_inside_vault_money-r2.png
 * Moves: the warm strip lights breathe (each on its own phase, one glow canvas), their reflections on the glossy floor
 *        breathe and shimmer with them, gold glints twinkle on measured highlights of the bars and cash bundles,
 *        dust motes drift up through the light, slow push toward the robber with a small handheld sway.
 * Does not move: the robber, the bag, the cash and the gold (baked into the still).
 * Deliberately not animated: anything red. The alarm is off in this scene, so the red of his sweater and its floor
 * reflection are left exactly as painted. No text, nothing live.
 *
 * Geometry measured from the PNG (1672x941, bright-blob search, about +-2 px). Everything below is in art pixels and
 * is converted when it is drawn:
 *   horizontal strips (shelf lights)  10, slanted ones follow the shelf perspective
 *   vertical strips (pillar lights)   13, x = 299..307, 547..551, 916, 1339..1342, 1476..1478
 *   floor streaks                     7, the strips' reflections, x = 300, 355, 547, 698, 1199, 1353, 1480
 *   cash bundles on the floor         x 480-1345, y 715-820                                               */
(function () {
  'use strict';
  var MP = window.MP, W = 1672, H = 941, TAU = Math.PI * 2;
  var AMBER = '255,176,64', PALE = '255,226,150', GOLD = '255,206,110';

  // [x1, y1, x2, y2, halo radius, phase]; the glow follows the segment, so slanted strips stay registered.
  var STRIPS = [
    [62, 64, 118, 90, 26, 0.00],   [72, 300, 124, 319, 26, 0.31],  [328, 189, 421, 226, 28, 0.62], [323, 368, 410, 391, 28, 0.93],
    [676, 84, 784, 89, 26, 0.17],  [688, 257, 800, 261, 26, 0.48], [678, 426, 790, 429, 26, 0.79],
    [1072, 59, 1170, 59, 26, 0.41], [1078, 240, 1194, 240, 26, 0.72], [1096, 415, 1200, 415, 26, 0.03],
    [307, 0, 307, 40, 24, 0.22],   [303, 160, 303, 245, 24, 0.53], [299, 392, 299, 459, 24, 0.84],
    [551, 124, 551, 173, 24, 0.36], [549, 276, 549, 328, 24, 0.67], [547, 438, 547, 491, 24, 0.98],
    [916, 117, 916, 168, 24, 0.58],
    [1339, 78, 1339, 131, 24, 0.09], [1340, 244, 1340, 299, 24, 0.40], [1342, 415, 1342, 470, 24, 0.71],
    [1476, 0, 1476, 40, 24, 0.27], [1476, 171, 1476, 236, 24, 0.58], [1478, 386, 1478, 456, 24, 0.89]
  ];
  // Floor streaks: [x, y1, y2, half width, phase of the strip they mirror]
  var FLOOR = [
    [300, 826, 936, 17, 0.84], [355, 798, 850, 19, 0.93], [547, 828, 912, 14, 0.98], [698, 858, 938, 21, 0.79],
    [1199, 858, 938, 26, 0.03], [1353, 826, 938, 20, 0.71], [1480, 815, 905, 13, 0.89]
  ];
  // Glints sit on measured specular points: gold bar corners, then the wrappers and paper edges of the floor bundles.
  var SPOTS = [
    [723, 111], [772, 117], [839, 145], [632, 196], [773, 204], [884, 206],           // gold, top centre
    [1142, 114], [1011, 159], [976, 193], [1169, 182],                                // gold, top right
    [191, 176], [188, 215], [254, 45], [341, 77], [329, 216], [350, 267],             // gold, left shelves
    [655, 298], [699, 309], [749, 319], [606, 381], [781, 375],                       // gold, behind the robber
    [1423, 285], [1417, 475], [1570, 212], [1149, 312],                               // gold and cash, right
    [608, 726], [968, 758], [1286, 726]                                               // cash bundles on the floor
  ];

  var r = MP.rng(20260707);
  var glints = SPOTS.map(function (p) {
    return { x: p[0] / W, y: p[1] / W, per: 1.9 + r() * 1.8, ph: r(), s: 0.009 + r() * 0.011 };
  });
  var motes = MP.fx.motes({ rng: r, n: 26, x: [0.03, 0.97], y: [0.06, 0.86] });

  // A soft halo around a line segment, rendered once into its own small canvas (alpha falls off with distance).
  function haloTex(ax, ay, bx, by, R, rgb) {
    var x0 = Math.floor(Math.min(ax, bx) - R), y0 = Math.floor(Math.min(ay, by) - R);
    var w = Math.ceil(Math.abs(bx - ax) + 2 * R) + 1, h = Math.ceil(Math.abs(by - ay) + 2 * R) + 1;
    var c = document.createElement('canvas'); c.width = w; c.height = h;
    var cx = c.getContext('2d'), im = cx.createImageData(w, h), d = im.data;
    var dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy || 1, c3 = rgb.split(','), i = 0, x, y;
    for (y = 0; y < h; y++) for (x = 0; x < w; x++) {
      var px = x0 + x - ax, py = y0 + y - ay, t = Math.max(0, Math.min(1, (px * dx + py * dy) / L2));
      var ex = px - t * dx, ey = py - t * dy, k = 1 - Math.sqrt(ex * ex + ey * ey) / R;
      k = k > 0 ? k * k : 0;
      d[i] = +c3[0]; d[i + 1] = +c3[1]; d[i + 2] = +c3[2]; d[i + 3] = Math.round(255 * k);
      i += 4;
    }
    cx.putImageData(im, 0, 0);
    return { c: c, x: x0, y: y0 };
  }
  function put(cx, t, a) { cx.globalAlpha = a; cx.drawImage(t.c, t.x, t.y); }
  // Slow breath in 0..1 (about 0.45 Hz, a little faster ripple on top); every strip has its own phase.
  function breath(lt, ph) { return 0.5 + 0.5 * (0.82 * Math.sin(TAU * (0.45 * lt + ph)) + 0.18 * Math.sin(TAU * (1.15 * lt + 2.3 * ph))); }

  MP.register({
    id: 'money',
    setup: function (sc, L) {
      var g = sc.g = {};
      var cv = document.createElement('canvas');
      cv.width = W; cv.height = H;
      cv.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;mix-blend-mode:screen;pointer-events:none;opacity:0';
      L.appendChild(cv);
      sc.glows.push(cv);                       // the engine hides it on the pre-play frame like any glow
      g.cv = cv; g.cx = cv.getContext('2d');
      // each light is a tight halo plus a wide faint one, so the swell reaches the shelves and bars around it
      g.strips = STRIPS.map(function (s) {
        return { tight: haloTex(s[0], s[1], s[2], s[3], s[4], PALE), wide: haloTex(s[0], s[1], s[2], s[3], s[4] * 2.8, AMBER), ph: s[5] };
      });
      g.floor = FLOOR.map(function (f) {
        return { tight: haloTex(f[0], f[1], f[0], f[2], f[3], GOLD), wide: haloTex(f[0], f[1], f[0], f[2], f[3] * 2.6, GOLD), ph: f[4] };
      });
    },
    cam: MP.cam({ push: 0.06, ox: 58, oy: 52, sway: { ax: 0.08, ay: 0.06, fx: 0.6, fy: 0.8, py: 0.4 } }),
    dom: function (sc, lt) {
      var g = sc.g, cx = g.cx, k = MP.reduced ? 0.4 : 1, i, s, b;
      g.cv.style.opacity = '1';
      cx.setTransform(1, 0, 0, 1, 0, 0);
      cx.clearRect(0, 0, W, H);
      cx.globalCompositeOperation = 'lighter';
      for (i = 0; i < g.strips.length; i++) {
        s = g.strips[i]; b = breath(lt, s.ph);
        put(cx, s.wide, 0.05 + 0.11 * (0.5 + k * (b - 0.5)));
        put(cx, s.tight, 0.04 + 0.42 * (0.5 + k * (b - 0.5)));
      }
      for (i = 0; i < g.floor.length; i++) {
        s = g.floor[i]; b = breath(lt, s.ph);
        // follows its strip's breath, plus a faster, smaller ripple of its own
        put(cx, s.wide, 0.03 + 0.09 * (0.5 + k * (b - 0.5)));
        put(cx, s.tight, 0.06 + 0.34 * (0.5 + k * (b - 0.5)) + 0.05 * k * Math.sin(TAU * 0.9 * lt + s.ph * 9));
      }
      cx.globalCompositeOperation = 'source-over';
      cx.globalAlpha = 1;
    },
    draw: function (sc, lt) {
      var ctx = MP.ctx, i, g, b;
      motes.draw(lt);
      ctx.globalCompositeOperation = 'lighter';
      for (i = 0; i < glints.length; i++) {
        g = glints[i];
        b = Math.pow(Math.max(0, Math.sin(TAU * ((lt / g.per + g.ph) % 1))), 12);
        if (b < 0.02) continue;
        MP.fx.star(g.x, g.y, g.s * (0.6 + 0.6 * b), b * (MP.reduced ? 0.5 : 0.95), 'rgb(255,244,214)');
      }
      ctx.globalCompositeOperation = 'source-over';
    }
  });
})();
