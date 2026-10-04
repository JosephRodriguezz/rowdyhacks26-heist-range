/* Scene 01: route-light sweep, START glow, dash LEDs and slow push.
 * Driver/cars/police lights remain still. No emergency animation.
 * Art anchors (1672x941): START 845,708; route 712,685 -> 879,550.
 * Nine glows, START breathes at 0.8 Hz. */
(function(){
'use strict';var MP=window.MP,path=[[712,685],[740,622],[861,623],[869,592],[853,586],[858,571],[879,550]];
MP.register({id:'driver',
setup:function(sc,L){var g=sc.g={};
g.start=MP.glow(sc,L,50.54,75.24,8,8,'255,65,45');
g.route=MP.glow(sc,L,43,73,2.4,2.4,'255,180,150');
g.dash=[[72.4,78,15,1.5],[96.9,79.2,10,1.8]].map(function(p){return MP.glow(sc,L,p[0],p[1],p[2],p[3],'255,35,40');});
g.lamps=[[558,115],[667,330],[1350,340],[1455,290],[1645,245]].map(function(p){return MP.glow(sc,L,p[0]/1672*100,p[1]/941*100,3,4,'255,205,125');});},
cam:MP.cam({push:0.035,ox:58,oy:46}),
dom:function(sc,lt){var g=sc.g,k=MP.reduced?0.5:0.5+0.5*Math.sin(MP.TAU*0.8*lt);
MP.put(g.start,0.12+0.2*k,1+0.04*k);g.dash.forEach(function(el){MP.put(el,0.18+0.08*k,1);});
g.lamps.forEach(function(el,i){MP.put(el,0.14+0.09*(MP.reduced?0.5:MP.flick(lt+i)),1);});
var u=MP.clamp(lt/2.3,0,1)*(path.length-1),i=Math.min(path.length-2,Math.floor(u)),p=u-i;
g.route.style.left=MP.lerp(path[i][0],path[i+1][0],p)/1672*100+'%';
g.route.style.top=MP.lerp(path[i][1],path[i+1][1],p)/941*100+'%';
MP.put(g.route,MP.reduced?0:0.5*Math.sin(Math.PI*MP.clamp(lt/2.8,0,1)),1);}
});})();
