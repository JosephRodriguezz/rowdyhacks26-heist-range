/* Scene 09, "Back to the car" (4.0 s). 09_rush_same_parking-r2.png
 * Moves: the same cruiser as scene 08, now stronger: the light bar keeps alternating at 2.2 Hz through MP.lightbar on the
 *        same clock (no phase jump at the cut), starting at the level where scene 08 ended and rising to full; headlight
 *        bloom grows; haze and road reflections follow. Two bursts of water thrown up by his feet and ripples in that
 *        puddle, tail light and road glow breathing, the same rain and ripples as scene 08, a push toward the open car door
 *        with a small run shake. The camera starts exactly where scene 08's ended and drifts to the car.
 * Does not move: the robber, the bag, the car and its door (baked into the still).
 * Deliberately not animated: the robber's stride (the splash bursts once, as the foot lands, and is not repeated, so no
 *        step is implied). No alarm: nothing red but the cruiser, the tail light and what the art already shows.
 * Everything cruiser-related is the shared block below, identical to scene 08's.
 *
 * Geometry measured from the PNG (1672x941, about +-2 px), art pixels:
 *   rear foot (970,660) and its spray (975,706)   front foot lands (1127,707), heel splash (1085,728)
 *   open door (1170-1320, 400-690)                 puddle under his feet x 940-1110, y 695-735            */
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

  // Scene 09 only.
  var DUR = 4.0, CAM_END_09 = [1.09, 85, 60];         // camera ends pushed toward the car
  // A scale about an origin is the same view as the scale about the centre plus a shift, so the two scenes' cameras can be blended.
  function viewOf(s, ox, oy) { return [s, (1 - s) * (ox - 50), (1 - s) * (oy - 50)]; }
  var VA = viewOf(CAM_END_08[0], CAM_END_08[1], CAM_END_08[2]), VB = viewOf(CAM_END_09[0], CAM_END_09[1], CAM_END_09[2]);

  var sr = MP.rng(20260909);
  var splashRear = MP.fx.splash({ rng: sr, n: 14, x: 975 / ART_W, y: 706 / ART_H, jitter: 0.018, angle: [-160, -25], speed: [0.1, 0.34], size: [0.0012, 0.0028], life: [0.5, 1.0], rgb: '255,232,200' });
  var splashFront = MP.fx.splash({ rng: sr, n: 18, x: 1085 / ART_W, y: 728 / ART_H, jitter: 0.02, angle: [-150, -30], speed: [0.12, 0.4], size: [0.0012, 0.003], life: [0.5, 1.1], rgb: '255,232,200' });
  var ripFeet = MP.fx.ripples({ rng: sr, n: 4, box: MP.rectU(56, 73, 66, 78), rmax: 0.018, alpha: [0.14, 0.32], period: [0.9, 1.4] });

  MP.register({
    id: 'rush',
    setup: function (sc, L) { sc.g = buildLights(sc, L); },
    cam: function (sc, lt) {
      if (MP.reduced) return MP.CAM0;
      var e = MP.easeInOut(lt / sc.dur), w = MP.smooth(0, 0.5, lt), T = MP.TAU;
      var tx = MP.lerp(VA[1], VB[1], e) + w * (0.1 * Math.sin(T * 2.3 * lt) + 0.04 * Math.sin(T * 3.7 * lt + 1.1));
      var ty = MP.lerp(VA[2], VB[2], e) + w * (0.14 * Math.sin(T * 2.9 * lt + 0.6) + 0.05 * Math.sin(T * 4.3 * lt + 2));
      return [MP.lerp(VA[0], VB[0], e), tx, ty, 50, 50];
    },
    dom: function (sc, lt) {
      var k = MP.smooth(0, DUR, lt);
      updateLights(sc.g, lt + T08, LEVEL_END + (1 - LEVEL_END) * k, GROW_END + 0.2 * k);
    },
    draw: function (sc, lt) {
      drawWeather(lt + T08);
      ripFeet.draw(lt + T08);
      splashRear.draw(lt - 0.3);
      splashFront.draw(lt - 0.48);
    }
  });
})();
