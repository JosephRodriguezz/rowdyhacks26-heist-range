/* Local fixture presenter. All visible activity is scripted, never executed as code. */
(function () {
  "use strict";
  const byId = id => document.getElementById(id);
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function clock(ms) {
    const seconds = Math.floor(ms / 1000);
    return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
  }
  try {
    const session = ArenaCore.validate(globalThis.ARENA_FIXTURE);
    const events = session.timeline;
    let selectedAgent = session.agents[0].id;
    let previousIndex = -1, previousStatus = "", previousRedCode = "", previousBlueCode = "";
    let frameTime = null, announceKey = "";
    const cards = new Map(), sceneButtons = [];
    const preloaded = new Set();
    const player = ArenaCore.createPlayer(session, render);
    function preload(index) {
      if (index < 0 || index >= events.length) return;
      const url = session.visual_scenes[events[index].visual.scene].backdrop;
      if (preloaded.has(url)) return;
      preloaded.add(url);
      const img = new Image(); img.src = url;
    }
    function publicEvents(state) { return state.status === "ready" ? [] : events.slice(0, state.index + 1); }
    function agentStatus(agent, state) {
      if (state.status === "ready") return "Ready";
      if (state.event.visual.active_agents.includes(agent.id)) return state.status === "playing" ? "Active" : "Paused at task";
      const appeared = publicEvents(state).some(event => event.visual.active_agents.includes(agent.id));
      return appeared ? "Task handed off" : "Standby";
    }
    function updateAgents(state) {
      session.agents.forEach(agent => {
        const card = cards.get(agent.id);
        card.classList.toggle("is-active", state.event.visual.active_agents.includes(agent.id) && state.status !== "ready");
        card.setAttribute("aria-pressed", String(selectedAgent === agent.id));
        card.querySelector(".agent-status").textContent = agentStatus(agent, state) + " · fixture";
      });
      const agent = session.agents.find(item => item.id === selectedAgent);
      byId("inspector-team").textContent = agent.team.toUpperCase() + " TEAM · FIXTURE";
      byId("inspector-name").textContent = agent.name;
      byId("inspector-role").textContent = agent.role;
      byId("inspector-task").textContent = agent.task;
      byId("inspector-status").textContent = agentStatus(agent, state);
      const list = byId("inspector-events"); list.replaceChildren();
      const relevant = publicEvents(state).filter(event => event.visual.active_agents.includes(agent.id) || event.actor_id === agent.id).slice(-3);
      if (!relevant.length) list.append(el("li", "", "No public activity yet."));
      relevant.forEach(event => list.append(el("li", "", event.time + " · " + event.summary)));
      if (agent.id === "red-scout" && state.index >= 3) list.append(el("li", "", "Demo handoff: route brief passed to Red Operator."));
      if (agent.id === "blue-monitor" && state.index >= 10) list.append(el("li", "", "Demo handoff: availability alert passed to Blue Defender."));
    }
    function updateTimeline(state) {
      const list = byId("timeline-list"); list.replaceChildren();
      const filter = byId("timeline-filter").value;
      const visible = publicEvents(state).filter(event => filter === "all" || event.team === filter);
      if (!visible.length) { list.append(el("li", "empty-events", "No events for this view yet.")); return; }
      visible.forEach(event => {
        const row = el("li");
        if (event.sequence === state.event.sequence) row.setAttribute("aria-current", "step");
        row.append(el("span", "event-time", event.time));
        const content = el("div");
        content.append(el("span", "event-actor", event.actor + " · FIXTURE"), el("p", "event-summary", event.summary));
        row.append(content); list.append(row);
      });
    }
    function render(state) {
      const event = state.event, visual = event.visual;
      const changed = previousIndex !== state.index;
      const statusChanged = previousStatus !== state.status;
      if (changed) {
        previousIndex = state.index;
        const frame = byId("scene-frame");
        frame.dataset.scene = visual.scene;
        frame.classList.remove("arrive");
        byId("scene-image").src = state.scene.backdrop;
        byId("scene-image").alt = state.scene.alt;
        requestAnimationFrame(() => { if (player.snapshot().index === state.index) frame.classList.add("arrive"); });
        byId("stage-title").textContent = event.title;
        byId("phase-label").textContent = visual.phase.toUpperCase();
        byId("scene-number").textContent = String(state.index + 1).padStart(2, "0") + " / 14";
        byId("scene-caption").textContent = event.summary;
        byId("bank-screen").hidden = visual.scene !== "vault";
        byId("red-screen").hidden = visual.scene !== "vault";
        byId("dispatch-screen").hidden = visual.scene !== "dispatch";
        byId("blue-screen").hidden = visual.scene !== "pursuit";
        byId("bank-status").textContent = "● " + visual.bank;
        byId("bank-status").dataset.state = visual.bank;
        byId("red-status").textContent = visual.red_status.replace("Scripted action", "Demo action").replace("Story: ", "");
        byId("blue-status").textContent = visual.blue_status.replace("Scripted action", "Demo action");
        byId("red-result").textContent = state.index >= 4 ? "✓ Demo action complete" : "Action pending";
        byId("blue-result").textContent = state.index >= 11 ? "✓ Demo recovery complete" : state.index >= 10 ? "Recovery in progress" : "Recovery pending";
        sceneButtons.forEach((button, index) => {
          button.classList.toggle("is-past", index < state.index);
          if (index === state.index) button.setAttribute("aria-current", "step");
          else button.removeAttribute("aria-current");
        });
        preload(state.index + 1); preload(state.index + 2);
      }
      previousStatus = state.status;
      byId("session-status").textContent = ({ready:"Ready",playing:"Playing",paused:"Paused",stopped:"Stopped",complete:"Demo complete"})[state.status];
      byId("playback-toggle").textContent = state.status === "playing" ? "Ⅱ Pause" : state.status === "complete" ? "↻ Replay demo" : state.status === "ready" ? "▶ Start demo" : "▶ Resume";
      byId("playback-toggle").setAttribute("aria-pressed", String(state.status === "playing"));
      byId("step-back").disabled = state.index === 0;
      byId("step-forward").disabled = state.index === events.length - 1;
      byId("scene-start").hidden = state.index !== 0 || state.status === "playing";
      byId("end-card").hidden = state.status !== "complete";
      byId("elapsed-label").textContent = clock(state.position) + " / " + clock(state.total);
      const percentage = Math.min(100, state.position / state.total * 100);
      byId("playback-progress-fill").style.width = percentage + "%";
      byId("playback-progress").setAttribute("aria-valuenow", String(Math.round(percentage)));
      byId("playback-progress").setAttribute("aria-valuetext", "Scene " + (state.index + 1) + " of 14, " + clock(state.position));
      const red = ArenaCore.activityLines(event, "red", state.fraction).slice(-4).join("\n");
      const blue = ArenaCore.activityLines(event, "blue", state.fraction).slice(-4).join("\n");
      if (red !== previousRedCode) { byId("red-code").textContent = red; previousRedCode = red; }
      if (blue !== previousBlueCode) { byId("blue-code").textContent = blue; previousBlueCode = blue; }
      const key = state.index + ":" + state.status;
      if (key !== announceKey) {
        announceKey = key;
        byId("playback-message").textContent = state.status === "complete" ? "Demo complete · Replay to run the story again." : byId("session-status").textContent + " · Scene " + (state.index + 1) + " of 14 · " + event.title;
      }
      if (changed || statusChanged) { updateAgents(state); updateTimeline(state); }
    }
    session.agents.forEach(agent => {
      const card = el("button", "agent-card " + agent.team);
      card.type = "button";
      card.setAttribute("aria-pressed", String(agent.id === selectedAgent));
      card.append(el("span", "agent-team", agent.team.toUpperCase() + " TEAM"), el("span", "agent-name", agent.name), el("span", "agent-role", agent.role), el("span", "agent-status", "Ready · fixture"));
      card.addEventListener("click", () => { selectedAgent = agent.id; updateAgents(player.snapshot()); });
      cards.set(agent.id, card); byId("agent-grid").append(card);
    });
    events.forEach((event, index) => {
      const button = el("button", "", String(index + 1).padStart(2, "0"));
      button.type = "button"; button.title = event.title;
      button.setAttribute("aria-label", "Scene " + (index + 1) + ": " + event.title);
      button.addEventListener("click", () => player.seek(index));
      sceneButtons.push(button); byId("scene-nav").append(button);
    });
    function toggle() { if (player.snapshot().status === "playing") player.pause(); else player.play(); }
    byId("playback-toggle").addEventListener("click", toggle);
    byId("scene-start").addEventListener("click", () => player.play());
    byId("replay-button").addEventListener("click", () => player.play());
    byId("step-forward").addEventListener("click", () => player.next());
    byId("step-back").addEventListener("click", () => player.previous());
    byId("playback-stop").addEventListener("click", () => player.stop());
    byId("playback-reset").addEventListener("click", () => player.reset());
    byId("playback-speed").addEventListener("change", event => player.setSpeed(Number(event.target.value)));
    byId("timeline-filter").addEventListener("change", () => updateTimeline(player.snapshot()));
    const cinema = byId("cinema");
    function setPresentationButton(active) {
      byId("presentation-toggle").textContent = active ? "Exit cinema ⛶" : "Cinema view ⛶";
      byId("presentation-toggle").setAttribute("aria-pressed", String(active));
    }
    byId("presentation-toggle").addEventListener("click", async () => {
      if (document.fullscreenElement) { await document.exitFullscreen(); return; }
      if (cinema.classList.contains("presentation")) { cinema.classList.remove("presentation"); setPresentationButton(false); return; }
      try { if (!cinema.requestFullscreen) throw new Error("Fullscreen unavailable"); await cinema.requestFullscreen(); }
      catch { cinema.classList.add("presentation"); setPresentationButton(true); }
    });
    document.addEventListener("fullscreenchange", () => setPresentationButton(Boolean(document.fullscreenElement)));
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") { cinema.classList.remove("presentation"); setPresentationButton(Boolean(document.fullscreenElement)); return; }
      if (event.ctrlKey || event.metaKey || event.altKey || ["INPUT","TEXTAREA","SELECT","BUTTON","A"].includes(event.target.tagName) || event.target.isContentEditable) return;
      if (event.code === "Space") { event.preventDefault(); toggle(); }
      else if (event.key === "ArrowRight") { event.preventDefault(); player.next(); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); player.previous(); }
      else if (event.key.toLowerCase() === "r") { event.preventDefault(); player.reset(); }
    });
    document.addEventListener("visibilitychange", () => { frameTime = null; if (document.hidden) player.pause(); });
    byId("scene-image").addEventListener("error", () => {
      player.stop();
      byId("load-error").hidden = false;
      byId("load-error").textContent = "A scene image could not load. Keep index.html and the scenes-v2 folder together, then reopen the demo.";
    });
    function tick(now) {
      if (frameTime !== null) player.tick(Math.min(1000, Math.max(0, now - frameTime)));
      frameTime = now; requestAnimationFrame(tick);
    }
    render(player.snapshot()); preload(0); requestAnimationFrame(tick);
  } catch (error) {
    byId("load-error").hidden = false;
    byId("load-error").textContent = "The demo could not start: " + error.message;
    byId("playback-toggle").disabled = true;
  }
})();
