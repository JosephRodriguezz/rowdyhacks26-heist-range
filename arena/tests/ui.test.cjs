const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const core = require("../demo-core.js");
const root=path.resolve(__dirname,"..");
class Element {
  constructor(tag="div",id=""){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.attributes={};this.dataset={};this.style={};this.handlers={};this.className="";this.textContent="";this.hidden=false;this.disabled=false;
    this.classList={contains:c=>this.className.split(/\s+/).includes(c),add:c=>{if(!this.classList.contains(c))this.className+=(this.className?" ":"")+c;},remove:c=>{this.className=this.className.split(/\s+/).filter(x=>x!==c).join(" ");},toggle:(c,on)=>{if(on)this.classList.add(c);else this.classList.remove(c);}};
  }
  setAttribute(k,v){this.attributes[k]=String(v);}
  getAttribute(k){return this.attributes[k];}
  removeAttribute(k){delete this.attributes[k];}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  querySelector(selector){const cls=selector.slice(1);for(const child of this.children){if(child.classList.contains(cls))return child;const nested=child.querySelector(selector);if(nested)return nested;}return null;}
  addEventListener(name,fn){(this.handlers[name]??=[]).push(fn);}
  async dispatch(name,props={}){for(const fn of this.handlers[name]||[])await fn({target:this,preventDefault(){},...props});}
}
function app(data) {
  const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
  const document=new Element("document"); const ids=new Map();
  for(const match of html.matchAll(/<([a-z][a-z0-9-]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)){
    const node=new Element(match[1],match[2]);node.hidden=/\shidden\b/.test(match[0]);ids.set(match[2],node);
  }
  document.getElementById=id=>{if(!ids.has(id))throw Error("Missing DOM ID: "+id);return ids.get(id);};
  document.createElement=tag=>new Element(tag);document.hidden=false;document.fullscreenElement=null;
  ids.get("timeline-filter").value="all";ids.get("playback-speed").value="1";
  const frames=[];const context={document,ArenaCore:core,ARENA_FIXTURE:data||JSON.parse(fs.readFileSync(path.join(root,"fixtures/session.json"),"utf8")),Image:class{},requestAnimationFrame:fn=>frames.push(fn)};
  vm.runInNewContext(fs.readFileSync(path.join(root,"arena.js"),"utf8"),context);
  async function click(id){await ids.get(id).dispatch("click");}
  function frame(time){const batch=frames.splice(0);batch.forEach(fn=>fn(time));}
  return {document,ids,click,frame};
}
test("controls run, pause, step, stop, reset, and complete without DOM errors",async()=>{
  const a=app();const id=x=>a.ids.get(x);
  assert.equal(id("load-error").hidden,true);assert.equal(id("scene-nav").children.length,14);assert.equal(id("agent-grid").children.length,4);
  await a.click("playback-toggle");a.frame(0);a.frame(1000);a.frame(2000);a.frame(3000);
  assert.equal(id("scene-number").textContent,"02 / 14");
  await a.click("playback-toggle");a.frame(4000);a.frame(5000);assert.equal(id("scene-number").textContent,"02 / 14");
  await a.click("step-forward");assert.equal(id("scene-number").textContent,"03 / 14");
  await a.click("playback-stop");assert.equal(id("session-status").textContent,"Stopped");
  await a.click("playback-reset");assert.equal(id("scene-number").textContent,"01 / 14");assert.equal(id("session-status").textContent,"Ready");
  await a.click("playback-toggle");for(let t=6000;t<=94000;t+=1000)a.frame(t);
  assert.equal(id("session-status").textContent,"Demo complete");assert.equal(id("end-card").hidden,false);
  await a.click("replay-button");assert.equal(id("scene-number").textContent,"01 / 14");assert.equal(id("end-card").hidden,true);
});
test("each scene shows only its designated screens; rewind removes future activity",async()=>{
  const a=app(),id=x=>a.ids.get(x);
  for(let i=0;i<14;i++){
    await id("scene-nav").children[i].dispatch("click");
    assert.equal(id("bank-screen").hidden,i!==3);assert.equal(id("red-screen").hidden,i!==3);
    assert.equal(id("dispatch-screen").hidden,i!==5);assert.equal(id("blue-screen").hidden,i!==10);
    if(i<10)assert.equal(id("blue-code").textContent,"");
  }
  await id("scene-nav").children[3].dispatch("click");
  assert.equal(id("bank-status").textContent,"● ONLINE");assert.equal(id("blue-result").textContent,"Recovery pending");
  assert.equal(id("timeline-list").children.length,4);
});
test("agent selection and timeline filters work; hidden page pauses playback",async()=>{
  const a=app(),id=x=>a.ids.get(x);await id("scene-nav").children[10].dispatch("click");
  await id("agent-grid").children[3].dispatch("click");assert.equal(id("inspector-name").textContent,"Blue Defender");
  id("timeline-filter").value="blue";await id("timeline-filter").dispatch("change");
  assert.equal(id("timeline-list").children.length,2);
  await a.click("playback-toggle");a.document.hidden=true;await a.document.dispatch("visibilitychange");
  assert.equal(id("session-status").textContent,"Paused");
});
test("cinema fallback toggles and Escape exits",async()=>{
  const a=app(),id=x=>a.ids.get(x);await a.click("presentation-toggle");assert.ok(id("cinema").classList.contains("presentation"));
  await a.document.dispatch("keydown",{key:"Escape",target:new Element("body")});assert.equal(id("cinema").classList.contains("presentation"),false);
});
test("private or live data fails closed with visible error",()=>{
  const fixture=JSON.parse(fs.readFileSync(path.join(root,"fixtures/session.json"),"utf8"));fixture.source_mode="LIVE";
  const a=app(fixture);assert.equal(a.ids.get("load-error").hidden,false);assert.equal(a.ids.get("playback-toggle").disabled,true);
});
