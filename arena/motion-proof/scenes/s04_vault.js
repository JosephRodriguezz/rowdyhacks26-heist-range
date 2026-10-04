/* Scene 04, "At the keypad" (12.0 s). 04_large_straight_website-r4.png
 * Moves: keypad keys light in sequence, the website on the large display (it slows down but stays ONLINE),
 *        the Red feed typing on the small display, a brass glint across the vault door, drifting dust, slow push-in.
 * Does not move: the robber and his hand (baked into the still).
 * Deliberately not animated: the red beacon at the top of the wall. The alarm stays off until scene 05.
 *
 * Screen geometry, measured from the PNG (1672x941, about +-2 px), then inset ~0.1 % off the bezel:
 *   large display quad TL 820,131 TR 1578,91 BR 1584,446 BL 817,454; fitted inside the glass
 *   small display  left 78.1  top 56.0  width 14.6  height 13.6                                          */
(function () {
  'use strict';
  var MP = window.MP;
  var BIG = { left: 49.1, top: 10.1, width: 45.9, height: 37.8 };
  var SMALL = { left: 78.2, top: 56.1, width: 14.4, height: 13.4 };
  var KEYS = { 1: [51.0, 58.8], 2: [53.6, 58.8], 3: [56.3, 58.8], 4: [50.3, 63.3], 5: [53.0, 63.3], 6: [55.7, 63.3], 8: [52.2, 67.6], 9: [55.1, 67.6] };
  var SEQ = [4, 1, 5, 9, 2, 8, 6, 3];
  var FEED_T = [0.6, 1.9, 3.4, 5.0, 6.6, 8.4];     // when each of the six Red lines starts typing
  var SWEEPS = [1.2, 5.0, 8.8], SWEEP_DUR = 1.2;

  // Same stream as the first proof, advanced past scenes 02 and 03 so the layout is unchanged.
  var r = MP.rng(20261003);
  MP.skip(r, 54 * 13 + 14 * 9 + 30 * 6 + 36 * 6 + 17 * 5);
  var motes = MP.fx.motes({ rng: r, n: 30, x: [0.04, 0.50], y: [0.10, 0.90] });

  function quadMatrix(w, h, q) {
    var x0 = q[0][0], y0 = q[0][1], x1 = q[1][0], y1 = q[1][1], x2 = q[2][0], y2 = q[2][1], x3 = q[3][0], y3 = q[3][1];
    var dx1 = x1 - x2, dx2 = x3 - x2, dy1 = y1 - y2, dy2 = y3 - y2;
    var sx = x0 - x1 + x2 - x3, sy = y0 - y1 + y2 - y3, den = dx1 * dy2 - dx2 * dy1;
    var g = (sx * dy2 - dx2 * sy) / den, hh = (dx1 * sy - sx * dy1) / den;
    var a = x1 - x0 + g * x1, b = x3 - x0 + hh * x3, d = y1 - y0 + g * y1, e = y3 - y0 + hh * y3;
    return 'matrix3d(' + [a / w, d / w, 0, g / w, b / h, e / h, 0, hh / h, 0, 0, 1, 0, x0, y0, 0, 1].map(function (v) { return v.toFixed(7); }).join(',') + ')';
  }

  function rtAt(lt) {
    var q = Math.floor(lt * 8) / 8;
    var base = 108 + 3700 * Math.pow(MP.smooth(1.5, 11.5, q), 2.2);
    return base * (1 + 0.07 * Math.sin(q * 41) + 0.04 * Math.sin(q * 17 + 1));
  }
  function drawDoorSweep(lt) {
    var ctx = MP.ctx, cw = MP.cw, A = MP.ASPECT;
    var cx = 0.239 * cw, cy = 0.409 * A * cw, R = 0.150 * cw;
    for (var i = 0; i < SWEEPS.length; i++) {
      var p = (lt - SWEEPS[i]) / SWEEP_DUR;
      if (p < 0 || p > 1) continue;
      var q = -0.2 + 1.4 * MP.easeInOut(p);
      var gr = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
      var peak = 0.5 * (MP.reduced ? 0.5 : 1) * Math.sin(Math.PI * p);
      gr.addColorStop(MP.clamp(q - 0.14, 0, 1), 'rgba(255,240,200,0)');
      gr.addColorStop(MP.clamp(q, 0, 1), 'rgba(255,244,214,' + peak.toFixed(3) + ')');
      gr.addColorStop(MP.clamp(q + 0.14, 0, 1), 'rgba(255,240,200,0)');
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, MP.TAU); ctx.clip();
      ctx.fillStyle = gr; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
      ctx.restore();
    }
  }

  MP.register({
    id: 'vault',
    setup: function (sc, L) {
      var g = sc.g = {}, label;
      g.spill = MP.glow(sc, L, BIG.left + BIG.width / 2, BIG.top + BIG.height / 2, 56, 34, '190,215,255');
      g.led = MP.glow(sc, L, 59.9, 66.5, 3.4, 3.4, '255,60,50');
      g.site = MP.siteScreen(L, {left:0,top:0,width:45.6,height:36.4});
      g.site.el.style.transformOrigin = '0 0';
      g.code = MP.codeScreen(L, SMALL, { theme: 'red' });
      g.feed = sc.redLines.map(function (s, i) { return { t: FEED_T[i], s: s }; });
      g.keys = {};
      for (label in KEYS) {
        var k = MP.add(L, 'key', 'left:' + KEYS[label][0] + '%;top:' + KEYS[label][1] + '%');
        g.keys[label] = k;
      }
    },
    cam: MP.cam({ push: 0.065, ox: 62, oy: 45, sway: { ax: 0.08, ay: 0.06, fx: 0.6, fy: 0.8, py: 0.4 } }),
    dom: function (sc, lt) {
      var g = sc.g, i, d;
      var W = sc.layer.offsetWidth;
      if (W > 0 && W !== g.siteWidth) {
        g.siteWidth = W;
        var k = W / 1672;
        g.site.el.style.transform = quadMatrix(g.site.el.offsetWidth, g.site.el.offsetHeight,
          [[820,131],[1578,91],[1584,446],[817,454]].map(function(p){return [p[0]*k,p[1]*k];}));
      }
      for (i = 0; i < SEQ.length; i++) {
        d = lt - (0.9 + i * 1.15);
        g.keys[SEQ[i]].style.opacity = (d < 0 ? 0 : d < 0.06 ? d / 0.06 : Math.exp(-(d - 0.06) / 0.16)).toFixed(3);
      }
      MP.put(g.led, 0.45 + 0.45 * (0.5 + 0.5 * Math.sin(MP.TAU * 1.2 * lt)), 1);
      MP.put(g.spill, 0.10 + 0.03 * Math.sin(MP.TAU * 0.3 * lt), 1);
      g.site.set({
        ms: rtAt(lt),
        spinner: MP.smooth(4.0, 4.8, lt), spin: lt * 430,
        notice: MP.smooth(7.5, 8.3, lt),
        rows: [0, 1, 2].map(function (n) { return 1 - 0.55 * MP.smooth(6 + n, 8.5 + n, lt); })
      });
      g.code.update(lt, g.feed, 30);
    },
    draw: function (sc, lt) { motes.draw(lt); drawDoorSweep(lt); }
  });
})();
