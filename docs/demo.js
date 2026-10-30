const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const CIRC = 2 * Math.PI * 52;
const ringFg = $("#ringFg");
if (ringFg) ringFg.style.strokeDasharray = CIRC;

const state = {
  key: false,
  prompt: false,
  framework: false,
  pdfs: [],
  running: false,
  done: 0,
};

const SAMPLES = [
  "Begen & Turner-Cobb, 2015.pdf",
  "Blanke et al., 1990.pdf",
  "Buchko, 1995.pdf",
];

function toast(msg) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function setRing(pct) {
  const p = Math.min(100, Math.max(0, pct));
  if (ringFg) ringFg.style.strokeDashoffset = CIRC - (CIRC * p) / 100;
  $("#ringPct").textContent = `${Math.round(p)}%`;
}

function setCheck(id, ok, text) {
  const el = $(id);
  el.textContent = `${ok ? "✓" : "○"} ${text}`;
  el.classList.toggle("done", ok);
}

function updateUI() {
  const total = state.pdfs.length || 3;
  const coded = state.done;
  setRing(total ? (coded / total) * 100 : 0);
  $("#statDone").textContent = coded;
  $("#statWait").textContent = Math.max(0, total - coded);

  const ready = state.key && state.prompt && state.pdfs.length > 0;
  $("#demoStart").disabled = !ready || state.running;

  if (state.running) {
    $("#demoStatus").textContent = "Simulating coding…";
  } else if (ready) {
    $("#demoStatus").textContent = "Ready. Click Start or try Step 5 simulation";
  } else {
    $("#demoStatus").textContent = "Complete steps 1, 2, and 4 first. Step 3 is optional";
  }

  if (state.done >= total && total > 0) {
    $("#demoCsv").classList.remove("disabled");
    $("#demoCsv").classList.add("btn-primary");
    setCheck("#check5", true, "CSV ready (demo)");
    $("#demoBanner").hidden = false;
  }
}

function showStep(n) {
  $$(".step-tab").forEach((t) => t.classList.toggle("active", t.dataset.step === String(n)));
  $$(".step-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === String(n)));
}

$$(".step-tab").forEach((tab) => {
  tab.addEventListener("click", () => showStep(Number(tab.dataset.step)));
});

$("#demoSaveKey")?.addEventListener("click", () => {
  const v = $("#demoKey").value.trim();
  if (v.length < 10) {
    toast("Enter at least 10 characters (demo only)");
    return;
  }
  state.key = true;
  setCheck("#check1", true, "API key saved (demo)");
  toast("API key saved. In the real app this stays in memory only");
  updateUI();
  showStep(2);
});

$("#demoPrompt")?.addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  state.prompt = true;
  $("#demoPromptName").textContent = `✓ ${f.name}`;
  setCheck("#check2", true, "Prompt uploaded");
  toast("Prompt uploaded");
  updateUI();
  showStep(3);
  e.target.value = "";
});

$("#demoFramework")?.addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  state.framework = true;
  $("#demoFrameworkName").textContent = `✓ ${f.name}`;
  setCheck("#check3", true, "Framework attached (optional)");
  toast("Framework PDF attached. Claude would read this first");
  updateUI();
  showStep(4);
  e.target.value = "";
});

$("#demoSkipFramework")?.addEventListener("click", () => {
  state.framework = false;
  $("#demoFrameworkName").textContent = "No framework attached. Coding prompt only";
  setCheck("#check3", true, "Skipped. Prompt only");
  toast("Skipped framework PDF");
  updateUI();
  showStep(4);
});

function renderPapers() {
  const ul = $("#demoPaperList");
  if (!state.pdfs.length) {
    ul.innerHTML = '<li class="muted">No papers yet</li>';
    return;
  }
  ul.innerHTML = state.pdfs.map((n) => `<li>📄 ${n}</li>`).join("");
}

function addPdfs(names) {
  for (const n of names) {
    if (state.pdfs.length >= 400) break;
    if (!state.pdfs.includes(n)) state.pdfs.push(n);
  }
  setCheck("#check4", state.pdfs.length > 0, `${state.pdfs.length} PDF(s) ready`);
  renderPapers();
  updateUI();
}

$("#demoPdfs")?.addEventListener("change", (e) => {
  const names = [...e.target.files].map((f) => f.name).filter((n) => n.toLowerCase().endsWith(".pdf"));
  if (!names.length) {
    toast("Choose PDF files only");
    return;
  }
  addPdfs(names);
  toast(`Added ${names.length} PDF(s)`);
  e.target.value = "";
});

const drop = $("#demoDrop");
drop?.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.classList.add("dragover");
});
drop?.addEventListener("dragleave", () => drop.classList.remove("dragover"));
drop?.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("dragover");
  const names = [...e.dataTransfer.files]
    .filter((f) => f.name.toLowerCase().endsWith(".pdf"))
    .map((f) => f.name);
  addPdfs(names);
  toast(`Added ${names.length} PDF(s)`);
});

$("#demoAddSamples")?.addEventListener("click", () => {
  addPdfs(SAMPLES);
  toast("Added 3 sample papers");
});

async function simulateRun() {
  if (!state.key || !state.prompt || !state.pdfs.length) {
    toast("Complete steps 1, 2, and 4 first. Step 3 is optional");
    return;
  }
  state.running = true;
  state.done = 0;
  $("#demoStart").disabled = true;
  $("#demoRun").disabled = true;
  const ul = $("#demoResults");
  ul.innerHTML = "";
  const papers = state.pdfs.slice(0, 5);

  for (let i = 0; i < papers.length; i++) {
    $("#demoStatus").textContent = `Coding: ${papers[i]}…`;
    await new Promise((r) => setTimeout(r, 600));
    state.done = i + 1;
    const eligible = i % 2 === 0;
    ul.innerHTML += `<li>✓ ${papers[i]}: ${eligible ? "Eligible" : "Excluded"} · 85% conf</li>`;
    updateUI();
  }

  state.running = false;
  $("#demoRun").disabled = false;
  $("#demoStatus").textContent = "Done. Download CSV in the real app";
  setCheck("#check5", true, "Simulation complete");
  toast("Demo run complete!");
  updateUI();
  showStep(5);
}

$("#demoStart")?.addEventListener("click", simulateRun);
$("#demoRun")?.addEventListener("click", simulateRun);

$("#copySetup")?.addEventListener("click", async () => {
  const text = $("#setupCode").textContent;
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch {
    toast("Select and copy the code block manually");
  }
});

updateUI();
