/* Scene 05, "Bank Lab goes dark" (6.5 s). 05_open_vault_matched-r3.png
 * Moves: the website on the large display (it starts exactly as scene 04 ended, tears once, flips to OFFLINE, fades
 *        to the art's black glass), the red beacon sweep, a slow red wash on the wall and floor, the vault's warm
 *        light and ceiling lamps, a few gold glints, drifting dust, one soft green pulse on the check, the keypad
 *        LED and wall strips, a slow push that continues scene 04's camera.
 * Does not move: the robber and his hand, the vault door, the check on the small display (baked into the still).
 * Deliberately not animated: the characters; the alarm gets no siren or strobe, only the beacon sweep (0.83 turns
 *        per second) and a wash that breathes at 0.83 Hz and never passes 0.16 opacity.
 *
 * Story: bank OFFLINE, alarm ON, Red "Demo action complete", Blue "Alert pending". The beacon lamp is already lit in
 * the art, so the sweep and wash fade in as the site dies (0.55 to 1.9 s), which makes the alarm the consequence.
 *
 * Screen geometry, measured from the PNG (1672x941, about +-1.5 px). The large display's glass is a keystone, not a
 * rectangle: the top edge climbs about 40 px from left to right. Both scenes 04 and 05 now fit that glass.
 * Here the website is laid out in a box and mapped onto the measured corners
 * (matrix3d, 2 px inset), so it sits inside the glass:
 *   glass corners TL (818,129)  TR (1580,89)  BR (1586,448)  BL (815,456)
 *   small display (green check) glass 1302..1552 x 526..657, circle centre (1427,590) radius 47
 *   beacon bulb (1125,34); vault opening centre (462,372), about 315 x 465; ceiling lamps (462,211) (562,275)
 *   keypad LED (1003,625)
 * The state at the cut is taken from scene 04 (rtAt copied below and evaluated at 12.0 s, rows 0.45, spinner 1,
 * notice 1, pill ONLINE), and the camera starts where scene 04's ended (scale 1.065, origin 62,45, sway phase 12 s). */
(function () {
  'use strict';
  var MP = window.MP, TAU = MP.TAU, DUR = 6.5;
  var AW = 1672, AH = 941;                                  // art size in px
  function X(px) { return px / AW * 100; }                  // art px to % of the stage width
  function Y(py) { return py / AH * 100; }                  // art px to % of the stage height

  var GLASS = [[818, 129], [1580, 89], [1586, 448], [815, 456]];     // TL, TR, BR, BL
  var INSET = [[2, 2], [-2, 2], [-2, -2], [2, -2]];
  var QUAD = GLASS.map(function (p, i) { return [p[0] + INSET[i][0], p[1] + INSET[i][1]]; });
  function dist(a, b) { return Math.sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1])); }
  var BOX_W = (dist(QUAD[0], QUAD[1]) + dist(QUAD[3], QUAD[2])) / 2;   // layout size of the website, art px
  var BOX_H = (dist(QUAD[0], QUAD[3]) + dist(QUAD[1], QUAD[2])) / 2;
  var CHECK = { x: 1427, y: 590, r: 47, clip: [1302, 526, 1552, 657] };

  // Scene 04's state at its last frame (copied from s04_vault.js so the cut is seamless).
  function rtAt(lt) {
    var q = Math.floor(lt * 8) / 8;
    var base = 108 + 3700 * Math.pow(MP.smooth(1.5, 11.5, q), 2.2);
    return base * (1 + 0.07 * Math.sin(q * 41) + 0.04 * Math.sin(q * 17 + 1));
  }
  var RT_END = rtAt(12.0), PREV = 12.0;
  var CAM_S0 = 1.065, CAM_S1 = 1.10, CAM_OX = 62, CAM_OY = 45, CAM_FX = 32, CAM_FY = 42;   // push toward the vault

  var T_TEAR = 0.50, D_TEAR = 0.40, T_PILL = 0.72, T_DARK = 0.95, D_DARK = 0.70;
  var BEACON_PERIOD = 360 / 300;                            // MP.beacon turns 300 deg/s
  var T_CHECK = 1.0;

  var r = MP.rng(50505);
  var glints = MP.fx.glints({ rng: r, per: [2.2, 4.4], size: [0.007, 0.016], regions: [
    { n: 4, x: [0.203, 0.269], y: [0.292, 0.515] },        // gold on the left shelves
    { n: 4, x: [0.290, 0.356], y: [0.345, 0.579] },        // gold on the right shelves
    { n: 2, x: [0.005, 0.075], y: [0.585, 0.715] }         // bars on the trolley
  ] });
  var motes = MP.fx.motes({ rng: r, n: 16, x: [0.10, 0.44], y: [0.14, 0.82], alpha: 0.8, rgb: '255,212,150' });

  // Projective map of a w x h box onto a quad [TL,TR,BR,BL] in px, as a CSS matrix3d (origin 0 0).
  function quadMatrix(w, h, q) {
    var x0 = q[0][0], y0 = q[0][1], x1 = q[1][0], y1 = q[1][1], x2 = q[2][0], y2 = q[2][1], x3 = q[3][0], y3 = q[3][1];
    var dx1 = x1 - x2, dx2 = x3 - x2, dy1 = y1 - y2, dy2 = y3 - y2;
    var sx = x0 - x1 + x2 - x3, sy = y0 - y1 + y2 - y3, den = dx1 * dy2 - dx2 * dy1;
    var g = (sx * dy2 - dx2 * sy) / den, hh = (dx1 * sy - sx * dy1) / den;
    var a = x1 - x0 + g * x1, b = x3 - x0 + hh * x3, d = y1 - y0 + g * y1, e = y3 - y0 + hh * y3;
    return 'matrix3d(' + [a / w, d / w, 0, g / w, b / h, e / h, 0, hh / h, 0, 0, 1, 0, x0, y0, 0, 1].map(function (v) { return v.toFixed(7); }).join(',') + ')';
  }

  function drawCheckRing(lt) {
    var p = (lt - T_CHECK) / 0.9;
    if (MP.reduced || p < 0 || p > 1) return;
    var ctx = MP.ctx, cw = MP.cw, k = cw / AW, rad = (CHECK.r + 4 + 28 * MP.easeOut(p)) * k, c = CHECK.clip;
    ctx.save();
    ctx.beginPath(); ctx.rect(c[0] * k, c[1] * k, (c[2] - c[0]) * k, (c[3] - c[1]) * k); ctx.clip();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.5 * Math.pow(1 - p, 1.6) * Math.sin(Math.PI * Math.min(1, p * 4));
    ctx.strokeStyle = 'rgb(90,255,160)'; ctx.lineWidth = Math.max(1.5, 3 * k);
    ctx.beginPath(); ctx.arc(CHECK.x * k, CHECK.y * k, rad, 0, TAU); ctx.stroke();
    ctx.restore();
  }

  MP.register({
    id: 'alarm',
    setup: function (sc, L) {
      var g = sc.g = {};
      g.spill = MP.glow(sc, L, 72.1, 29.5, 56, 34, '190,215,255');             // the website's light on the wall
      g.site = MP.siteScreen(L, { left: 0, top: 0, width: BOX_W / AW * 100, height: BOX_H / AH * 100 });
      g.site.el.style.transformOrigin = '0 0';
      g.siteKey = '';
      g.bands = ['.site-top', '.site-body', '.site-foot'].map(function (s) { return g.site.el.querySelector(s); });

      g.vault = MP.glow(sc, L, X(462), Y(372), 19, 28, '255,190,100');
      g.lampA = MP.glow(sc, L, X(462), Y(211), 6.4, 4.4, '255,226,170');
      g.lampB = MP.glow(sc, L, X(562), Y(275), 5.6, 4, '255,226,170');
      g.stripA = MP.glow(sc, L, X(776), Y(281), 2.6, 8.6, '255,176,70');
      g.stripB = MP.glow(sc, L, X(812), Y(48), 2.4, 7, '255,176,70');
      g.stripC = MP.glow(sc, L, X(1650), Y(225), 2.8, 9, '255,176,70');
      g.stripD = MP.glow(sc, L, X(1650), Y(640), 2.8, 9, '255,176,70');
      g.led = MP.glow(sc, L, X(1003), Y(625), 3.4, 3.4, '255,60,50');
      g.check = MP.glow(sc, L, X(CHECK.x), Y(CHECK.y), 15, 10.5, '60,235,130');

      g.wash = MP.glow(sc, L, X(1125), Y(150), 64, 40, '255,40,50');          // red wash on the wall
      g.floorA = MP.glow(sc, L, X(1018), Y(902), 13, 3.8, '255,40,50');        // beacon light on the glossy floor
      g.floorB = MP.glow(sc, L, X(744), Y(909), 9, 3.2, '255,40,50');
      g.beacon = MP.beacon(sc, L, { x: X(1125), y: Y(34), w: 5 });
    },

    // Continues scene 04's camera (scale 1.065 about 62,45, sway phase 12 s), then pushes slowly toward the vault.
    cam: function (sc, lt) {
      if (MP.reduced) return MP.CAM0;
      var s = CAM_S0 + (CAM_S1 - CAM_S0) * MP.easeInOut(lt / DUR), u = PREV + lt;
      var tx = 0.08 * Math.sin(TAU * 0.6 * u) + (CAM_S0 - s) * (CAM_FX - CAM_OX);
      var ty = 0.06 * Math.sin(TAU * 0.8 * u + 0.4) + (CAM_S0 - s) * (CAM_FY - CAM_OY);
      return [s, tx, ty, CAM_OX, CAM_OY];
    },

    dom: function (sc, lt) {
      var g = sc.g, put = MP.put, flick = MP.flick, red = MP.reduced;
      var dark = MP.smooth(T_DARK, T_DARK + D_DARK, lt);
      var alarm = MP.smooth(0.55, 1.9, lt);
      var pulse = 0.5 + 0.5 * Math.cos(TAU * (lt - 0.51) / BEACON_PERIOD);     // peaks as the beam points down the wall

      // Map the website onto the glass (needs the stage's pixel size, so it is done here, not in setup).
      var W = sc.layer.offsetWidth;
      if (W > 0) {
        var key = W + ':' + g.site.el.offsetWidth + ':' + g.site.el.offsetHeight;
        if (key !== g.siteKey) {
          var k = W / AW;
          g.siteKey = key;
          g.site.el.style.transform = quadMatrix(g.site.el.offsetWidth, g.site.el.offsetHeight, QUAD.map(function (p) { return [p[0] * k, p[1] * k]; }));
        }
      }

      // The website: scene 04's last state, one tear, the pill flips, then it fades to black.
      g.site.set({
        ms: RT_END, spinner: 1, spin: (PREV + lt) * 430, notice: 1, rows: [0.45, 0.45, 0.45],
        pill: lt >= T_PILL ? 'OFFLINE' : 'ONLINE', dark: dark
      });
      var tk = (lt - T_TEAR) / D_TEAR, tear = (!red && tk > 0 && tk < 1) ? Math.pow(Math.sin(Math.PI * tk), 2) : 0;
      var shift = [1.5, -0.9, 0.7];
      for (var i = 0; i < 3; i++) g.bands[i].style.transform = tear > 0 ? 'translateX(' + (shift[i] * tear).toFixed(3) + 'cqw)' : '';
      g.site.el.style.opacity = dark > 0.8 ? (1 - (dark - 0.8) / 0.2).toFixed(3) : '1';
      g.site.el.style.boxShadow = '0 0 2cqw rgba(150,190,255,' + (0.25 * (1 - dark)).toFixed(3) + ')';
      put(g.spill, (0.10 + 0.03 * Math.sin(TAU * 0.3 * (PREV + lt))) * (1 - dark), 1);

      // Alarm: beacon sweep and a slow red wash, fading in as the site dies.
      g.beacon.update(lt, alarm);
      put(g.wash, alarm * (red ? 0.07 : 0.035 + 0.125 * pulse), 1);
      put(g.floorA, alarm * (red ? 0.10 : 0.05 + 0.2 * pulse), 1);
      put(g.floorB, alarm * (red ? 0.08 : 0.04 + 0.16 * pulse), 1);

      // The room: vault light, lamps, wall strips, keypad LED.
      var breath = 0.5 + 0.5 * Math.sin(TAU * 0.4 * lt);
      put(g.vault, 0.07 + 0.05 * breath * MP.smooth(0, 1.2, lt) + 0.03 * MP.smooth(0, 2, lt), 1 + 0.02 * breath);
      put(g.lampA, 0.18 * MP.smooth(0, 0.8, lt) + 0.12 * flick(lt + 1.3), 1);
      put(g.lampB, 0.18 * MP.smooth(0, 0.8, lt) + 0.12 * flick(lt + 3.1), 1);
      put(g.stripA, 0.10 + 0.14 * flick(lt * 0.9 + 0.5), 1);
      put(g.stripB, 0.10 + 0.14 * flick(lt * 0.9 + 2.5), 1);
      put(g.stripC, 0.10 + 0.14 * flick(lt * 0.9 + 4.5), 1);
      put(g.stripD, 0.10 + 0.14 * flick(lt * 0.9 + 6.5), 1);
      put(g.led, 0.45 + 0.45 * (0.5 + 0.5 * Math.sin(TAU * 1.2 * (PREV + lt))), 1);

      // One soft green pulse on the check around 1.0 s, then a faint steady glow.
      var cp = lt - T_CHECK, bump = cp < 0 ? 0 : cp < 0.25 ? MP.easeOut(cp / 0.25) : Math.exp(-(cp - 0.25) / 0.5);
      put(g.check, 0.10 * MP.smooth(T_CHECK, T_CHECK + 0.8, lt) + (red ? 0.1 * (cp > 0 ? 1 : 0) : 0.5 * bump), 1);
    },

    draw: function (sc, lt) {
      motes.draw(lt);
      glints.draw(lt);
      drawCheckRing(lt);
    }
  });
})();
