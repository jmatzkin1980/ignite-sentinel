const model = JSON.parse(document.getElementById("readiness-data").textContent);
    const $ = (id) => document.getElementById(id);
    const es = model.language === "es";
    const T = es ? {
      eyebrow: "Vista derivada de solo lectura", items: "Ítems", recipients: "Pedidos por destinatario", marks: "Marcas locales",
      marksHint: "Marcá un pedido cuando lo enviaste o lo respondieron. Las marcas viven solo en este navegador: exportalas para pasarlas a otro.",
      blockers: "Qué lo bloquea", warnings: "Advertencias", partial: "Chequeos que no pudieron correr", next: "Próximo paso",
      copy: "Copiar pedido", copied: "Copiado", none: "Sin pedidos abiertos.", unassigned: "sin dueño registrado",
      degraded: "un pedido abierto lo degrada", empty: "sin historias: nunca se pinta verde", stories: "Historias",
      open: "abiertos", requestsLabel: "pedidos", exported: "Marcas exportadas en el cuadro.", imported: "Marcas importadas.",
      cleared: "Marcas borradas.", badImport: "El JSON no es un export de esta vista para este proyecto.", storage: "Este navegador no guarda marcas; se pierden al cerrar.",
      blocks: { start: "bloquea arranque", slice: "bloquea slice", no: "no bloquea" },
      verdict: { READY: "Listo", READY_WITH_WARNINGS: "Listo con advertencias", NOT_READY: "No listo" },
      greeting: (r) => "Hola " + r + ", para avanzar necesitamos:", stat: { items: "ítems", requests: "pedidos", recipients: "destinatarios", blocks_start: "bloquean arranque", blocks_slice: "bloquean slice" }
    } : {
      eyebrow: "Read-only derived view", items: "Items", recipients: "Requests by recipient", marks: "Local marks",
      marksHint: "Mark a request once it was sent or answered. Marks live only in this browser: export them to move them.",
      blockers: "What blocks it", warnings: "Warnings", partial: "Checks that could not run", next: "Next step",
      copy: "Copy request", copied: "Copied", none: "No open requests.", unassigned: "no registered owner",
      degraded: "an open request degrades it", empty: "no stories: never shown green", stories: "Stories",
      open: "open", requestsLabel: "requests", exported: "Marks exported to the box.", imported: "Marks imported.",
      cleared: "Marks cleared.", badImport: "That JSON is not an export of this view for this project.", storage: "This browser does not keep marks; they are lost on close.",
      blocks: { start: "blocks start", slice: "blocks slice", no: "does not block" },
      verdict: { READY: "Ready", READY_WITH_WARNINGS: "Ready with warnings", NOT_READY: "Not ready" },
      greeting: (r) => "Hi " + r + ", to move forward we need:", stat: { items: "items", requests: "requests", recipients: "recipients", blocks_start: "block start", blocks_slice: "block slice" }
    };
    const storageKey = "ignite-sentinel:readiness:" + model.project_id;
    let storageOk = true;
    let marks = loadMarks();
    const requestsById = Object.fromEntries(model.requests.map(r => [r.id, r]));

    function loadMarks() {
      try {
        const raw = window.localStorage.getItem(storageKey);
        const parsed = raw ? JSON.parse(raw) : {};
        return parsed && typeof parsed === "object" ? parsed : {};
      } catch (error) {
        storageOk = false;
        return {};
      }
    }
    function saveMarks() {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(marks));
      } catch (error) {
        storageOk = false;
      }
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch]));
    }
    function badge(verdict) {
      return `<span class="verdict v-${escapeHtml(verdict)}">${escapeHtml(T.verdict[verdict] || verdict)}</span>`;
    }
    function itemRequests(item) {
      const ids = new Set(item.kind === "wave" ? item.stories : [item.id]);
      return model.requests.filter(r => ids.has(r.item));
    }
    // Marks never upgrade a governed verdict: they only lift the degradation an
    // open request puts on a READY item.
    function shownVerdict(item) {
      const open = itemRequests(item).filter(r => !marks[r.id]);
      if (item.verdict === "READY" && open.length) return { verdict: "READY_WITH_WARNINGS", degraded: true, open: open.length };
      return { verdict: item.verdict, degraded: false, open: open.length };
    }
    function list(title, values) {
      return values.length ? `<h3>${escapeHtml(title)}</h3><ul>${values.map(v => `<li>${escapeHtml(v)}</li>`).join("")}</ul>` : "";
    }

    function renderHeader() {
      const v = model.verdict;
      $("eyebrow").textContent = T.eyebrow;
      $("title").textContent = model.project_id + " · " + model.label;
      renderVerdictBadge();
      $("meta").textContent = "maturity score " + Math.round((v.maturity_score || 0) * 100) + "% · cut-off " + model.provenance.cutoff;
      $("next").innerHTML = `<strong>${escapeHtml(T.next)}:</strong> ${escapeHtml(v.next_step.text)} <code>${escapeHtml(v.next_step.command)}</code>`;
      $("why").innerHTML = list(T.blockers, v.blockers) + list(T.warnings, v.warnings) + list(T.partial, v.partial_coverage.map(p => p.check + ": " + p.reason));
      $("itemsTitle").textContent = T.items;
      $("navItemsTitle").textContent = T.items;
      $("recipientsTitle").textContent = T.recipients;
      $("marksTitle").textContent = T.marks;
      $("marksHint").textContent = T.marksHint + (storageOk ? "" : " " + T.storage);
      $("stats").innerHTML = Object.entries(model.summary).map(([k, n]) => `<div class="stat"><strong>${n}</strong><span>${escapeHtml(T.stat[k] || k)}</span></div>`).join("");
      $("toc").innerHTML = model.items.map(i => `<a href="#item-${escapeHtml(i.id)}">${escapeHtml(i.label)}</a>`).join("");
    }

    function renderItems() {
      $("items").innerHTML = model.items.map(item => {
        const shown = shownVerdict(item);
        const notes = [];
        if (shown.degraded) notes.push(T.degraded);
        if (item.empty) notes.push(T.empty);
        const total = itemRequests(item).length;
        return `<article class="card" id="item-${escapeHtml(item.id)}" data-shown="${escapeHtml(shown.verdict)}">
          <h3>${escapeHtml(item.label)} ${badge(shown.verdict)}</h3>
          ${item.stories.length ? `<div class="sub">${escapeHtml(T.stories)}: ${item.stories.map(escapeHtml).join(", ")}</div>` : ""}
          <div class="sub">${shown.open}/${total} ${escapeHtml(T.requestsLabel)} ${escapeHtml(T.open)}</div>
          ${notes.map(n => `<div class="sub">${escapeHtml(n)}</div>`).join("")}
        </article>`;
      }).join("");
    }

    function renderRecipients() {
      if (!model.recipients.length) {
        $("recipients").innerHTML = `<div class="empty">${escapeHtml(T.none)}</div>`;
        return;
      }
      $("recipients").innerHTML = model.recipients.map((recipient, index) => {
        const rows = recipient.request_ids.map(id => requestsById[id]).map(r => `
          <label class="req${marks[r.id] ? " marked" : ""}">
            <input type="checkbox" data-request="${escapeHtml(r.id)}"${marks[r.id] ? " checked" : ""}>
            <span class="req-text"><span class="tag b-${escapeHtml(r.blocks)}">${escapeHtml(T.blocks[r.blocks])}</span><strong>${escapeHtml(r.source_id)}</strong> ${escapeHtml(r.text)}</span>
          </label>`).join("");
        return `<section class="recipient">
          <header><span>${escapeHtml(recipient.label)}${recipient.assigned ? "" : ` <span class="unassigned">· ${escapeHtml(T.unassigned)}</span>`}</span>
          <button type="button" data-copy="${index}">${escapeHtml(T.copy)}</button></header>
          ${rows}
        </section>`;
      }).join("");
    }

    function requestText(recipient) {
      const open = recipient.request_ids.map(id => requestsById[id]).filter(r => !marks[r.id]);
      const name = recipient.label.replace(/\s*\(.*\)$/, "");
      return [T.greeting(name), "", ...open.map((r, i) => `${i + 1}. [${r.source_id}] ${r.text} (${T.blocks[r.blocks]})`)].join("\n");
    }

    async function copyText(text, button) {
      try {
        await navigator.clipboard.writeText(text);
      } catch (error) {
        $("marksBox").value = text;
        $("marksBox").select();
      }
      const before = button.textContent;
      button.textContent = T.copied;
      setTimeout(() => { button.textContent = before; }, 1200);
    }

    // The header follows the workspace card: same degradation, same marks.
    function renderVerdictBadge() {
      const workspace = model.items.find(i => i.kind === "workspace");
      $("verdict").innerHTML = badge(workspace ? shownVerdict(workspace).verdict : model.verdict.verdict);
    }

    function render() {
      renderVerdictBadge();
      renderItems();
      renderRecipients();
    }

    document.addEventListener("change", (event) => {
      const id = event.target?.dataset?.request;
      if (!id) return;
      if (event.target.checked) marks[id] = true; else delete marks[id];
      saveMarks();
      render();
    });
    document.addEventListener("click", (event) => {
      const index = event.target?.dataset?.copy;
      if (index === undefined) return;
      copyText(requestText(model.recipients[Number(index)]), event.target);
    });
    $("exportMarks").addEventListener("click", () => {
      $("marksBox").value = JSON.stringify({ view: "readiness", project_id: model.project_id, marks }, null, 2);
      $("marksStatus").textContent = T.exported;
    });
    $("importMarks").addEventListener("click", () => {
      try {
        const data = JSON.parse($("marksBox").value);
        if (!data || data.view !== "readiness" || data.project_id !== model.project_id || typeof data.marks !== "object") throw new Error("shape");
        marks = Object.fromEntries(Object.keys(data.marks).filter(id => requestsById[id]).map(id => [id, true]));
        saveMarks();
        render();
        $("marksStatus").textContent = T.imported;
      } catch (error) {
        $("marksStatus").textContent = T.badImport;
      }
    });
    $("clearMarks").addEventListener("click", () => {
      marks = {};
      saveMarks();
      render();
      $("marksStatus").textContent = T.cleared;
    });

    renderHeader();
    render();
