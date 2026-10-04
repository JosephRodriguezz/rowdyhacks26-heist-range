/* Scene 02, "Through the front doors" (4.5 s). 02_bank_crash.png
 * Moves: impact flash, camera shake and kick, 54 debris pieces, sparks, dust, chandelier stutter, tail-light pulse,
 *        street-lamp flicker.
 * Does not move: the car and the robber (baked into the still).
 * Deliberately not animated: the blue light in the far background. No police activity before scene 06. */
(function () {
  'use strict';
  var MP = window.MP, IMPACT = 0.33;       // seconds into the scene when the car hits the doors

  // One shared stream, drawn in the same order as the first proof, so the layout is unchanged.
  var r = MP.rng(20261003);
  var debris = MP.fx.debris({ rng: r, n: 54, x: [0.60, 0.70], y: [0.52, 0.66], angle: [-170, -20], speed: [0.18, 0.80], ground: [0.84, 0.95], tau: [0.9, 1.5], size: [0.003, 0.011], life: [2.0, 3.9], delay: 0.06 });
  var dust = MP.fx.dust({ rng: r, n: 14, x: [0.58, 0.72], y: [0.50, 0.66] });
  var sparks = MP.fx.sparks({ rng: r, n: 30, x: [0.63, 0.70], y: [0.55, 0.65], angle: [-160, -20], speed: [0.35, 1.25], spread: 0.4, life: [0.35, 1.05] });

  MP.register({
    id: 'crash',
    setup: function (sc, L) {
      var g = sc.g = {};
      g.flash = MP.glow(sc, L, 66, 56, 70, 50, '255,214,150');
      g.embers = MP.glow(sc, L, 65, 54, 18, 14, '255,160,60');
      g.chand = MP.glow(sc, L, 65.5, 29, 16, 12, '255,225,160');
      g.tl = MP.glow(sc, L, 21, 64.8, 11, 8, '255,40,40');
      g.tr = MP.glow(sc, L, 39.2, 63.6, 10, 7, '255,40,40');
      g.lampA = MP.glow(sc, L, 9, 31, 8, 8, '255,200,120');
      g.lampB = MP.glow(sc, L, 14.5, 42.5, 6, 6, '255,200,120');
      g.bolA = MP.glow(sc, L, 13.9, 68, 5, 5, '255,190,100');
      g.bolB = MP.glow(sc, L, 84, 66, 6, 6, '255,190,100');
    },
    cam: MP.cam({ push: 0.055, ease: 'out', ox: 60, oy: 58, shake: { t0: IMPACT, amp: 0.9, decay: 0.34, kick: 0.028, kickDecay: 0.28 } }),
    dom: function (sc, lt) {
      var g = sc.g, tp = lt - IMPACT, hit = tp > 0, r = MP.reduced, put = MP.put, flick = MP.flick;
      var flash = r || !hit || tp >= 0.32 ? 0 : (tp < 0.04 ? tp / 0.04 : 1 - MP.smooth(0.04, 0.32, tp)) * 0.95;
      put(g.flash, flash, 1 + 0.15 * flash);
      put(g.embers, (hit ? 0.15 + 0.4 * Math.exp(-tp / 2.6) : 0.18) * (0.8 + 0.2 * flick(lt + 5)), 1);
      var amp = r ? 0.08 : 0.15 + (hit ? 0.3 * Math.exp(-tp / 0.9) : 0);
      put(g.chand, 0.42 + amp * (flick(lt) - 0.5) * 2, 1);
      var bump = r || !hit ? 0 : 0.35 * Math.exp(-tp / 0.6);
      put(g.tl, 0.35 + 0.2 * (0.5 + 0.5 * Math.sin(MP.TAU * 0.9 * lt)) + bump, 1);
      put(g.tr, 0.35 + 0.2 * (0.5 + 0.5 * Math.sin(MP.TAU * 0.9 * lt + 0.4)) + bump, 1);
      put(g.lampA, 0.2 + 0.1 * flick(lt * 0.8), 1);
      put(g.lampB, 0.2 + 0.1 * flick(lt * 0.8 + 2), 1);
      put(g.bolA, 0.2 + 0.1 * flick(lt * 0.8 + 4), 1);
      put(g.bolB, 0.2 + 0.1 * flick(lt * 0.8 + 6), 1);
    },
    draw: function (sc, lt) {
      var tp = lt - IMPACT;
      if (tp < 0) return;
      dust.draw(tp);          // dimmer in reduced motion
      debris.draw(tp);        // skipped in reduced motion
      sparks.draw(tp);        // skipped in reduced motion
    }
  });
})();
