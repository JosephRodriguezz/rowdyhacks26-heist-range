// In-memory DOM/canvas contract tests. These do not render browser pixels or certify visual alignment.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'index.html'),'utf8');
function canvasContext(record=false){
  const log=[],base={log,createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)})};
  const ctx=new Proxy(base,{get(o,k){if(k in o)return o[k];return (...args)=>{
    for(const a of args)if(typeof a==='number')assert.ok(Number.isFinite(a),'Nonfinite canvas argument '+k);
    if(record)log.push([k,...args.map(a=>typeof a==='object'?(a?.tagName||'gradient'):a)]);
    if(k==='createRadialGradient'||k==='createLinearGradient')return {addColorStop(p){assert.ok(p>=0&&p<=1);}};
  };}});return ctx;
}
class Element{
  constructor(tag='div'){
    this.tagName=tag.toUpperCase();this.children=[];this.parentNode=null;this.style={};this.attributes={};this.dataset={};this.handlers={};this.className='';this._text='';this.hidden=false;this.value='';this.offsetOverride=null;
    this.classList={contains:c=>this.className.split(/\s+/).includes(c),add:c=>{if(!this.classList.contains(c))this.className+=' '+c;},remove:c=>{this.className=this.className.split(/\s+/).filter(x=>x!==c).join(' ');},toggle:(c,on)=>on?this.classList.add(c):this.classList.remove(c)};
  }
  appendChild(e){e.parentNode=this;this.children.push(e);return e;}
  insertBefore(e,b){e.parentNode=this;const i=this.children.indexOf(b);if(i<0)this.children.push(e);else this.children.splice(i,0,e);return e;}
  setAttribute(k,v){this.attributes[k]=String(v);if(k==='class')this.className=v;if(k==='id')this.id=v;if(k==='style')this.style.cssText=v;if(k==='value')this.value=v;}
  getAttribute(k){return this.attributes[k];} removeAttribute(k){delete this.attributes[k];}
  set textContent(v){this._text=String(v);this.children=[];} get textContent(){return this._text+this.children.map(e=>e.textContent).join('');}
  set innerHTML(v){this.children=[];this._text='';parse(v,this);} get innerHTML(){return this.textContent;}
  matches(s){if(s[0]==='.')return this.classList.contains(s.slice(1));if(s[0]==='#')return this.id===s.slice(1);const a=s.match(/^(\w+)\[value="([^"]+)"\]$/);if(a)return this.tagName===a[1].toUpperCase()&&this.value===a[2];return this.tagName===s.toUpperCase();}
  querySelectorAll(s){return this.children.flatMap(e=>[...(e.matches(s)?[e]:[]),...e.querySelectorAll(s)]);} querySelector(s){return this.querySelectorAll(s)[0]||null;}
  closest(s){return this.matches(s)?this:this.parentNode?.closest(s)||null;}
  addEventListener(k,f){(this.handlers[k]??=[]).push(f);} dispatch(k,props={}){for(const f of this.handlers[k]||[])f({target:this,preventDefault(){},...props});} focus(){}
  dimension(key){
    if(this.id==='stage'||this.classList.contains('world')||this.classList.contains('fx-layer'))return key==='width'?1226:1226*941/1672;
    const css=this.style[key]||this.style.cssText?.match(new RegExp('(?:^|;)'+key+':([^;]+)'))?.[1];
    if(!css)return this.parentNode?.dimension(key)||1226;
    const v=parseFloat(css);return css.endsWith('cqw')?v*12.26:css.endsWith('%')?v/100*(this.parentNode?.dimension(key)||1226):v;
  }
  get offsetWidth(){return this.dimension('width');}get offsetHeight(){return this.dimension('height');}
  getBoundingClientRect(){return {width:this.offsetWidth,height:this.offsetHeight};}
  getContext(){return this.ctx||(this.ctx=canvasContext(this.id==='fx'));}
}
function parse(src,parent){
  const stack=[parent];
  for(const m of src.matchAll(/<\/?[a-zA-Z][^>]*>|([^<]+)/g)){
    const t=m[0];if(!t.startsWith('<')){stack.at(-1)._text+=t;continue;}
    if(t.startsWith('</')){if(stack.length>1)stack.pop();continue;}
    const tag=t.match(/^<(\w+)/)[1],e=new Element(tag);for(const a of t.matchAll(/([\w-]+)="([^"]*)"/g))e.setAttribute(a[1],a[2]);
    e.hidden=/\shidden(?:\s|>)/.test(t);stack.at(-1).appendChild(e);
    if(!/^(input|meta|link|img|br|hr)$/i.test(tag)&&!t.endsWith('/>'))stack.push(e);
  }
}
function app(search=''){
  const document=new Element('document');document.head=new Element('head');parse(html.match(/<body>([\s\S]*?)<noscript>/)[1],document);
  document.createElement=tag=>new Element(tag);document.getElementById=id=>{const e=document.querySelector('#'+id);assert.ok(e,'Missing '+id);return e;};
  const window=new Element('window');window.document=document;window.location={search};window.devicePixelRatio=1;window.matchMedia=()=>({matches:false});
  const frames=new Map(),errors=[];let next=1;
  const context={window,document,URLSearchParams,console:{error:s=>errors.push(s)},Image:class extends Element{constructor(){super('img');}},requestAnimationFrame:fn=>{const id=next++;frames.set(id,fn);return id;},cancelAnimationFrame:id=>frames.delete(id)};
  vm.createContext(context);
  for(const m of html.matchAll(/<script src="([^"]+)"/g))vm.runInContext(fs.readFileSync(path.join(root,m[1]),'utf8'),context,{filename:m[1]});
  const id=k=>document.getElementById(k);
  function frame(ts){const batch=[...frames.values()];frames.clear();batch.forEach(f=>f(ts));}
  function seek(t){id('scrub').value=String(t);id('scrub').dispatch('input');}
  function snapshot(){function tree(e){return [e.className,e._text,e.style,e.hidden,e.children.map(tree)];}return JSON.stringify([id('world').style,tree(id('world').children.find(e=>e.classList.contains('fx-layer')&&e.classList.contains('on'))),id('fx').ctx.log]);}
  function capture(t){id('fx').ctx.log.length=0;seek(t);return snapshot();}
  return {window,document,id,frame,seek,capture,errors,frames};
}
test('all 14 scene files and approved assets load; complete hooks at every sampled time',()=>{
  const a=app(),MP=a.window.MP,story=a.window.MP_STORY;
  assert.equal(story.scenes.length,14);assert.equal(story.total,85.5);assert.equal(a.id('chips').children.length,14);
  for(const reduced of [false,true]){
    a.id('reduced').checked=reduced;a.id('reduced').dispatch('change');
    for(const sc of story.scenes){
      assert.equal(typeof MP.defs[sc.id].setup,'function',sc.id+' is still a stub');assert.ok(!MP.defs[sc.id].interim);
      assert.ok(fs.existsSync(path.join(root,'../scenes-v2',sc.file)));
      for(const lt of [0,0.2,0.55,1.5,sc.dur/2,sc.dur-0.001]){
        a.seek(sc.start+lt);assert.equal(a.id('hudBank').dataset.state,sc.bank);assert.equal(a.id('hudAlarm').dataset.state,sc.alarm?'on':'');
        if(reduced)assert.equal(a.id('world').style.transform,'translate3d(0.000%,0.000%,0) scale(1.0000)');
      }
    }
  }
  assert.deepEqual(a.errors,[]);
});
test('seek backwards and replay reproduce identical DOM and canvas commands',()=>{
  const a=app();for(const sc of a.window.MP_STORY.scenes){const t=sc.start+sc.dur*0.63,first=a.capture(t);a.seek(85.5);a.seek(0);assert.equal(a.capture(t),first,sc.id+' changed after seeking');}assert.deepEqual(a.errors,[]);
});
test('full clock run, pause/resume, visibility pause, replay and keyboard controls',()=>{
  const a=app(),click=k=>a.id(k).dispatch('click');click('play');
  for(let ts=100;ts<=90000;ts+=100)a.frame(ts);
  assert.equal(a.id('endCard').hidden,false);assert.equal(a.id('play').textContent,'Play again');assert.equal(a.frames.size,0);
  click('replay');a.frame(91000);a.frame(91100);click('play');const t=a.id('scrub').value;a.frame(92000);assert.equal(a.id('scrub').value,t);assert.equal(a.frames.size,0);
  click('play');assert.equal(a.frames.size,1);a.document.hidden=true;a.document.dispatch('visibilitychange');assert.equal(a.frames.size,0);
  a.document.dispatch('keydown',{key:'6'});assert.equal(a.id('hudBlue').textContent,'Alert received');
  a.document.dispatch('keydown',{key:']'});assert.match(a.id('hudScene').textContent,/07/);
  a.document.dispatch('keydown',{key:'r'});assert.match(a.id('hudScene').textContent,/01/);assert.equal(a.id('play').textContent,'Pause');
  assert.deepEqual(a.errors,[]);
});
test('dispatch contains alert only; Blue feed types in 11 and dissolves in 12; site dark in 05',()=>{
  const a=app(),active=()=>a.id('world').children.find(e=>e.classList.contains('fx-layer')&&e.classList.contains('on'));
  a.seek(33);assert.match(active().textContent,/BANK LAB ALERT/);assert.equal(active().querySelectorAll('pre').length,0);
  a.seek(55.2);const early=active().querySelector('pre').textContent;a.seek(67.9);const full=active().querySelector('pre').textContent;
  assert.ok(full.length>early.length);assert.match(full,/awaiting demo health event/);
  a.seek(68);assert.equal(active().querySelector('pre').textContent,full);
  a.seek(70);assert.equal(active().querySelector('.code').style.visibility,'hidden');
  a.seek(27);assert.equal(active().querySelector('.site').style.visibility,'hidden');
  a.seek(20);assert.equal(active().querySelector('.pill').textContent,'ONLINE');
});
test('scene 11 -> 12 -> 13 camera continuity and no transition dip on shared viewpoints',()=>{
  const a=app('?play=1'),MP=a.window.MP,story=a.window.MP_STORY.scenes;
  assert.deepEqual(Array.from(MP.defs.pursuit.cam(story[10],13)),Array.from(MP.defs.recovered.cam(story[11],0)));
  assert.deepEqual(Array.from(MP.defs.recovered.cam(story[11],6.5)),Array.from(MP.defs.hydroplane.cam(story[12],0)));
  a.seek(68);assert.equal(a.id('fade').style.opacity,'0.000');
});
test('effect failure shows error and hides the partial overlay',()=>{
  const a=app();a.window.MP.defs.pursuit.dom=()=>{throw Error('test failure');};a.seek(57);
  assert.equal(a.errors.length,1);assert.equal(a.id('errBanner').hidden,false);
  assert.equal(a.id('world').children.find(e=>e.classList.contains('fx-layer')&&e.classList.contains('on')).style.visibility,'hidden');
  a.seek(58);assert.equal(a.errors.length,1);
});
