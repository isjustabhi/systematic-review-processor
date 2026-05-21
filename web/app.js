const $ = (sel) => document.querySelector(sel);

const ringFg = $("#ringFg");
const ringPct = $("#ringPct");
const CIRC = 2 * Math.PI * 52;
ringFg.style.strokeDasharray = CIRC;

let eventSource = null;
let state = null;
let papersFingerprint = "";
let pollTimer = null;

function toast(msg, type = "info") {
  const stack = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

function setProgress(pct) {
  const p = Math.min(100, Math.max(0, pct));
  ringFg.style.strokeDashoffset = CIRC - (CIRC * p) / 100;
  ringPct.textContent = `${Math.round(p)}%`;
}

function render(data) {
  state = data;
  const counts = data.counts || {};
  const papers = data.papers || [];
  const job = data.job || { state: "idle" };

  const done =
    (counts.success || 0) +
    (counts.parse_error || 0) +
    (counts.failed || 0);
  const total = data.pdf_count || 0;
  setProgress(total ? (done / total) * 100 : 0);

  $("#statSuccess").textContent = counts.success || 0;
  $("#statPending").textContent = counts.pending || 0;
  $("#statFailed").textContent = counts.failed || 0;
  $("#statReview").textContent = counts.parse_error || 0;
  $("#paperCount").textContent = `${total} / ${data.max_papers || 20}`;

  const promptBar = $("#promptBar");
  const promptLabel = $("#promptLabel");
  if (data.prompt_ready) {
    promptBar.classList.add("ready");
    promptLabel.textContent = `Prompt: ${data.prompt_name}`;
  } else {
    promptBar.classList.remove("ready");
    promptLabel.textContent = "No coding prompt uploaded";
  }

  const running = job.state === "running" || job.state === "stopping";
  $("#btnRun").classList.toggle("hidden", running);
  $("#btnStop").classList.toggle("hidden", !running);
  $("#btnRun").disabled =
    running || !data.prompt_ready || total === 0;
  $("#btnStop").disabled = job.state === "stopping";

  const csvReady = data.csv_ready;
  $("#btnCsv").classList.toggle("disabled", !csvReady);
  $("#btnZip").classList.toggle("disabled", done === 0);

  const jobEl = $("#jobStatus");
  if (job.state === "stopping") {
    jobEl.className = "job-status running";
    jobEl.textContent = "Stopping — finishing current API call…";
  } else if (job.state === "running") {
    const prog = job.progress || {};
    jobEl.className = "job-status running";
    jobEl.textContent = `Processing ${prog.done || 0}/${prog.total || total}${
      prog.current ? ` — ${prog.current}` : ""
    }`;
  } else if (job.state === "cancelled") {
    jobEl.className = "job-status";
    jobEl.textContent = "Stopped";
  } else if (job.message) {
    jobEl.className = "job-status";
    jobEl.textContent = job.message;
  } else {
    jobEl.className = "job-status";
    jobEl.textContent = "";
  }

  renderPapers(papers, running);
}

function paperDetailText(p) {
  const eligible =
    p.eligible === true
      ? "Eligible"
      : p.eligible === false
        ? "Excluded"
        : "—";
  const conf =
    p.confidence != null ? `${(p.confidence * 100).toFixed(0)}% conf.` : "";
  if (p.error) {
    return p.error.slice(0, 120) + (p.error.length > 120 ? "…" : "");
  }
  return [eligible, conf].filter(Boolean).join(" · ");
}

function paperCardHtml(p, running) {
  const detail = paperDetailText(p);
  return `
    <article class="paper-card ${p.status}" data-file="${escapeAttr(p.filename)}">
      <div class="paper-title">${escapeHtml(p.filename)}</div>
      <div class="paper-meta">
        <span class="badge ${p.status}">${p.status.replace("_", " ")}</span>
      </div>
      <div class="paper-detail">${escapeHtml(detail)}</div>
      <div class="paper-actions">
        <button type="button" class="btn-remove" data-file="${escapeAttr(p.filename)}" ${
          running ? "disabled" : ""
        }>Remove</button>
      </div>
    </article>`;
}

function bindRemoveButtons(grid) {
  grid.querySelectorAll(".btn-remove").forEach((btn) => {
    btn.onclick = () => removePdf(btn.dataset.file);
  });
}

function renderPapers(papers, running) {
  const grid = $("#papersGrid");
  const fp = JSON.stringify(papers);

  if (!papers.length) {
    if (papersFingerprint !== "empty") {
      grid.innerHTML =
        '<p class="empty-state">No papers yet. Upload PDFs to begin.</p>';
      papersFingerprint = "empty";
    }
    return;
  }

  if (fp === papersFingerprint) {
    grid.querySelectorAll(".btn-remove").forEach((btn) => {
      btn.disabled = running;
    });
    return;
  }

  const prev = papersFingerprint;
  papersFingerprint = fp;

  if (!prev || prev === "empty") {
    grid.innerHTML = papers.map((p) => paperCardHtml(p, running)).join("");
    bindRemoveButtons(grid);
    return;
  }

  const existing = new Map();
  grid.querySelectorAll(".paper-card[data-file]").forEach((el) => {
    existing.set(el.dataset.file, el);
  });

  const next = document.createDocumentFragment();
  papers.forEach((p) => {
    const key = p.filename;
    let card = existing.get(key);
    if (card) {
      card.className = `paper-card ${p.status}`;
      card.querySelector(".badge").className = `badge ${p.status}`;
      card.querySelector(".badge").textContent = p.status.replace("_", " ");
      card.querySelector(".paper-detail").textContent = paperDetailText(p);
      card.querySelector(".btn-remove").disabled = running;
      existing.delete(key);
      next.appendChild(card);
    } else {
      const wrap = document.createElement("div");
      wrap.innerHTML = paperCardHtml(p, running);
      next.appendChild(wrap.firstElementChild);
    }
  });

  grid.replaceChildren(next);
  bindRemoveButtons(grid);
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function escapeAttr(s) {
  return s.replace(/"/g, "&quot;");
}

async function refresh() {
  const data = await api("/api/status");
  render(data);
  return data;
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const data = await api("/api/status");
      render(data);
      const st = data.job?.state;
      if (!st || st === "idle" || st === "completed" || st === "cancelled" || st === "failed") {
        stopPolling();
      }
    } catch (_) {}
  }, 2500);
}

async function uploadPdfs(files) {
  if (!files.length) return;
  papersFingerprint = "";
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  try {
    const res = await api("/api/pdfs", { method: "POST", body: fd });
    toast(`Added ${res.added} PDF(s) — ${res.total} total`, "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function uploadPrompt(file) {
  const fd = new FormData();
  fd.append("file", file);
  try {
    await api("/api/prompt", { method: "POST", body: fd });
    toast("Prompt uploaded", "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function removePdf(filename) {
  if (!confirm(`Remove ${filename} and its results?`)) return;
  papersFingerprint = "";
  try {
    await api(`/api/pdfs/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

$("#pdfInput").onchange = (e) => uploadPdfs([...e.target.files]);
$("#promptInput").onchange = (e) => {
  if (e.target.files[0]) uploadPrompt(e.target.files[0]);
};

const dropzone = $("#dropzone");
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () =>
  dropzone.classList.remove("dragover")
);
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadPdfs([...e.dataTransfer.files].filter((f) =>
    f.name.toLowerCase().endsWith(".pdf")
  ));
});

$("#btnRun").onclick = async () => {
  try {
    await api("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workers: 1 }),
    });
    toast("Processing started", "success");
    await refresh();
    startPolling();
  } catch (e) {
    toast(e.message, "error");
  }
};

$("#btnStop").onclick = async () => {
  try {
    $("#btnStop").disabled = true;
    await api("/api/stop", { method: "POST" });
    toast("Stop requested — halting after current step", "info");
    render(await api("/api/status"));
    stopPolling();
  } catch (e) {
    toast(e.message, "error");
    $("#btnStop").disabled = false;
  }
};

$("#btnClear").onclick = async () => {
  if (!confirm("Clear all JSON and CSV outputs? (PDFs stay)")) return;
  papersFingerprint = "";
  try {
    await api("/api/clear-outputs", { method: "POST" });
    toast("Outputs cleared", "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
};

async function init() {
  const health = await api("/api/health");
  const badge = $("#apiBadge");
  const text = $("#apiBadgeText");
  if (health.api_key_set) {
    badge.className = "api-badge ok";
    text.textContent = "API key connected";
  } else {
    badge.className = "api-badge bad";
    text.textContent = "Set ANTHROPIC_API_KEY in .env";
  }
  await refresh();
}

init().catch((e) => toast(e.message, "error"));
