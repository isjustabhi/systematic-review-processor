const $ = (sel) => document.querySelector(sel);

const ringFg = $("#ringFg");
const CIRC = 2 * Math.PI * 52;
if (ringFg) ringFg.style.strokeDasharray = CIRC;

let state = null;
let papersFingerprint = "";
let pollTimer = null;
let modelsReady = false;

function toast(msg, type = "info", ms = 5000) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function setChip(id, text) {
  const el = $(id);
  if (!el) return;
  if (text) {
    el.textContent = text;
    el.classList.remove("hidden");
  } else {
    el.textContent = "";
    el.classList.add("hidden");
  }
}

function setRunBanner(text, kind = "") {
  const el = $("#runBanner");
  if (!el) return;
  if (!text) {
    el.className = "run-banner hidden";
    el.textContent = "";
    return;
  }
  el.className = `run-banner ${kind}`.trim();
  el.textContent = text;
}

function formatApiError(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return "Request failed";
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatApiError(err.detail) || res.statusText);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

function setProgress(pct) {
  if (!ringFg) return;
  const p = Math.min(100, Math.max(0, pct));
  ringFg.style.strokeDashoffset = CIRC - (CIRC * p) / 100;
  $("#ringPct").textContent = `${Math.round(p)}%`;
}

function setCheck(id, ok) {
  const el = $(id);
  if (el) {
    el.className = ok ? "step-check done" : "step-check";
    el.setAttribute("aria-label", ok ? "Done" : "Not done");
  }
}

function render(data) {
  state = data;
  const counts = data.counts || {};
  const papers = data.papers || [];
  const job = data.job || { state: "idle" };
  const total = data.pdf_count || 0;
  const max = data.max_papers || 400;
  const done =
    (counts.success || 0) + (counts.parse_error || 0) + (counts.failed || 0);

  setProgress(total ? (done / total) * 100 : 0);
  $("#statSuccess").textContent = counts.success || 0;
  $("#statPending").textContent = counts.pending || 0;
  $("#statFailed").textContent = counts.failed || 0;
  $("#paperCount").textContent = `${total} / ${max}`;

  const hasKey = !!data.api_key_set;
  const hasPrompt = !!data.prompt_ready;
  const hasPdfs = total > 0;
  setCheck("#checkApiKey", hasKey);
  setCheck("#checkPrompt", hasPrompt);
  setCheck("#checkFramework", !!data.framework_ready);
  setCheck("#checkPdfs", hasPdfs);

  const jobBusy = job.state === "running" || job.state === "stopping";
  const btnRemovePrompt = $("#btnRemovePrompt");
  const promptBtnLabel = $("#promptBtnLabel");
  if (data.prompt_ready) {
    $("#promptLabel").textContent = data.prompt_name;
    setChip("#promptChip", `Uploaded: ${data.prompt_name}`);
    $("#step2")?.classList.add("step-done");
    if (promptBtnLabel) promptBtnLabel.textContent = "Replace .docx file";
    if (btnRemovePrompt) {
      btnRemovePrompt.classList.remove("hidden");
      btnRemovePrompt.disabled = jobBusy;
    }
  } else {
    $("#promptLabel").textContent = "No file uploaded yet";
    setChip("#promptChip", "");
    $("#step2")?.classList.remove("step-done");
    if (promptBtnLabel) promptBtnLabel.textContent = "Choose .docx file";
    if (btnRemovePrompt) btnRemovePrompt.classList.add("hidden");
  }

  if (hasKey) {
    $("#step1")?.classList.add("step-done");
    const src = data.api_key_source === "env" ? "from your .env file" : "for this session";
    $("#apiKeyHint").textContent = `API key is saved ${src}`;
    setChip("#apiSavedChip", "API key is saved");
  } else {
    $("#step1")?.classList.remove("step-done");
    $("#apiKeyHint").textContent = "Paste once per session, or set in .env";
    setChip("#apiSavedChip", "");
  }

  const btnRemoveFramework = $("#btnRemoveFramework");
  const frameworkBtnLabel = $("#frameworkBtnLabel");
  if (data.framework_ready) {
    $("#frameworkLabel").textContent = data.framework_name;
    setChip("#frameworkChip", `Uploaded: ${data.framework_name}`);
    $("#stepFramework")?.classList.add("step-done");
    if (frameworkBtnLabel) frameworkBtnLabel.textContent = "Replace framework PDF";
    if (btnRemoveFramework) {
      btnRemoveFramework.classList.remove("hidden");
      btnRemoveFramework.disabled = jobBusy;
    }
  } else {
    $("#frameworkLabel").textContent = "No framework attached";
    setChip("#frameworkChip", "");
    $("#stepFramework")?.classList.remove("step-done");
    if (frameworkBtnLabel) frameworkBtnLabel.textContent = "Choose PDF (optional)";
    if (btnRemoveFramework) btnRemoveFramework.classList.add("hidden");
  }

  if (hasPdfs) $("#step3")?.classList.add("step-done");
  else $("#step3")?.classList.remove("step-done");

  const running = job.state === "running" || job.state === "stopping";
  const blockers = [];
  if (!hasKey) blockers.push("API key (Step 1)");
  if (!hasPrompt) blockers.push("coding prompt (Step 2)");
  if (!hasPdfs) blockers.push("PDFs (Step 4)");

  const btnRun = $("#btnRun");
  const blocked = !running && blockers.length > 0;
  btnRun.classList.toggle("hidden", running);
  $("#btnStop").classList.toggle("hidden", !running);
  btnRun.disabled = running;
  btnRun.classList.toggle("btn-blocked", blocked);
  btnRun.dataset.blockers = blockers.join(", ");

  $("#btnCsv").classList.toggle("disabled", !data.csv_ready);
  $("#btnBriefing")?.classList.toggle("disabled", !data.framework_briefing_ready);
  $("#btnChangeLog")?.classList.toggle("disabled", !data.change_log_ready && done === 0);
  $("#btnZip").classList.toggle("disabled", done === 0);
  const btnReset = $("#btnReset");
  if (btnReset) {
    btnReset.disabled = running;
    btnReset.classList.toggle("disabled", running || (total === 0 && done === 0));
  }

  const jobEl = $("#jobStatus");
  const p = job.progress || {};
  if (job.state === "stopping") {
    jobEl.textContent = "Stopping. Finishing the current paper…";
    setRunBanner(
      "Stop requested. This may take a minute while the current paper finishes.",
      "warn"
    );
  } else if (running) {
    jobEl.textContent = `Coding paper ${p.done || 0} of ${p.total || total}…${
      p.current ? ` (${p.current})` : ""
    }`;
    setRunBanner(
      `Coding started. This may take a while, especially with many papers. You can leave this window open. Currently on ${p.done || 0} of ${p.total || total}${p.current ? `: ${p.current}` : ""}.`
    );
  } else if (job.state === "completed") {
    jobEl.textContent = job.message || "Coding finished. Download the CSV when you are ready.";
    setRunBanner("Coding finished. This can take a while on big batches, and yours is done. Download the CSV when you are ready to review.", "ok");
  } else if (job.state === "failed") {
    jobEl.textContent = job.message || "Coding stopped with an error.";
    setRunBanner(job.message || "Coding stopped with an error. Check the change log and try again.", "warn");
  } else if (job.state === "cancelled") {
    jobEl.textContent = job.message || "Coding was stopped.";
    setRunBanner("Coding was stopped. Papers already finished are still saved.", "warn");
  } else if (job.message) {
    jobEl.textContent = job.message;
    setRunBanner("");
  } else if (blocked) {
    jobEl.textContent = `Complete: ${blockers.join(", ")}`;
    setRunBanner("");
  } else {
    jobEl.textContent = "Ready. Click Start coding papers";
    setRunBanner("");
  }

  renderPapers(papers, running);
  syncModelSelect(data, running);
}

function syncModelSelect(data, running) {
  const sel = $("#modelSelect");
  if (!sel) return;
  const models = data.supported_models || [];
  if (models.length && !modelsReady) {
    sel.innerHTML = models
      .map(
        (m) =>
          `<option value="${escapeAttr(m.id)}">${escapeHtml(m.label)}</option>`
      )
      .join("");
    modelsReady = true;
    const initial = data.default_model || models[0].id;
    if (initial) sel.value = initial;
  }
  if (running && data.job && data.job.model) {
    sel.value = data.job.model;
  }
  sel.disabled = !!running;
}

function renderPapers(papers, running) {
  const grid = $("#papersGrid");
  const fp = JSON.stringify(papers);

  if (!papers.length) {
    if (papersFingerprint !== "empty") {
      grid.innerHTML =
        '<p class="empty-state">No papers yet. Drop PDFs above to list them here.</p>';
      papersFingerprint = "empty";
    }
    return;
  }

  if (fp === papersFingerprint) {
    grid.querySelectorAll(".btn-remove").forEach((b) => {
      b.disabled = running;
    });
    return;
  }
  papersFingerprint = fp;

  grid.innerHTML = papers
    .map(
      (p) => `
    <div class="paper-row ${p.status}">
      <div class="paper-row-main">
        <span class="paper-name">${escapeHtml(p.filename)}</span>
        <span class="badge ${p.status}">${p.status.replace("_", " ")}</span>
      </div>
      <div class="paper-row-sub">${escapeHtml(paperDetail(p))}</div>
      <button type="button" class="btn-remove" data-file="${escapeAttr(p.filename)}" ${
        running ? "disabled" : ""
      } title="Remove this paper"><svg class="icon" aria-hidden="true"><use href="#i-trash"></use></svg>Remove</button>
    </div>`
    )
    .join("");

  grid.querySelectorAll(".btn-remove").forEach((btn) => {
    btn.onclick = () => removePdf(btn.dataset.file);
  });
}

function paperDetail(p) {
  if (p.error) return p.error.slice(0, 120);
  const parts = [];
  if (p.eligible === true) parts.push("Eligible");
  if (p.eligible === false) parts.push("Excluded");
  if (p.confidence != null) parts.push(`${(p.confidence * 100).toFixed(0)}% confidence`);
  if (p.needs_human_review) parts.push("Needs human review");
  return parts.join(" · ") || "Not processed yet";
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function escapeAttr(s) {
  return String(s).replace(/"/g, "&quot;");
}

async function refresh() {
  render(await api("/api/status"));
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      await refresh();
      const st = state?.job?.state;
      if (!st || ["idle", "completed", "cancelled", "failed"].includes(st)) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    } catch (_) {}
  }, 2000);
}

async function uploadPdfs(files) {
  const pdfs = [...files].filter((f) => f.name.toLowerCase().endsWith(".pdf"));
  if (!pdfs.length) {
    toast("Please choose PDF files only", "error");
    return;
  }
  toast(`Uploading ${pdfs.length} PDF(s)…`, "info");
  const fd = new FormData();
  for (const f of pdfs) fd.append("files", f);
  try {
    const res = await api("/api/pdfs", { method: "POST", body: fd });
    if (!res.added) {
      toast("No new PDFs added (maybe wrong file type or 400 limit reached)", "error");
      return;
    }
    toast(`Uploaded ${res.added} file(s). Total: ${res.total} papers.`, "success");
    papersFingerprint = "";
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function uploadPrompt(file) {
  toast(`Uploading ${file.name}…`, "info");
  const fd = new FormData();
  fd.append("file", file);
  try {
    await api("/api/prompt", { method: "POST", body: fd });
    toast(`Uploaded: ${file.name}`, "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function uploadFramework(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    toast("Framework file must be a PDF", "error");
    return;
  }
  toast(`Uploading ${file.name}…`, "info");
  const fd = new FormData();
  fd.append("file", file);
  try {
    await api("/api/framework", { method: "POST", body: fd });
    toast(`Uploaded: ${file.name}. Claude will read this first`, "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function removePdf(filename) {
  if (!confirm(`Remove "${filename}" from the list?`)) return;
  papersFingerprint = "";
  try {
    await api(`/api/pdfs/${encodeURIComponent(filename)}`, { method: "DELETE" });
    toast("Paper removed", "info");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
}

$("#pdfInput")?.addEventListener("change", (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  uploadPdfs(files);
});

$("#promptInput")?.addEventListener("change", (e) => {
  if (e.target.files[0]) uploadPrompt(e.target.files[0]);
  e.target.value = "";
});

$("#frameworkInput")?.addEventListener("change", (e) => {
  if (e.target.files[0]) uploadFramework(e.target.files[0]);
  e.target.value = "";
});

$("#btnRemoveFramework")?.addEventListener("click", async () => {
  const name = state?.framework_name || "framework PDF";
  if (!confirm(`Remove ${name}? Coding will use the prompt only.`)) return;
  try {
    await api("/api/framework", { method: "DELETE" });
    toast(`Removed ${name}. You can upload another PDF if you want.`, "info");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

$("#btnRemovePrompt")?.addEventListener("click", async () => {
  const name = state?.prompt_name || "coding instructions";
  if (!confirm(`Remove ${name}?`)) return;
  try {
    await api("/api/prompt", { method: "DELETE" });
    toast(`Removed ${name}. Upload another .docx when you are ready.`, "info");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

const dropzone = $("#dropzone");
if (dropzone) {
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    uploadPdfs([...e.dataTransfer.files]);
  });
}

$("#btnSaveApiKey")?.addEventListener("click", async () => {
  const key = $("#apiKeyInput").value.trim();
  if (!key) {
    toast("Paste your API key first", "error");
    return;
  }
  try {
    await api("/api/api-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    $("#apiKeyInput").value = "";
    toast("API key is saved for this session", "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

$("#btnClearApiKey")?.addEventListener("click", async () => {
  try {
    await api("/api/api-key", { method: "DELETE" });
    toast("Pasted key cleared", "info");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

$("#btnRun")?.addEventListener("click", async () => {
  const btn = $("#btnRun");
  if (btn.classList.contains("btn-blocked")) {
    toast(`Complete first: ${btn.dataset.blockers}`, "error");
    return;
  }
  if (btn.disabled) return;
  try {
    await api("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workers: 1,
        model: $("#modelSelect")?.value || undefined,
      }),
    });
    toast(
      "Coding started. This may take a while, especially with many papers. You can leave this window open.",
      "success",
      10000
    );
    await refresh();
    startPolling();
  } catch (e) {
    toast(e.message, "error");
  }
});

$("#btnStop")?.addEventListener("click", async () => {
  try {
    await api("/api/stop", { method: "POST" });
    toast("Stop requested", "info");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

[
  ["#btnCsv", "/api/download/csv"],
  ["#btnBriefing", "/api/download/framework-briefing"],
  ["#btnChangeLog", "/api/download/change-log"],
  ["#btnZip", "/api/download/zip"],
].forEach(([sel, base]) => {
  $(sel)?.addEventListener("click", (e) => {
    if (e.currentTarget.classList.contains("disabled")) {
      e.preventDefault();
      return;
    }
    e.currentTarget.href = `${base}?t=${Date.now()}`;
  });
});

$("#btnReset")?.addEventListener("click", async () => {
  if ($("#btnReset").disabled) return;
  if (
    !confirm(
      "Clear ALL uploaded papers and ALL results to start a new run?\n\nThis removes every PDF and its coded output. Your API key and coding prompt are kept."
    )
  )
    return;
  try {
    const res = await api("/api/reset", { method: "POST" });
    papersFingerprint = "";
    toast(`Cleared ${res.removed_pdfs || 0} paper(s) and all results`, "success");
    await refresh();
  } catch (e) {
    toast(e.message, "error");
  }
});

refresh().catch(() =>
  toast("Cannot connect. Open a terminal and run: python3 run_server.py", "error")
);

function resetPapersSplit() {
  const setup = $(".setup-stack");
  if (!setup) return;
  setup.dataset.userSized = "0";
  setup.style.maxHeight = "";
}

function bindPapersSplit() {
  const handle = $("#splitHandle");
  const setup = $(".setup-stack");
  if (!handle || !setup) return;

  handle.addEventListener("mousedown", (e) => {
    if (window.innerWidth <= 800) return;
    e.preventDefault();
    const startY = e.clientY;
    const startH = setup.getBoundingClientRect().height;
    handle.classList.add("is-dragging");

    const onMove = (ev) => {
      const next = Math.min(
        window.innerHeight - 180,
        Math.max(64, startH + (ev.clientY - startY))
      );
      setup.style.maxHeight = `${next}px`;
      setup.dataset.userSized = "1";
    };
    const onUp = () => {
      handle.classList.remove("is-dragging");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  });

  handle.addEventListener("dblclick", () => {
    resetPapersSplit();
  });
}

bindPapersSplit();
window.addEventListener("resize", () => {
  if (window.innerWidth <= 800) resetPapersSplit();
});
