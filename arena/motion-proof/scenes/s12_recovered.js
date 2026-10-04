/* Scene 12: continue scene 11 camera, seeded rain and lights at T=13+lt.
 * Completed fixture feed dissolves to the approved check. Characters/cars stay still.
 * Shared glass geometry in s11; check centre 1233,693, radius 88 art px.
 * One green ring; emergency lights 2.2 Hz. 14 glows, 41 particles. */
(function(){'use strict';var MP=window.MP,chase=MP.defs.pursuit;
MP.register({id:'recovered',
setup:function(sc,L){chase.setup(sc,L);
sc.g.feed=window.MP_STORY.scenes[10].blueLines.map(function(s){return {t:0,s:s};});
sc.g.check=MP.glow(sc,L,1233/1672*100,693/941*100,13,13,'70,255,110');},
cam:function(sc,lt){return chase.cam(sc,13+lt);},
dom:function(sc,lt){chase.dom(sc,13+lt);var fade=MP.smooth(0.4,1.05,lt),g=sc.g;
g.screen.el.style.opacity=(1-fade).toFixed(3);g.screen.el.style.visibility=fade>=1?'hidden':'visible';
var bump=Math.sin(Math.PI*MP.clamp((lt-0.9)/0.9,0,1));
MP.put(g.check,MP.reduced?0.10*fade:0.10*fade+0.28*bump,1);},
draw:function(sc,lt){chase.draw(sc,13+lt);var p=(lt-0.9)/0.8;if(MP.reduced||p<0||p>1)return;
var ctx=MP.ctx,k=MP.cw/1672;ctx.save();ctx.globalAlpha=0.35*Math.sin(Math.PI*p);ctx.strokeStyle='#77ffac';ctx.lineWidth=2*k;
ctx.beginPath();ctx.arc(1233*k,693*k,(92+12*MP.easeOut(p))*k,0,MP.TAU);ctx.stroke();ctx.restore();}
});})();
