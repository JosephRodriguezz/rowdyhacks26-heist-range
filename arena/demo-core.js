/* Fixture playback engine. No networking, target actions or verdict inference. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ArenaCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  function validate(session) {
    if (!session || session.source_mode !== "FIXTURE") throw new Error("Demo v0 requires FIXTURE data.");
    if (!Array.isArray(session.timeline) || session.timeline.length !== 14) throw new Error("Expected the approved 14-scene sequence.");
    const ids = new Set();
    session.timeline.forEach((event, i) => {
      if (event.sequence !== i + 1 || ids.has(event.event_id)) throw new Error("Events must have unique IDs and consecutive ordered sequences.");
      ids.add(event.event_id);
      if (event.visibility !== "judge_safe" || event.source_mode !== "FIXTURE" || event.producer !== "fixture" || event.session_id !== session.session_id) throw new Error("Event source or audience does not match this demo.");
      if (!Number.isFinite(event.duration_ms) || event.duration_ms < 1000) throw new Error("Invalid scene duration.");
      const scene = session.visual_scenes[event.visual.scene];
      if (!scene || !/^scenes-v2\/[a-z0-9_-]+\.png$/.test(scene.backdrop)) throw new Error("Invalid local scene asset.");
      if (event.referee.status !== "NOT_CONNECTED" || event.referee.verified !== false) throw new Error("Demo art cannot establish a referee verdict.");
      if (i < 10 && (event.visual.blue_code_active || event.public_activity.blue.length)) throw new Error("Blue code must remain inactive before scene 11.");
    });
    return session;
  }
  function createPlayer(input, onChange = function () {}) {
    const session = validate(input);
    const events = session.timeline;
    const total = events.reduce((sum, event) => sum + event.duration_ms, 0);
    let index = 0, elapsed = 0, status = "ready", speed = 1;
    function snapshot() {
      const event = events[index];
      const position = events.slice(0, index).reduce((sum, item) => sum + item.duration_ms, 0) + elapsed;
      return { index, elapsed, status, speed, event, scene: session.visual_scenes[event.visual.scene], total, position, fraction: elapsed / event.duration_ms };
    }
    function emit() { const state = snapshot(); onChange(state); return state; }
    function seek(value) {
      if (!Number.isInteger(value) || value < 0 || value >= events.length) throw new Error("Scene is outside the demo.");
      index = value; elapsed = 0; status = "paused"; return emit();
    }
    return {
      snapshot,
      play() { if (status === "complete") { index = 0; elapsed = 0; } status = "playing"; return emit(); },
      pause() { if (status === "playing") status = "paused"; return emit(); },
      stop() { status = "stopped"; return emit(); },
      reset() { index = 0; elapsed = 0; status = "ready"; return emit(); },
      seek,
      next() { return seek(Math.min(index + 1, events.length - 1)); },
      previous() { return seek(Math.max(index - 1, 0)); },
      setSpeed(value) { if (![0.5, 1, 2].includes(value)) throw new Error("Unsupported speed."); speed = value; return emit(); },
      tick(delta) {
        if (status !== "playing" || !Number.isFinite(delta) || delta <= 0) return snapshot();
        elapsed += delta * speed;
        while (elapsed >= events[index].duration_ms) {
          if (index === events.length - 1) { elapsed = events[index].duration_ms; status = "complete"; break; }
          elapsed -= events[index].duration_ms; index += 1;
        }
        return emit();
      }
    };
  }
  function activityLines(event, team, fraction) {
    if (team === "blue" && !event.visual.blue_code_active) return [];
    const lines = event.public_activity[team] || [];
    const count = Math.max(1, Math.min(lines.length, Math.floor(Math.max(0, fraction) * (lines.length + 1)) + 1));
    return lines.slice(0, count);
  }
  return { validate, createPlayer, activityLines };
});
