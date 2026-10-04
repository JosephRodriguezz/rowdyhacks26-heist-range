/* Scene 14: rain, puddles, lights and a settling camera over the arrest still.
 * Officer, robber, cuffs and cars do not move. No invented verification text.
 * Art anchors: bar 285,293 blue / 411,295 red; headlights 75,435 / 350,445;
 * tail 1145,515; steam 1490,480. Ten glows, 72 particles.
 * Emergency lights 2.2 Hz, fading to 40% during the last second. */
(function(){'use strict';var MP=window.MP;
var rain=MP.fx.rain({seed:141,n:52,box:MP.rectU(0,0,100,100),alpha:[0.09,0.25],speed:[0.6,0.9],len:[0.012,0.028]});
var ripples=MP.fx.ripples({seed:142,n:16,box:MP.rectU(0,82,100,100),rmax:0.017,alpha:[0.10,0.24]});
var steam=MP.fx.dust({seed:143,n:4,x:[0.885,0.90],y:[0.49,0.52],rgb:'175,190,205',scale:0.28,alpha:0.2});
MP.register({id:'arrest',
setup:function(sc,L){var g=sc.g={};
g.bar=MP.lightbar(sc,L,{hz:2.2,lights:[
{x:17,y:31.2,w:8,h:3,rgb:MP.BLUE,phase:0.5,max:0.5},{x:24.6,y:31.4,w:8,h:3,rgb:MP.RED,max:0.5},
{x:14,y:78,w:8,h:17,rgb:MP.BLUE,phase:0.5,max:0.28},{x:24,y:79,w:8,h:17,rgb:MP.RED,max:0.28}]});
g.heads=[[75,435],[350,445]].map(function(p){return MP.glow(sc,L,p[0]/1672*100,p[1]/941*100,5,5,'255,235,180');});
g.lamps=[[282,110],[520,203],[1330,63]].map(function(p){return MP.glow(sc,L,p[0]/1672*100,p[1]/941*100,5,6,'255,210,135');});
g.tail=MP.glow(sc,L,68.48,54.73,5,6,'255,65,40');},
cam:MP.cam({push:0.035,ox:55,oy:55,ease:'out'}),
dom:function(sc,lt){var g=sc.g;g.bar.update(lt,1-0.6*MP.smooth(5.5,6.5,lt));
g.heads.forEach(function(el){MP.put(el,0.24,1);});
g.lamps.forEach(function(el,i){MP.put(el,0.13+0.06*(MP.reduced?0.5:MP.flick(lt+i)),1);});
MP.put(g.tail,0.2+0.05*Math.sin(MP.TAU*0.4*lt),1);},
draw:function(sc,lt){rain.draw(lt);ripples.draw(lt);if(!MP.reduced)steam.draw(lt);}
});})();
