/* Scene 08, "Spotted at the entrance" (4.5 s). 08_bank_exit.png
 * Moves: the cruiser's light bar alternates red and blue at 2.2 Hz through MP.lightbar, with the haze above the bar and
 *        the long reflections on the wet road; the lights fade in over the first 0.6 s and keep rising. Headlights breathe,
 *        street lamps and the bank's lights flicker softly, the hatchback's tail light and its road glow breathe at 0.9 Hz,
 *        light rain over the whole frame, ripples on the road, slow push toward the left (the cruiser) with a small sway.
 * Does not move: the robber, the bag, the cruiser and the hatchback (baked into the still).
 * Deliberately not animated: the robber's face and bag, the bank's windows. The alarm is off in this scene, so there is no
 *        red wash on the bank and no beacon; the only red is the cruiser, the tail light and what the art already shows.
 * The viewpoint, cruiser and lights are identical in scene 09; the shared block below is repeated there unchanged.
 *
 * Geometry measured from the PNG (1672x941, bright-blob search, about +-2 px), art pixels:
 *   light bar     red lamp (166,492), white (184,492), cyan (210,493), blue (228,494); haze rises above it
 *   headlights    (150,543) and (233,543)         road reflections  red x 144-196 / blue x 194-240, y 590-880
 *   street lamps  (551,165) (411,335) (324,409)   bank interior light (1229,228)   wall sconce (1167,404)
 *   tail light    (1538,585), 84 x 99 px           its glow on the road (1540,895)                           */
(function () {
  'use strict';
  var MP = window.MP;

  /* ---- Shared with scene 09 (same viewpoint, same street). Keep this block identical in s08_exit.js and s09_rush.js ---- */
  var ART_W = 1672, ART_H = 941;
  function X(px) { return px / ART_W * 100; }        // art pixel -> % of the stage, across
  function Y(py) { return py / ART_H * 100; }        // art pixel -> % of the stage, down
  function Q(px) { return px / ART_W * 100; }        // art pixel -> cqw
  var RED_RGB = '255,34,84', BLUE_RGB = '58,76,255';  // sampled from the cruiser's lamps and their road reflections
  var BAR_HZ = 2.2;                                   // MP.lightbar caps this at 2.5
  var T08 = 4.5;                                      // scene 08's length; scene 09 keeps this clock running
  var CAM_END_08 = [1.05, 14, 56];                    // scale and origin (% of stage) where scene 08's camera ends; scene 09 starts there
  var LEVEL_END = 0.72, GROW_END = 1.1;               // light level and headlight bloom scale where scene 08 ends and scene 09 begins
  // Measured with a bright-blob search on both stills (they agree to +-1 px). Art pixels.
  var CRUISER = {
    redLamp: [169, 491], redHaze: [177, 468], redRoad: [176, 740],         // bar, its haze above, its reflection below
    blueLamp: [219, 493], blueHaze: [212, 468], blueRoad: [217, 742],
    headL: [150, 543], headR: [233, 543]
  };
  var LAMPS = [[551, 165, 110], [411, 335, 84], [324, 409, 62]];            // street lamps: x, y, glow width
  var DOOR = [1229, 228];                                                    // bank interior light
  var TAIL = [1538, 585], TAIL_ROAD = [1540, 895];                           // hatchback tail light and its wet-road glow
  // Same rain and puddle ripples in both scenes, on one clock, so the weather carries across the cut.
  var wr = MP.rng(20260808);
  var rain = MP.fx.rain({ rng: wr, n: 46, box: MP.rectU(0, 0, 100, 100), speed: [0.55, 0.95], len: [0.014, 0.034], alpha: [0.14, 0.34], width: [0.8, 1.4] });
  var ripFar = MP.fx.ripples({ rng: wr, n: 4, box: MP.rectU(0, 64, 18, 74), rmax: 0.013, alpha: [0.12, 0.28] });
  var ripNear = MP.fx.ripples({ rng: wr, n: 7, box: MP.rectU(1, 76, 34, 99), rmax: 0.03, alpha: [0.12, 0.3] });
  var ripPave = MP.fx.ripples({ rng: wr, n: 4, box: MP.rectU(54, 83, 78, 96), rmax: 0.02, alpha: [0.1, 0.26] });

  // Builds the glows that both scenes share, in the same order and at the same positions.
  function buildLights(sc, L) {
    var g = {}, c = CRUISER;
    g.bar = MP.lightbar(sc, L, { hz: BAR_HZ, lights: [
      { x: X(c.redLamp[0]), y: Y(c.redLamp[1]), w: Q(90), h: Q(78), rgb: RED_RGB, phase: 0, max: 0.6 },
      { x: X(c.redHaze[0]), y: Y(c.redHaze[1]), w: Q(104), h: Q(140), rgb: RED_RGB, phase: 0, max: 0.3 },
      { x: X(c.redRoad[0]), y: Y(c.redRoad[1]), w: Q(56), h: Q(260), rgb: RED_RGB, phase: 0, max: 0.5 },
      { x: X(c.blueLamp[0]), y: Y(c.blueLamp[1]), w: Q(90), h: Q(78), rgb: BLUE_RGB, phase: 0.5, max: 0.6 },
      { x: X(c.blueHaze[0]), y: Y(c.blueHaze[1]), w: Q(104), h: Q(140), rgb: BLUE_RGB, phase: 0.5, max: 0.3 },
      { x: X(c.blueRoad[0]), y: Y(c.blueRoad[1]), w: Q(52), h: Q(250), rgb: BLUE_RGB, phase: 0.5, max: 0.5 }
    ] });
    g.headL = MP.glow(sc, L, X(c.headL[0]), Y(c.headL[1]), Q(120), Q(96), '255,246,226');
    g.headR = MP.glow(sc, L, X(c.headR[0]), Y(c.headR[1]), Q(120), Q(96), '255,246,226');
    g.lamps = LAMPS.map(function (p) { return MP.glow(sc, L, X(p[0]), Y(p[1]), Q(p[2]), Q(p[2]), '255,196,110'); });
    g.door = MP.glow(sc, L, X(DOOR[0]), Y(DOOR[1]), Q(150), Q(86), '255,222,150');
    g.tail = MP.glow(sc, L, X(TAIL[0]), Y(TAIL[1]), Q(150), Q(176), '255,36,44');
    g.tailRoad = MP.glow(sc, L, X(TAIL_ROAD[0]), Y(TAIL_ROAD[1]), Q(150), Q(92), '255,40,48');
    return g;
  }
  // T is the shared clock (scene 08: lt, scene 09: lt + T08). level scales the emergency lights; grow scales the headlight bloom.
  function updateLights(g, T, level, grow) {
    var r = MP.reduced, flick = MP.flick, breath = 0.5 + 0.5 * Math.sin(MP.TAU * 0.9 * T);
    g.bar.update(T, level);
    MP.put(g.headL, 0.2 + 0.1 * flick(T * 0.9 + 1.3), grow);
    MP.put(g.headR, 0.2 + 0.1 * flick(T * 0.9 + 4.1), grow);
    g.lamps.forEach(function (el, i) { MP.put(el, 0.2 + 0.12 * flick(T * 0.8 + 2.6 * i), 1); });
    MP.put(g.door, 0.16 + 0.08 * (0.5 + 0.5 * Math.sin(MP.TAU * 0.4 * T + 1)), 1);
    MP.put(g.tail, 0.26 + (r ? 0.05 : 0.16) * breath, 1);
    MP.put(g.tailRoad, 0.2 + (r ? 0.04 : 0.12) * breath, 1);
  }
  function drawWeather(T) {
    ripFar.draw(T); ripNear.draw(T); ripPave.draw(T);
    rain.draw(T);
  }
  /* ---- end of the shared block ---- */

  // Scene 08 only: the lamp on the doorway wall.
  var SCONCE = [1167, 404];
  function level(lt) { return 0.56 * MP.smooth(0, 0.6, lt) + (LEVEL_END - 0.56) * MP.smooth(0.6, T08, lt); }

  MP.register({
    id: 'exit',
    setup: function (sc, L) {
      var g = sc.g = buildLights(sc, L);
      g.sconce = MP.glow(sc, L, X(SCONCE[0]), Y(SCONCE[1]), Q(60), Q(60), '255,214,140');
    },
    cam: MP.cam({ push: CAM_END_08[0] - 1, ox: CAM_END_08[1], oy: CAM_END_08[2], sway: { ax: 0.07, ay: 0.05, fx: 0.55, fy: 0.8, py: 0.5 } }),
    dom: function (sc, lt) {
      updateLights(sc.g, lt, level(lt), 1 + (GROW_END - 1) * MP.smooth(0.6, T08, lt));
      MP.put(sc.g.sconce, 0.2 + 0.1 * MP.flick(lt * 0.8 + 6.1), 1);
    },
    draw: function (sc, lt) { drawWeather(lt); }
  });
})();
