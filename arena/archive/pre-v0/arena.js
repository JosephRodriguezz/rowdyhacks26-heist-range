const FIXTURE_URL = "fixtures/session.json";
const PLAYBACK_INTERVAL_MS = 2400;

function makeElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderAgent(agent) {
  const team = String(agent.team).toLowerCase();
  const card = makeElement("article", `agent-card ${team}`);
  card.dataset.agentId = agent.id;
  card.setAttribute("aria-label", `${agent.team} team, ${agent.name}`);

  const top = makeElement("div", "agent-topline");
  top.append(
    makeElement("span", "team-tag", `${team.toUpperCase()} TEAM`),
    makeElement("span", "agent-status", "Ready · fixture")
  );
  card.append(
    top,
    makeElement("h3", "agent-name", agent.name),
    makeElement("p", "agent-role", agent.role),
    makeElement("p", "agent-task", agent.task)
  );
  return card;
}

function renderEvent(event, index) {
  const item = makeElement("li", "timeline-event");
  item.dataset.eventIndex = String(index);
  const marker = makeElement("span", "event-marker", String(event.sequence).padStart(2, "0"));
  marker.setAttribute("aria-hidden", "true");
  item.append(
    marker,
    makeElement("span", "event-sequence", event.time),
    makeElement("span", "event-actor", event.actor),
    makeElement("p", "event-summary", event.summary)
  );
  return item;
}

function setScene(scene) {
  if (!scene) return;
  const frame = document.querySelector(".scene-frame");
  const image = document.getElementById("scene-image");
  const changed = image.getAttribute("src") !== scene.backdrop;
  if (changed) {
    frame.classList.remove("scene-transition");
    image.src = scene.backdrop;
    image.alt = scene.alt;
    requestAnimationFrame(() => {
      frame.classList.add("scene-transition");
      window.setTimeout(() => frame.classList.remove("scene-transition"), 850);
    });
  }
  document.getElementById("scene-label").textContent = scene.label;
}

function loadFixture() {
  return fetch(FIXTURE_URL, { cache: "no-store" }).then((response) => {
    if (!response.ok) throw new Error(`Fixture request failed (${response.status}).`);
    return response.json();
  });
}

function initializePlayback(session) {
  if (session.source_mode !== "FIXTURE") {
    throw new Error("This walkthrough only accepts a FIXTURE session.");
  }

  const events = [...session.timeline].sort((a, b) => a.sequence - b.sequence);
  if (!events.length) throw new Error("The fixture has no events to play.");

  document.title = `RowdyHacks26 | ${session.session_name}`;
  document.getElementById("session-name").textContent = session.session_name;
  document.getElementById("scenario-summary").textContent = session.scenario_summary;
  document.getElementById("agent-count").textContent = `${session.agents.length} agents`;

  const agentGrid = document.getElementById("agent-grid");
  session.agents.forEach((agent) => agentGrid.append(renderAgent(agent)));

  const timeline = document.getElementById("timeline-list");
  events.forEach((event, index) => timeline.append(renderEvent(event, index)));

  const progress = document.querySelector(".playback-progress");
  progress.setAttribute("aria-valuemax", String(events.length));

  const image = document.getElementById("scene-image");
  image.src = session.scene.backdrop;
  image.alt = session.scene.alt;
  document.getElementById("scene-label").textContent = session.scene.label;
  document.getElementById("scene-caption").textContent = session.scene.caption;

  const statePanel = document.getElementById("scene-live-state");
  const stateTitle = document.getElementById("scene-state-title");
  const stateDetail = document.getElementById("scene-state-detail");
  const alarm = document.getElementById("scene-alarm");
  const phase = document.getElementById("phase-label");
  const message = document.getElementById("playback-message");
  const fill = document.getElementById("playback-progress-fill");
  const playButton = document.getElementById("playback-toggle");
  let currentIndex = -1;
  let timer = null;

  function stopPlayback() {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
    playButton.textContent = "Play fixture";
    playButton.setAttribute("aria-pressed", "false");
  }

  function renderFrame(index, announcement) {
    currentIndex = index;
    const event = index >= 0 ? events[index] : null;
    const visual = event?.visual ?? null;

    if (visual) {
      setScene(session.visual_scenes[visual.scene]);
      statePanel.dataset.tone = visual.tone || "normal";
      stateTitle.textContent = visual.title || "FIXTURE EVENT";
      stateDetail.textContent = [visual.detail, visual.service].filter(Boolean).join(" · ") || event.summary;
      document.getElementById("scene-caption").textContent = event.summary;
      alarm.classList.toggle("is-visible", Boolean(visual.alarm));
      phase.textContent = visual.title || "Fixture event";
    } else {
      setScene(session.visual_scenes?.[session.scene.id] || session.scene);
      statePanel.dataset.tone = "normal";
      stateTitle.textContent = "FIXTURE READY";
      stateDetail.textContent = "Waiting for walkthrough";
      document.getElementById("scene-caption").textContent = session.scene.caption;
      alarm.classList.remove("is-visible");
      phase.textContent = "Fixture walkthrough ready";
    }

    document.querySelectorAll(".agent-card").forEach((card) => {
      const id = card.dataset.agentId;
      const active = visual?.active_agents?.includes(id) ?? false;
      const hasAppeared = index >= 0 && events.slice(0, index + 1).some((item) => item.actor.toLowerCase().replaceAll(" ", "-") === id);
      card.classList.toggle("is-active", active);
      card.classList.toggle("has-acted", !active && hasAppeared);
      const badge = card.querySelector(".agent-status");
      badge.textContent = active ? "Active · fixture" : hasAppeared ? "Complete · fixture" : index < 0 ? "Ready · fixture" : "Standby · fixture";
    });

    document.querySelectorAll(".timeline-event").forEach((item, itemIndex) => {
      item.classList.toggle("is-current", itemIndex === index);
      item.classList.toggle("is-past", itemIndex < index);
      if (itemIndex === index) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });

    const completed = index + 1;
    progress.setAttribute("aria-valuenow", String(Math.max(completed, 0)));
    fill.style.width = `${(Math.max(completed, 0) / events.length) * 100}%`;
    if (announcement) message.textContent = announcement;
    else if (event) message.textContent = `Fixture event ${index + 1} of ${events.length} · ${event.actor}: ${event.summary}`;
    else message.textContent = "Fixture ready · Play to step through the sample incident.";
  }

  function advance() {
    if (currentIndex >= events.length - 1) {
      stopPlayback();
      message.textContent = "Fixture playback complete · no live referee verdict is connected.";
      return false;
    }
    renderFrame(currentIndex + 1);
    if (currentIndex === events.length - 1) {
      stopPlayback();
      message.textContent = "Fixture playback complete · no live referee verdict is connected.";
      return false;
    }
    return true;
  }

  playButton.addEventListener("click", () => {
    if (timer !== null) {
      stopPlayback();
      message.textContent = "Fixture playback paused.";
      return;
    }
    if (currentIndex >= events.length - 1) renderFrame(-1, "Fixture reset for replay.");
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    advance();
    if (currentIndex < events.length - 1) timer = window.setInterval(advance, PLAYBACK_INTERVAL_MS);
  });

  document.getElementById("step-forward").addEventListener("click", () => {
    stopPlayback();
    if (currentIndex >= events.length - 1) renderFrame(-1, "Fixture reset for replay.");
    advance();
  });
  document.getElementById("step-back").addEventListener("click", () => {
    stopPlayback();
    renderFrame(Math.max(-1, currentIndex - 1));
  });
  document.getElementById("playback-reset").addEventListener("click", () => {
    stopPlayback();
    renderFrame(-1, "Fixture reset · ready to replay.");
  });

  renderFrame(-1);
}

loadFixture()
  .then(initializePlayback)
  .catch((error) => {
    const message = makeElement("p", "error-message", `Could not load the fixture session: ${error.message} Open this page from a local web server, not as a file:// URL.`);
    message.setAttribute("role", "alert");
    document.querySelector("main").append(message);
  });
