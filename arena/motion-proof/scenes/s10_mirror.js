/* Scene 10, "Blue in the mirror" (4.5 s). 10_rear_view.png
 * Moves: the cruiser's light bar and grille lights flash inside the mirror (2.2 Hz, red and blue alternate), a soft red/blue
 *        spill on the windscreen edge, the dash top and Red's hat, the cruiser's headlights, three street lamps, the lit
 *        hazard button, rain on the windscreen, a few drops creeping down the glass, road vibration, a slow push to the mirror.
 * Does not move: Red, the cruiser and its driver (baked into the still).
 * Deliberately not animated: the drops and street inside the mirror, the dash display. The flashing stays in the mirror
 *        and in its spill on the windscreen edge, dash top and hat; nothing flashes on the street ahead.
 *
 * Geometry, measured from the PNG (1672x941, about +-2 px):
 *   mirror glass          x 704-1513, y 114-325 (outer frame 679-1541, 94-346)
 *   light bar lenses      red (1089,146)  blue (1172,146)   caps at 1049-1073 and 1188-1217
 *   grille lights         red (1090,259)  blue (1166,259)
 *   cruiser headlights    (1008,298) and (1247,299)
 *   hazard button         (885,892)
 *   lamps                 (527,149) (1558,262) (697,361)                                                              */
(function () {
  'use strict';
  var MP = window.MP;
  var PX = 100 / 1672, PY = 100 / 941;          // art pixels to % of the stage
  var HZ = 2.2;                                  // emergency lights, under the 2.5 Hz cap
  var WARM = '255,206,130';

  function glow(sc, L, x, y, w, h, rgb) { return MP.glow(sc, L, x * PX, y * PY, w * PX, h * PX, rgb); }
  function spec(x, y, w, h, rgb, phase, max) { return { x: x * PX, y: y * PY, w: w * PX, h: h * PX, rgb: rgb, phase: phase, max: max }; }

  // Rain and drops are clipped to the windscreen glass: outside the hat, outside the mirror, above the dash.
  var GLASS = [[347, 128], [600, 100], [790, 88], [975, 94], [1185, 94], [1190, 52], [1672, 33], [1672, 675], [1100, 654], [840, 641], [700, 642],
               [655, 626], [611, 604], [565, 588], [508, 586], [490, 556], [500, 500], [527, 440], [532, 400], [521, 347], [540, 285],
               [521, 240], [467, 193], [400, 167], [347, 143]];
  var MIRROR = [679, 94, 1541, 346, 62];
  function tracePoly(ctx, pts) {
    var k = MP.cw / 1672;
    for (var i = 0; i < pts.length; i++) { if (i) ctx.lineTo(pts[i][0] * k, pts[i][1] * k); else ctx.moveTo(pts[i][0] * k, pts[i][1] * k); }
    ctx.closePath();
  }
  function traceRound(ctx, b) {
    var k = MP.cw / 1672, x0 = b[0] * k, y0 = b[1] * k, x1 = b[2] * k, y1 = b[3] * k, r = b[4] * k;
    ctx.moveTo(x0 + r, y0); ctx.arcTo(x1, y0, x1, y1, r); ctx.arcTo(x1, y1, x0, y1, r); ctx.arcTo(x0, y1, x0, y0, r); ctx.arcTo(x0, y0, x1, y0, r); ctx.closePath();
  }
  function clipGlass(ctx) {
    ctx.beginPath(); tracePoly(ctx, GLASS); ctx.clip();
    ctx.beginPath(); ctx.rect(0, 0, MP.cw, MP.cw); traceRound(ctx, MIRROR); ctx.clip('evenodd');
  }

  // The baked bar shows both lenses lit. A dark tint over a lens while its flash is off makes the two sides read as alternating.
  function dimmer(L, x, y, w, h, rgb) {
    return MP.add(L, 'dim', 'position:absolute;left:' + x * PX + '%;top:' + y * PY + '%;width:' + w * PX + 'cqw;height:' + h * PX + 'cqw;transform:translate(-50%,-50%);' +
      'border-radius:40%;opacity:0;pointer-events:none;mix-blend-mode:multiply;' +
      'background:radial-gradient(closest-side,rgba(' + rgb + ',1),rgba(' + rgb + ',.9) 70%,rgba(' + rgb + ',0))');
  }

  var rain = MP.fx.rain({ seed: 1010, n: 64, box: MP.rectU(20.6, 3.2, 100, 70), slant: 0.14, speed: [0.55, 1.0], len: [0.02, 0.05], alpha: [0.16, 0.42], width: [1, 1.6] });

  // x, y0 (art px), radius (px), creep speed (px/s)
  var DROPS = [[588, 292, 5.2, 9], [640, 455, 4.4, 12], [905, 470, 5.0, 8], [1256, 540, 5.6, 10], [1584, 318, 4.6, 11], [1622, 520, 5.4, 8]];
  function drawDrops(lt) {
    var ctx = MP.ctx, k = MP.cw / 1672, creep = MP.reduced ? 0 : lt;
    ctx.save(); clipGlass(ctx);
    for (var i = 0; i < DROPS.length; i++) {
      var d = DROPS[i], y = d[1] + d[3] * creep, x = d[0] + 1.2 * Math.sin(creep * 1.6 + i * 2), r = d[2], trail = 4 + d[3] * creep * 0.9;
      var g = ctx.createLinearGradient(0, (y - trail) * k, 0, y * k);
      g.addColorStop(0, 'rgba(210,225,255,0)'); g.addColorStop(1, 'rgba(210,225,255,0.24)');
      ctx.globalAlpha = 1; ctx.strokeStyle = g; ctx.lineWidth = Math.max(1, 1.6 * k);
      ctx.beginPath(); ctx.moveTo(x * k, (y - trail) * k); ctx.lineTo(x * k, y * k); ctx.stroke();
      // a bead of water: clear middle, brighter rim, one highlight up and to the left
      var rx = r * 0.8 * k, ry = r * k;
      var b = ctx.createRadialGradient(x * k, y * k, 0, x * k, y * k, ry);
      b.addColorStop(0, 'rgba(255,255,255,0.04)'); b.addColorStop(0.65, 'rgba(210,225,255,0.12)'); b.addColorStop(0.9, 'rgba(255,255,255,0.42)'); b.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = b; ctx.beginPath(); ctx.ellipse(x * k, y * k, rx * 1.1, ry * 1.1, 0, 0, MP.TAU); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.beginPath(); ctx.ellipse((x - r * 0.3) * k, (y - r * 0.38) * k, rx * 0.22, ry * 0.18, -0.5, 0, MP.TAU); ctx.fill();
    }
    ctx.restore();
  }

  // Slow lift of the whole scene by the push; road vibration is a second, faster and tiny sway on top.
  var baseCam = MP.cam({ push: 0.05, ox: 60, oy: 25, sway: { ax: 0.09, ay: 0.07, fx: 0.7, fy: 0.9, py: 1.3 } });

  MP.register({
    id: 'mirror',
    setup: function (sc, L) {
      var g = sc.g = {};
      // 1. Flashing inside the mirror
      g.mirror = MP.lightbar(sc, L, { hz: HZ, lights: [
        spec(1078, 146, 130, 52, MP.RED, 0, 0.55),
        spec(1184, 146, 130, 52, MP.BLUE, 0.5, 0.55),
        spec(1090, 259, 84, 34, MP.RED, 0, 0.5),
        spec(1166, 259, 92, 34, MP.BLUE, 0.5, 0.5)
      ] });
      // 2. Its spill: windscreen edge, dash top, Red's hat
      g.spill = MP.lightbar(sc, L, { hz: HZ, lights: [
        spec(1060, 652, 360, 70, MP.RED, 0, 0.30),
        spec(1290, 654, 320, 66, MP.BLUE, 0.5, 0.30),
        spec(1010, 722, 520, 92, MP.RED, 0, 0.20),
        spec(1290, 724, 520, 92, MP.BLUE, 0.5, 0.20),
        spec(468, 245, 140, 290, MP.RED, 0, 0.17),
        spec(452, 215, 130, 250, MP.BLUE, 0.5, 0.17)
      ] });
      g.headL = glow(sc, L, 1008, 298, 104, 58, '255,214,140');
      g.headR = glow(sc, L, 1247, 299, 104, 58, '255,214,140');
      g.hazard = glow(sc, L, 885, 892, 72, 72, '255,56,66');
      g.lampA = glow(sc, L, 527, 149, 96, 96, WARM);
      g.dimR = dimmer(L, 1077, 146, 64, 26, '150,12,22');
      g.dimB = dimmer(L, 1187, 146, 68, 26, '12,34,150');
    },
    cam: function (sc, lt) {
      var c = baseCam(sc, lt);
      if (MP.reduced) return c;
      var a = MP.TAU * lt;
      return [c[0], c[1] + 0.035 * Math.sin(a * 3.1 + 0.4) + 0.02 * Math.sin(a * 5.3), c[2] + 0.05 * Math.sin(a * 4.3 + 1.1) + 0.025 * Math.sin(a * 6.9 + 0.2), c[3], c[4]];
    },
    dom: function (sc, lt) {
      var g = sc.g, flick = MP.flick, lvl = 0.8 + 0.2 * MP.smooth(0, 1.0, lt);
      g.mirror.update(lt, lvl);
      g.spill.update(lt, lvl);
      MP.put(g.headL, 0.22 + 0.10 * flick(lt * 0.7 + 1), 1);
      MP.put(g.headR, 0.22 + 0.10 * flick(lt * 0.7 + 3), 1);
      MP.put(g.hazard, MP.reduced ? 0.4 : 0.15 + 0.5 * (0.5 + 0.5 * Math.sin(MP.TAU * 1.3 * lt)), 1);
      MP.put(g.lampA, 0.28 + 0.14 * flick(lt * 0.8 + 2), 1);
      g.dimR.style.opacity = (MP.reduced ? 0 : lvl * 0.95 * (1 - MP.pulse(lt, HZ, 0.5, 0.2))).toFixed(3);
      g.dimB.style.opacity = (MP.reduced ? 0 : lvl * 0.95 * (1 - MP.pulse(lt + 0.5 / HZ, HZ, 0.5, 0.2))).toFixed(3);
    },
    draw: function (sc, lt) {
      var ctx = MP.ctx;
      ctx.save(); clipGlass(ctx); rain.draw(lt); ctx.restore();
      drawDrops(lt);
    }
  });
})();
