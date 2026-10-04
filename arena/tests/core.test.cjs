const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const core = require("../demo-core.js");
const root = path.resolve(__dirname, "..");
const fixture = JSON.parse(fs.readFileSync(path.join(root, "fixtures/session.json"), "utf8"));
const clone = () => structuredClone(fixture);
test("fixture uses all 14 approved scene assets and identical direct-open bundle", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "scenes-v2/manifest.json"), "utf8"));
  const context = {}; vm.runInNewContext(fs.readFileSync(path.join(root,"fixtures/session.js"),"utf8"), context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.ARENA_FIXTURE)), fixture);
  core.validate(fixture);
  fixture.timeline.forEach((event, i) => {
    assert.equal(manifest[i].approval, "APPROVED");
    assert.equal(fixture.visual_scenes[event.visual.scene].backdrop, "scenes-v2/" + manifest[i].file);
    assert.ok(fs.existsSync(path.join(root, "scenes-v2", manifest[i].file)));
  });
});
test("pause and stop freeze the clock; resume continues remaining scene duration", () => {
  const p = core.createPlayer(clone()); p.play(); p.tick(2000); p.pause(); p.tick(20000);
  assert.equal(p.snapshot().elapsed, 2000); assert.equal(p.snapshot().index, 0);
  p.play(); p.tick(1000); assert.equal(p.snapshot().index, 1);
  p.stop(); const position = p.snapshot().position; p.tick(90000);
  assert.equal(p.snapshot().position, position); assert.equal(p.snapshot().status, "stopped");
});
test("full simulation includes outage, delayed Blue code, recovery, and terminal arrest", () => {
  const p = core.createPlayer(clone()); p.play();
  for (let i=0; i<14; i++) {
    const s=p.snapshot(); assert.equal(s.index,i);
    assert.equal(s.event.visual.bank, i<4 || i>=11 ? "ONLINE" : i===10 ? "RECOVERING" : "OFFLINE");
    if(i<10) assert.deepEqual(core.activityLines(s.event,"blue",1),[]);
    p.tick(s.event.duration_ms);
  }
  assert.equal(p.snapshot().index,13); assert.equal(p.snapshot().status,"complete");
  assert.equal(p.snapshot().position,p.snapshot().total); assert.equal(p.snapshot().event.referee.verified,false);
});
test("jump, rewind, reset and replay clear future scene state", () => {
  const p=core.createPlayer(clone()); p.seek(11); assert.equal(p.snapshot().event.visual.blue_check,true);
  p.previous(); assert.equal(p.snapshot().index,10); p.seek(3);
  assert.equal(p.snapshot().event.visual.bank,"ONLINE"); assert.deepEqual(core.activityLines(p.snapshot().event,"blue",1),[]);
  p.reset(); assert.equal(p.snapshot().status,"ready"); assert.equal(p.snapshot().elapsed,0);
  p.play(); p.tick(100000); p.play(); assert.equal(p.snapshot().index,0); assert.equal(p.snapshot().position,0);
});
test("speed scales time and code lines progress with scene time", () => {
  const p=core.createPlayer(clone()); p.setSpeed(2); p.play(); p.tick(1500); assert.equal(p.snapshot().index,1);
  p.seek(3); const e=p.snapshot().event; assert.equal(core.activityLines(e,"red",0).length,1);
  assert.equal(core.activityLines(e,"red",1).length,e.public_activity.red.length);
  assert.throws(()=>p.setSpeed(9)); assert.throws(()=>p.seek(-1));
});
test("source, audience, order, early Blue code and verdict errors are rejected", () => {
  const mutations=[
    s=>s.source_mode="LIVE",s=>s.timeline[0].visibility="red_private",
    s=>s.timeline[1].sequence=1,s=>s.timeline[1].event_id=s.timeline[0].event_id,
    s=>s.timeline[3].visual.blue_code_active=true,
    s=>s.timeline[5].public_activity.blue=["private plan"],
    s=>s.timeline[11].referee.verified=true,s=>s.timeline[0].session_id="other-session",
    s=>s.visual_scenes.driver.backdrop="https://untrusted.example/image.png"
  ];
  mutations.forEach(mutate=>{const data=clone();mutate(data);assert.throws(()=>core.validate(data));});
});
