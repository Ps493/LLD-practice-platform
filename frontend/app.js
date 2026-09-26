const API = "/api";
const app = document.getElementById("app");

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function difficultyBadge(d) {
  return `<span class="badge ${d.toLowerCase()}">${d}</span>`;
}

function statusPill(status) {
  const label = status.replace(/_/g, " ");
  return `<span class="status-pill status-${status}">${label}</span>`;
}

// ---------------- Router ----------------

const routes = {
  "": renderProblemList,
  "problem": renderProblemDetail,
  "attempt": renderAttempt,
};

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [page, id] = hash.split("/");
  const fn = routes[page] || renderProblemList;
  fn(id);
}

function go(hash) {
  location.hash = hash;
}

// ---------------- Views ----------------

async function renderProblemList() {
  app.innerHTML = `<h1>Choose a problem</h1><p class="muted">Practice loop: choose → design → submit → feedback → review → try again.</p><div id="list"></div>`;
  const list = document.getElementById("list");
  try {
    const problems = await api("/problems");
    list.innerHTML = "";
    problems.forEach((p) => {
      const card = el(`
        <div class="card clickable">
          <div class="row between">
            <h2 style="margin:0">${p.title}</h2>
            ${difficultyBadge(p.difficulty)}
          </div>
          <p class="summary">${p.summary}</p>
        </div>
      `);
      card.addEventListener("click", () => go(`problem/${p.id}`));
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = `<div class="error-box">Could not load problems: ${e.message}</div>`;
  }
}

async function renderProblemDetail(problemId) {
  app.innerHTML = `<div class="crumb" id="back">&larr; All problems</div><div id="content">Loading…</div>`;
  document.getElementById("back").addEventListener("click", () => go(""));
  const content = document.getElementById("content");
  try {
    const [p, history] = await Promise.all([
      api(`/problems/${problemId}`),
      api(`/problems/${problemId}/attempts`),
    ]);

    content.innerHTML = `
      <div class="card">
        <div class="row between">
          <h1 style="margin:0">${p.title}</h1>
          ${difficultyBadge(p.difficulty)}
        </div>
        <p class="summary">${p.summary}</p>
        <ul class="reqs">${p.requirements.map((r) => `<li>${r}</li>`).join("")}</ul>
        <div style="margin-top:16px">
          <button class="btn" id="start">Start new attempt</button>
        </div>
      </div>
      <div class="card">
        <h2>Attempt history</h2>
        <div id="history">${
          history.length
            ? history.map((h) => `
              <div class="history-row">
                <span>${new Date(h.created_at).toLocaleString()}</span>
                <span>${statusPill(h.status)}</span>
                <span>${h.score !== null && h.score !== undefined ? `<b>${h.score}</b>/100` : "—"}</span>
                <button class="link-btn" data-id="${h.id}">Review →</button>
              </div>`).join("")
            : `<p class="muted">No attempts yet — this will fill in as you practice.</p>`
        }</div>
      </div>
    `;

    document.getElementById("start").addEventListener("click", async () => {
      const a = await api("/attempts", { method: "POST", body: JSON.stringify({ problem_id: problemId }) });
      go(`attempt/${a.id}`);
    });
    content.querySelectorAll(".link-btn[data-id]").forEach((btn) => {
      btn.addEventListener("click", () => go(`attempt/${btn.dataset.id}`));
    });
  } catch (e) {
    content.innerHTML = `<div class="error-box">${e.message}</div>`;
  }
}

async function renderAttempt(attemptId) {
  app.innerHTML = `<div class="crumb" id="back">&larr; Back</div><div id="content">Loading…</div>`;
  const content = document.getElementById("content");

  try {
    const a = await api(`/attempts/${attemptId}`);
    document.getElementById("back").addEventListener("click", () => go(`problem/${a.problem_id}`));
    const problem = await api(`/problems/${a.problem_id}`);

    if (a.result) {
      renderFeedback(content, a, problem);
      return;
    }

    // draft / not-yet-evaluated: show the design form
    content.innerHTML = `
      <div class="card">
        <div class="row between">
          <h1 style="margin:0">${problem.title}</h1>
          ${statusPill(a.status)}
        </div>
        <ul class="reqs">${problem.requirements.map((r) => `<li>${r}</li>`).join("")}</ul>
      </div>
      <div class="card">
        <div class="row between" style="margin-bottom:10px">
          <h2 style="margin:0">Your design</h2>
          <select id="format">
            <option value="text_design" ${a.submission?.format === "text_design" ? "selected" : ""}>Text design (classes, responsibilities, relationships)</option>
            <option value="code" ${a.submission?.format === "code" ? "selected" : ""}>Code (class/interface skeletons)</option>
          </select>
        </div>
        <textarea id="design-input" placeholder="Describe your classes, their responsibilities, relationships, and how you'd handle edge cases...">${a.submission?.content || ""}</textarea>
        <div class="row" style="margin-top:12px; justify-content:flex-end">
          <button class="btn" id="submit">Submit for feedback</button>
        </div>
        <div id="err"></div>
      </div>
    `;

    document.getElementById("submit").addEventListener("click", async () => {
      const submitBtn = document.getElementById("submit");
      const errBox = document.getElementById("err");
      const text = document.getElementById("design-input").value.trim();
      const format = document.getElementById("format").value;
      if (!text) {
        errBox.innerHTML = `<div class="error-box">Write something before submitting.</div>`;
        return;
      }
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="spinner"></span>Evaluating…`;
      errBox.innerHTML = "";
      try {
        const res = await api(`/attempts/${attemptId}/submit`, {
          method: "POST",
          body: JSON.stringify({ content: text, format }),
        });
        renderFeedback(content, { ...a, status: res.attempt.status, result: res.result }, problem);
      } catch (e) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit for feedback";
        errBox.innerHTML = `<div class="error-box">Evaluation failed: ${e.message}. Your submission was saved — try again.</div>`;
      }
    });
  } catch (e) {
    content.innerHTML = `<div class="error-box">${e.message}</div>`;
  }
}

function scoreColor(score) {
  if (score === null || score === undefined) return "var(--muted)";
  if (score >= 75) return "var(--good)";
  if (score >= 50) return "var(--warn)";
  return "var(--bad)";
}

function renderFeedback(content, a, problem) {
  const r = a.result;
  const retryable = a.status === "evaluation_failed";
  content.innerHTML = `
    <div class="card">
      <div class="row between">
        <h1 style="margin:0">${problem.title}</h1>
        ${statusPill(a.status)}
      </div>
    </div>
    <div class="card">
      <div class="row between">
        <h2 style="margin:0">Feedback</h2>
        <div class="score-ring" style="color:${scoreColor(r?.score)}">${r?.score ?? "—"}<span style="font-size:16px;color:var(--muted)">/100</span></div>
      </div>
      ${r ? `
        <div class="feedback-section strengths">
          <h3>Strengths</h3>
          <ul>${(r.strengths.length ? r.strengths : ["—"]).map((s) => `<li>${s}</li>`).join("")}</ul>
        </div>
        <div class="feedback-section issues">
          <h3>Issues</h3>
          <ul>${(r.issues.length ? r.issues : ["—"]).map((s) => `<li>${s}</li>`).join("")}</ul>
        </div>
        <div class="feedback-section suggestions">
          <h3>Suggestions</h3>
          <ul>${(r.suggestions.length ? r.suggestions : ["—"]).map((s) => `<li>${s}</li>`).join("")}</ul>
        </div>
        <div class="note-box">${r.notes} (source: ${r.source})</div>
      ` : `<p class="muted">Evaluation did not complete.</p>`}
      <div class="row" style="margin-top:16px; justify-content:flex-end; gap:10px">
        ${retryable ? `<button class="btn secondary" id="retry">Retry evaluation</button>` : ""}
        <button class="btn secondary" id="again">Try again</button>
        <button class="btn" id="allattempts">View history</button>
      </div>
    </div>
  `;
  if (retryable) {
    document.getElementById("retry").addEventListener("click", async () => {
      try {
        const res = await api(`/attempts/${a.id}/retry`, { method: "POST" });
        renderFeedback(content, { ...a, status: res.attempt.status, result: res.result }, problem);
      } catch (e) {
        alert("Retry failed: " + e.message);
      }
    });
  }
  document.getElementById("again").addEventListener("click", async () => {
    const na = await api("/attempts", { method: "POST", body: JSON.stringify({ problem_id: problem.id }) });
    go(`attempt/${na.id}`);
  });
  document.getElementById("allattempts").addEventListener("click", () => go(`problem/${problem.id}`));
}
