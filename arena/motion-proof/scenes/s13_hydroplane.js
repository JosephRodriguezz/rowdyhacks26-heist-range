/* Scene 13: braking jolt, wheel spray and pole sparks over the approved crash still.
 * Car, pole, officer and check stay still. Check retains scene 12's exact size.
 * Art anchors: spray 1100,450 / 1425,450; impact 1470,395; check 1233,693.
 * 96 particles, 7 glows; emergency wash 2.2 Hz, one impact at 0.5 seconds. */
(function(){'use strict';var MP=window.MP;
var rain=MP.fx.rain({seed:131,n:46,box:MP.rectU(28,18,100,57),alpha:[0.16,0.36],speed:[0.7,1],len:[0.014,0.03]});
var a=MP.fx.splash({seed:132,n:18,x:1100/1672,y:450/941,speed:[0.07,0.15],life:[0.3,0.55]});
var b=MP.fx.splash({seed:133,n:18,x:1425/1672,y:450/941,speed:[0.07,0.16],life:[0.3,0.55]});
var sparks=MP.fx.sparks({seed:134,n:14,x:[0.867,0.88],y:[0.4,0.44],speed:[0.05,0.12],life:[0.15,0.4]});
var jolt=MP.cam({push:0.016,ox:60,oy:20,shake:{t0:0.5,amp:0.35,decay:0.25,kick:0.013,kickDecay:0.3}});
MP.register({id:'hydroplane',
setup:function(sc,L){var g=sc.g={};
g.bar=MP.lightbar(sc,L,{hz:2.2,lights:[
{x:42.3,y:2.1,w:8,h:2.5,rgb:MP.RED,max:0.5},{x:60.4,y:1.4,w:8,h:2.5,rgb:MP.BLUE,phase:0.5,max:0.5},
{x:44.9,y:56.8,w:7,h:2,rgb:MP.RED,max:0.4},{x:75.8,y:59.1,w:9,h:2,rgb:MP.BLUE,phase:0.5,max:0.4}]});
g.check=MP.glow(sc,L,73.74,73.64,12,12,'70,255,110');
g.lamps=[[1500,60],[1385,125]].map(function(p){return MP.glow(sc,L,p[0]/1672*100,p[1]/941*100,5,6,'255,205,135');});},
cam:function(sc,lt){if(MP.reduced)return MP.CAM0;
var c=jolt(sc,lt),prior=MP.defs.pursuit.cam(sc,19.5),settle=1-MP.smooth(0,1.4,lt);
c[0]+=0.06;c[1]+=prior[1]*settle;c[2]+=prior[2]*settle;return c;},
dom:function(sc,lt){var g=sc.g;g.bar.update(19.5+lt,1);MP.put(g.check,0.1,1);
var dip=MP.reduced?0:MP.smooth(0.5,0.65,lt)-MP.smooth(0.65,1,lt);
g.lamps.forEach(function(el){MP.put(el,0.22-0.13*dip,1);});},
draw:function(sc,lt){
  // Spray remains outside the car instead of falling across the dashboard display.
  var c=MP.ctx,k=MP.cw/1672;c.save();c.beginPath();c.rect(470*k,170*k,1202*k,375*k);c.clip();
  rain.draw(lt);a.draw(lt-0.5);b.draw(lt-0.5);sparks.draw(lt-0.5);c.restore();
}
});})();
