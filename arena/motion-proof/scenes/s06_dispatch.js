/* Scene 06: large dispatch alert, rain, cabin lights and a gentle idle camera. Characters and cars remain still. Alert only, no Blue code. Display corners inspected against approved art; 4 glows, 34 rain particles, lights 2.2 Hz, alert glow 0.9 Hz. */
(function () {
  'use strict';
  var MP = window.MP;

  /* ---- perspective fit: map a flat design box onto four corners given in art pixels ---- */
  function solve(A, B) {                           // Gaussian elimination, partial pivoting
    var n = B.length, i, j, k, M = A.map(function (row, r) { return row.concat([B[r]]); });
    for (i = 0; i < n; i++) {
      var p = i;
      for (j = i + 1; j < n; j++) if (Math.abs(M[j][i]) > Math.abs(M[p][i])) p = j;
      var t = M[i]; M[i] = M[p]; M[p] = t;
      for (j = i + 1; j < n; j++) {
        var f = M[j][i] / M[i][i];
        for (k = i; k <= n; k++) M[j][k] -= f * M[i][k];
      }
    }
    var x = new Array(n);
    for (i = n - 1; i >= 0; i--) {
      var s = M[i][n];
      for (j = i + 1; j < n; j++) s -= M[i][j] * x[j];
      x[i] = s / M[i][i];
    }
    return x;
  }
  function homography(src, dst) {                  // returns [a,b,c,d,e,f,g,h] with i = 1
    var A = [], B = [];
    for (var i = 0; i < 4; i++) {
      var x = src[i][0], y = src[i][1], X = dst[i][0], Y = dst[i][1];
      A.push([x, y, 1, 0, 0, 0, -x * X, -y * X]); B.push(X);
      A.push([0, 0, 0, x, y, 1, -x * Y, -y * Y]); B.push(Y);
    }
    return solve(A, B);
  }
  // A box of dw x dh design pixels, warped onto `corners` ([TL, TR, BR, BL] in art pixels). Call fit() every frame.
  function quad(layer, corners, dw, dh, cls) {
    var el = MP.add(layer, cls, 'position:absolute;left:0;top:0;width:' + dw + 'px;height:' + dh + 'px;transform-origin:0 0');
    var src = [[0, 0], [dw, 0], [dw, dh], [0, dh]], lastW = -1;
    return {
      el: el,
      fit: function () {
        var w = layer.offsetWidth;                 // layout width: unaffected by the camera transform
        if (!w || w === lastW) return;
        lastW = w;
        var k = w / 1672, h = homography(src, corners.map(function (c) { return [c[0] * k, c[1] * k]; }));
        el.style.transform = 'matrix3d(' + [h[0], h[3], 0, h[6], h[1], h[4], 0, h[7], 0, 0, 1, 0, h[2], h[5], 0, 1].join(',') + ')';
      }
    };
  }
  function isStub(id) { var d = MP.defs[id]; return !d || !d.setup; }

  /* ---------------------------------------------------------------- scene 06 */
  {
    MP.css('interim06',
      '.i6{background:#070d1a;color:#cfe3ff;font-family:system-ui,"Segoe UI",sans-serif;padding:14px 16px;box-sizing:border-box;display:flex;flex-direction:column;gap:8px}' +
      '.i6-head{display:flex;justify-content:space-between;font:700 11px/1 ui-monospace,Consolas,monospace;letter-spacing:.14em;color:#7ccbff}' +
      '.i6-banner{display:flex;align-items:center;justify-content:center;gap:10px;background:linear-gradient(180deg,#d31f2f,#a80f1c);border:2px solid #ff8a8a;border-radius:10px;padding:10px 6px;color:#fff;font:900 40px/1 system-ui,"Segoe UI",sans-serif;text-shadow:0 0 14px rgba(255,255,255,.35)}' +
      '.i6-icon{font:400 50px/1 "Segoe UI Symbol","Segoe UI",system-ui,sans-serif}' +
      '.i6-sub{font:700 24px/1.1 system-ui,sans-serif;color:#ffd2d2;text-align:center}' +
      '.i6-rule{height:2px;background:linear-gradient(90deg,transparent,#4aa3ff,transparent)}' +
      '.i6-foot{display:flex;justify-content:space-between;align-items:baseline;font:600 14px/1.1 system-ui,sans-serif;color:#9fc4f2}' +
      '.i6-foot span:last-child{color:#7f9cc4;font-weight:500;font-size:12px}');
    MP.register({
      id: 'dispatch',
      setup: function (sc, L) {
        var g = sc.g = {};
g.rain = MP.fx.rain({seed:606,n:34,box:MP.rectU(34,15,100,47),speed:[0.4,0.6],len:[0.01,0.023],alpha:[0.14,0.28]});
g.bar = MP.lightbar(sc,L,{hz:2.2,lights:[
{x:20,y:3,w:15,h:4,rgb:MP.BLUE,phase:0.5,max:0.45},
{x:69,y:6,w:8,h:4,rgb:MP.BLUE,phase:0.5,max:0.3},
{x:89,y:54,w:10,h:2,rgb:MP.RED,max:0.35},
{x:8,y:59,w:9,h:2,rgb:MP.BLUE,phase:0.5,max:0.35}]});
        g.q = quad(L, [[861, 473], [1356, 498], [1320, 760], [816, 700]], 490, 230, 'screen i6');
        g.q.el.innerHTML =
          '<div class="i6-head"><span>BLUE DISPATCH · FIXTURE</span></div>' +
          '<div class="i6-banner"><span class="i6-icon">⚠</span><span>BANK LAB ALERT</span></div>' +
          '<div class="i6-sub">Website unavailable</div>' +
          '<div class="i6-rule"></div>' +
          '<div class="i6-foot"><span>Respond to Bank Lab</span><span>Recovery team on standby</span></div>';
        g.banner = g.q.el.querySelector('.i6-banner');
        g.sub = g.q.el.querySelector('.i6-sub');
        g.rule = g.q.el.querySelector('.i6-rule');
        g.foot = g.q.el.querySelector('.i6-foot');
      },
      cam: MP.cam({ push: 0.05, ox: 60, oy: 55, sway: { ax: 0.08, ay: 0.07, fx: 0.6, fy: 0.8, py: 0.5 } }),
      dom: function (sc, lt) {
        var g = sc.g, S = MP.smooth, r = MP.reduced;
        g.q.fit(); g.bar.update(lt,0.2+0.8*MP.smooth(0.5,1.6,lt));
        // The display wakes: powers on, one short stutter, then holds.
        var on = S(0.1, 0.4, lt), dip = r ? 0 : S(0.5, 0.58, lt) - S(0.58, 0.72, lt);
        g.q.el.style.opacity = MP.clamp(on - 0.5 * dip, 0, 1).toFixed(3);
        // The alert pulses softly (under 1 Hz); reduced motion holds it steady.
        var k = r ? 0.5 : 0.5 + 0.5 * Math.sin(MP.TAU * 0.9 * lt);
        g.banner.style.boxShadow = '0 0 ' + (10 + 18 * k).toFixed(1) + 'px rgba(255,70,70,' + (0.35 + 0.4 * k).toFixed(3) + ')';
        g.sub.style.opacity = S(0.9, 1.3, lt).toFixed(3);
        g.rule.style.opacity = g.foot.style.opacity = S(1.4, 1.8, lt).toFixed(3);
      }, draw: function(sc,lt) { sc.g.rain.draw(lt); }
    });
  }
})();
