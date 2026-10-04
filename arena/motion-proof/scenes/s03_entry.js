/* Scene 03, "The vault in the distance" (5.0 s). 03_bank_entry-r2.png
 * Moves: rain in the broken door's window, glints on the floor glass, slow dolly toward the vault, chandelier and
 *        vault glow.
 * Does not move: the robber (baked into the still). */
(function () {
  'use strict';
  var MP = window.MP;

  // Same stream as the first proof, advanced past scene 02's debris, dust and sparks so the layout is unchanged.
  var r = MP.rng(20261003);
  MP.skip(r, 54 * 13 + 14 * 9 + 30 * 6);
  var rain = MP.fx.rain({ rng: r, n: 36, box: MP.rectU(3.6, 0, 16.8, 63) });
  var glints = MP.fx.glints({ rng: r, regions: [
    { n: 7, x: [0.03, 0.22], y: [0.88, 0.985] },     // glass on the floor, left
    { n: 6, x: [0.70, 0.97], y: [0.83, 0.93] },      // glass on the floor, right
    { n: 4, x: [0.03, 0.15], y: [0.62, 0.76] }       // glass in the broken door
  ] });

  MP.register({
    id: 'entry',
    setup: function (sc, L) {
      var g = sc.g = {};
      g.vault = MP.glow(sc, L, 66.6, 38, 22, 22, '255,205,120');
      g.pendA = MP.glow(sc, L, 66.4, 9, 14, 14, '255,226,160');
      g.pendB = MP.glow(sc, L, 65.5, 18.5, 11, 11, '255,226,160');
      g.pendC = MP.glow(sc, L, 66, 24.5, 8, 8, '255,226,160');
      g.lampA = MP.glow(sc, L, 7.6, 25, 7, 7, '255,196,110');
      g.lampB = MP.glow(sc, L, 13.9, 28.9, 6, 6, '255,196,110');
    },
    cam: MP.cam({ push: 0.10, ox: 66.6, oy: 42, sway: { ax: 0.12, ay: 0.10, fx: 0.9, fy: 1.3, py: 1 } }),
    dom: function (sc, lt) {
      var g = sc.g, put = MP.put, flick = MP.flick, breath = 0.5 + 0.5 * Math.sin(MP.TAU * 0.45 * lt);
      put(g.vault, 0.2 + 0.12 * breath + (MP.reduced ? 0 : 0.08 * MP.smooth(0, 5, lt)), 1 + 0.03 * Math.sin(MP.TAU * 0.45 * lt));
      put(g.pendA, 0.26 + 0.2 * flick(lt + 3), 1);
      put(g.pendB, 0.26 + 0.2 * flick(lt + 5), 1);
      put(g.pendC, 0.26 + 0.2 * flick(lt + 7), 1);
      put(g.lampA, 0.3 + 0.15 * flick(lt + 1.7), 1);
      put(g.lampB, 0.3 + 0.15 * flick(lt + 3.9), 1);
    },
    draw: function (sc, lt) { rain.draw(lt); glints.draw(lt); }
  });
})();
