"use strict";

const form = document.getElementById("ask-form");
const problemEl = document.getElementById("problem");
const submitBtn = document.getElementById("submit");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const modeBadge = document.getElementById("mode-badge");

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function anchorId(docId) {
  return "src-" + docId.replace(/[^A-Za-z0-9]/g, "-");
}

function sourceCard(doc) {
  const meta = el("div", { class: "meta" }, el("strong", {}, doc.reference));
  if (doc.kind === "quran") {
    meta.append(el("span", {}, doc.source));
    if (doc.url) meta.append(el("a", { href: doc.url, target: "_blank", rel: "noopener" }, "Read in context"));
  } else {
    meta.append(el("span", { class: "badge grade" }, doc.grade));
    meta.append(el("span", {}, doc.source));
  }
  return el(
    "article",
    { class: `card ${doc.kind}${doc.cited ? " cited" : ""}`, id: anchorId(doc.id) },
    doc.text_ar ? el("p", { class: "arabic", lang: "ar", dir: "rtl" }, doc.text_ar) : null,
    el("p", { class: "translation" }, doc.text_en),
    meta,
  );
}

function render(data) {
  resultsEl.replaceChildren();

  if (data.crisis) {
    resultsEl.append(
      el("div", { class: "banner danger", role: "alert" },
        el("h2", {}, "You don't have to carry this alone"),
        el("ul", {}, data.crisis_resources.map((r) => el("li", {}, r)))),
    );
  }
  if (data.needs_scholar && data.scholar_note) {
    resultsEl.append(el("div", { class: "banner info" }, el("p", {}, data.scholar_note)));
  }
  if (data.themes.length) {
    resultsEl.append(el("p", { class: "themes" }, "Themes: " + data.themes.join(" · ")));
  }

  const g = data.guidance;
  if (g) {
    const refs = Object.fromEntries([...data.verses, ...data.hadith].map((d) => [d.id, d.reference]));
    const box = el("div", { class: "guidance" }, el("p", {}, g.summary));
    for (const p of g.points) {
      box.append(
        el("div", { class: "point" },
          el("h3", {}, p.heading),
          el("p", {}, p.explanation),
          el("div", { class: "cite-list" },
            p.citations.map((c) => el("a", { href: "#" + anchorId(c) }, refs[c] || c)))),
      );
    }
    if (g.practical_steps.length) {
      box.append(el("h3", { style: "margin-top:16px" }, "Practical steps"),
        el("ul", { class: "steps" }, g.practical_steps.map((s) => el("li", {}, s))));
    }
    resultsEl.append(el("h2", { class: "section-title" }, "Guidance"), box);
  } else if (data.verses.length || data.hadith.length) {
    resultsEl.append(el("p", { class: "notice" },
      "Showing keyword matches. Not every text may apply to your situation, so read each one in its context."));
  }

  for (const n of data.notices) resultsEl.append(el("p", { class: "notice" }, n));

  if (data.verses.length) {
    resultsEl.append(el("h2", { class: "section-title" }, "From the Qur'an"), ...data.verses.map(sourceCard));
  }
  if (data.hadith.length) {
    resultsEl.append(el("h2", { class: "section-title" }, "From the Sunnah"), ...data.hadith.map(sourceCard));
  }
  resultsEl.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const problem = problemEl.value.trim();
  if (problem.length < 3) return;
  submitBtn.disabled = true;
  statusEl.textContent = "Searching the Qur'an and Sunnah…";
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem }),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    render(await res.json());
    statusEl.textContent = "";
  } catch (err) {
    statusEl.textContent = "Something went wrong. Please try again.";
    console.error(err);
  } finally {
    submitBtn.disabled = false;
  }
});

fetch("/api/health")
  .then((r) => r.json())
  .then((h) => {
    modeBadge.textContent = h.guided_mode ? "Guided mode" : "Search-only mode";
    const s = h.sources || {};
    const parts = [s.quran_translation && `Qur'an translation: ${s.quran_translation}.`, s.hadith && `Hadith: ${s.hadith}.`];
    document.getElementById("sources-note").textContent = parts.filter(Boolean).join(" ");
  })
  .catch(() => {});
