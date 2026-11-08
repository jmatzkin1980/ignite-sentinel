    const model = JSON.parse(document.getElementById("view-data").textContent);
    const $ = (id) => document.getElementById(id);
    const feedbackKey = "ignite-sentinel:view-feedback:" + [model.project_id, model.artifact, model.source_relative_path].join(":");
    const guidedKey = "ignite-sentinel:view-guided-response:" + [model.project_id, model.artifact, model.source_relative_path].join(":");
    const sourceShaKey = feedbackKey + ":source-sha";
    const provKey = "ignite-sentinel:view-provenance";
    let feedbackComments = loadFeedback();
    let feedbackTarget = { type: "section", id: model.sections[0]?.id || "content" };
    let guidedAnswers = loadGuidedAnswers();
    $("phase").textContent = model.phase + " · read-only derived view";
    $("title").textContent = model.project_id + " · " + model.label;
    $("meta").innerHTML = [
      "Source: <code>" + escapeHtml(model.source_path) + "</code>",
      "Source cut-off: " + escapeHtml(model.provenance.cutoff) + " · sha256 " + escapeHtml(model.provenance.source_sha256),
      "Language: " + escapeHtml(model.language)
    ].join("<span>·</span>");
    $("stats").innerHTML = Object.entries(model.summary).map(([k, v]) => `<div class="stat"><strong>${v}</strong><span>${label(k)}</span></div>`).join("");
    $("toc").innerHTML = model.sections.map(s => `<a class="level-${s.level}" href="#${s.id}">${escapeHtml(s.title)}</a>`).join("");
    $("content").innerHTML = model.sections.map(sectionHtml).join("");
    $("markers").innerHTML = model.markers.length ? model.markers.map(markerPill).join("") : `<div class="empty">No pending, gap, or assumption markers found.</div>`;
    const citationItems = [
      ...model.citations.map(evidenceCard),
      ...model.trace.nodes.map(n => `<a class="pill" href="#content"><strong>${escapeHtml(n.id || "")}</strong><br>${escapeHtml(n.type || "")} · ${escapeHtml(n.title || "")}</a>`)
    ];
    $("citations").innerHTML = citationItems.length ? citationItems.join("") : `<div class="empty">No citations or matching trace nodes found.</div>`;
    renderFeedbackTarget();
    renderFeedbackList();
    renderGuidedResponses();
    checkSourceChanged();
    applyProvenance(storedProvenance());
    $("provToggle").addEventListener("click", () => {
      const show = !document.body.classList.contains("show-prov");
      applyProvenance(show);
      try { localStorage.setItem(provKey, show ? "show" : "hide"); } catch (e) {}
    });
    window.addEventListener("hashchange", () => revealIfHidden(location.hash.slice(1)));
    revealIfHidden(location.hash.slice(1));
    document.addEventListener("click", event => {
      const link = event.target.closest && event.target.closest('a[href^="#"]');
      if (link) revealIfHidden(link.getAttribute("href").slice(1));
    });
    $("search").addEventListener("input", event => {
      const q = event.target.value.toLowerCase();
      document.querySelectorAll(".artifact-section").forEach(section => {
        section.classList.toggle("hidden", q && !section.textContent.toLowerCase().includes(q));
      });
    });
    $("markerFilter").addEventListener("change", event => {
      const value = event.target.value;
      document.querySelectorAll("#markers .pill").forEach(item => {
        item.hidden = value !== "all" && item.dataset.kind !== value;
      });
    });
    $("guidedAudienceFilter").addEventListener("change", renderGuidedResponses);
    document.addEventListener("input", event => {
      if (event.target.matches(".guided-answer")) {
        guidedAnswers[event.target.dataset.guidedId] = event.target.value;
        persistGuidedAnswers();
        renderGuidedProgress();
      }
    });
    document.addEventListener("click", event => {
      if (event.target.matches(".source-toggle")) {
        const target = document.getElementById(event.target.dataset.target);
        target.classList.toggle("open");
      }
      if (event.target.matches(".feedback-target")) {
        feedbackTarget = {
          type: event.target.dataset.targetType || "section",
          id: event.target.dataset.targetId || "content",
          marker: event.target.dataset.marker || "",
          gapId: event.target.dataset.gapId || "",
        };
        renderFeedbackTarget();
        $("feedbackText").focus();
      }
    });
    $("saveFeedback").addEventListener("click", saveFeedbackComment);
    $("exportFeedback").addEventListener("click", exportFeedbackMarkdown);
    $("mailFeedback").addEventListener("click", draftFeedbackEmail);
    $("clearFeedback").addEventListener("click", () => {
      feedbackComments = [];
      persistFeedback();
      renderFeedbackList();
      $("feedbackExportText").classList.remove("open");
    });

    function sectionHtml(s) {
      const readiness = s.readiness || { status: "populated" };
      return `<section class="artifact-section" id="${s.id}">
        <div class="section-meta">${escapeHtml(s.section_path)} · lines ${s.line_start}-${s.line_end} · <span class="badge ${escapeHtml(readiness.status)}">${escapeHtml(readiness.status)}</span></div>
        <div class="content">${highlightSection(s)}</div>
        <button class="feedback-target" data-target-type="section" data-target-id="${s.id}">Add feedback</button>
        <button class="source-toggle" data-target="src-${s.id}">Markdown source</button>
        <pre class="markdown-source" id="src-${s.id}">${escapeHtml(s.markdown)}</pre>
      </section>`;
    }
    function markerPill(item) {
      const gapId = item.marker.startsWith("GAP-") ? item.marker : "";
      return `<div class="pill ${item.kind}" data-kind="${item.kind}">
        <a href="#${item.id}"><strong>${escapeHtml(item.marker)}</strong><br>${escapeHtml(item.section_path || "")}</a>
        ${metadataHtml(item)}
        <button class="feedback-target" data-target-type="marker" data-target-id="${item.id}" data-marker="${escapeHtml(item.marker)}" data-gap-id="${escapeHtml(gapId)}">Add feedback</button>
      </div>`;
    }
    function pill(item, text, kind) {
      return `<a class="pill ${kind}" href="#${item.section_id || "content"}"><strong>${escapeHtml(text)}</strong><br>${escapeHtml(item.section_path || "")}</a>`;
    }
    function evidenceCard(item) {
      const node = (model.graph_nodes || {})[item.trace_id] || {};
      const fragment = (model.source_fragments || {})[item.trace_id] || {};
      const mini = item.mini_graph || { node_ids: [], edges: [] };
      const graph = { nodes: (mini.node_ids || []).map(id => (model.graph_nodes || {})[id]).filter(Boolean), edges: mini.edges || [] };
      return `<details class="evidence-card" id="evidence-${item.id}">
        <summary>${escapeHtml(item.citation)} <span>${escapeHtml(node.type || "citation")} · ${escapeHtml(item.section_path || "")}</span></summary>
        <div class="pill-meta">
          ${node.id ? `<span><b>Trace node:</b> ${escapeHtml(node.id)} · ${escapeHtml(node.title || "")}</span>` : `<span><b>Trace node:</b> No matching graph node</span>`}
          ${node.path ? `<span><b>Path:</b> ${escapeHtml(node.path)}</span>` : ""}
          ${fragment.available ? `<span><b>Source Fragment:</b> lines ${fragment.line_start}-${fragment.line_end}${fragment.truncated ? " · truncated" : ""}</span><pre class="source-fragment">${escapeHtml(fragment.text)}</pre>` : `<span><b>Source Fragment:</b> not available in local graph path</span>`}
          ${miniGraphHtml(graph)}
        </div>
      </details>`;
    }
    function miniGraphHtml(graph) {
      const nodes = graph.nodes || [];
      const edges = graph.edges || [];
      if (!nodes.length && !edges.length) return `<span><b>Mini Trace:</b> no direct graph relations found.</span>`;
      return `<div class="mini-graph"><b>Mini Trace</b>
        ${nodes.map(n => `<div class="mini-node"><strong>${escapeHtml(n.id || "")}</strong><br>${escapeHtml(n.type || "")} · ${escapeHtml(n.title || "")}</div>`).join("")}
        ${edges.map(e => `<div class="mini-edge">${escapeHtml(e.from || "")} → ${escapeHtml(e.to || "")} · ${escapeHtml(e.relation || "")}</div>`).join("")}
      </div>`;
    }
    function metadataHtml(item) {
      const meta = item.metadata || {};
      const rows = [];
      if (meta.lens || meta.severity || meta.status) rows.push(`<span><b>Lens/status:</b> ${escapeHtml([meta.lens, meta.severity, meta.status].filter(Boolean).join(" · "))}</span>`);
      if (meta.why) rows.push(`<span><b>Why it matters:</b> ${escapeHtml(meta.why)}</span>`);
      if (meta.unblocks) rows.push(`<span><b>Unblocks:</b> ${escapeHtml(meta.unblocks)}</span>`);
      if (meta.expected_format) rows.push(`<span><b>Expected format:</b> ${escapeHtml(meta.expected_format)}</span>`);
      if (meta.owner || meta.risk) rows.push(`<span><b>Owner/risk:</b> ${escapeHtml([meta.owner, meta.risk].filter(Boolean).join(" · "))}</span>`);
      if (meta.statement) rows.push(`<span><b>Assumption:</b> ${escapeHtml(meta.statement)}</span>`);
      if (meta.closes_gap) rows.push(`<span><b>Closes gap:</b> ${escapeHtml(meta.closes_gap)}</span>`);
      if (meta.readiness_cells?.length) rows.push(`<span><b>Readiness:</b> ${escapeHtml(meta.readiness_cells.map(c => [c.area, c.lens, c.status].filter(Boolean).join(" / ")).join("; "))}</span>`);
      return rows.length ? `<span class="pill-meta">${rows.join("")}</span>` : "";
    }
    function highlightSection(section) {
      let value = section.html;
      model.markers.filter(m => m.section_id === section.id).forEach(marker => {
        const pattern = new RegExp(escapeRegExp(marker.marker));
        value = value.replace(pattern, `<mark id="${marker.id}" class="marker ${marker.kind}">${escapeHtml(marker.marker)}</mark>`);
      });
      return value;
    }
    function loadGuidedAnswers() {
      try {
        const value = JSON.parse(localStorage.getItem(guidedKey) || "{}");
        return value && typeof value === "object" && !Array.isArray(value) ? value : {};
      } catch {
        return {};
      }
    }
    function persistGuidedAnswers() {
      try { localStorage.setItem(guidedKey, JSON.stringify(guidedAnswers)); } catch (e) {}
      rememberSourceSha();
    }
    function renderGuidedResponses() {
      const filter = $("guidedAudienceFilter").value;
      const items = (model.guided_response?.items || []).filter(item => filter === "all" || item.audience === filter);
      $("guidedResponses").innerHTML = items.length
        ? items.map(guidedItemHtml).join("")
        : `<div class="empty">No guided items for this audience.</div>`;
      renderGuidedProgress();
    }
    function renderGuidedProgress() {
      const clientItems = (model.guided_response?.items || []).filter(item => item.audience === "client" && item.response_needed);
      const answered = clientItems.filter(item => String(guidedAnswers[item.id] || "").trim()).length;
      $("guidedProgress").textContent = `Client progress: ${answered}/${clientItems.length}`;
    }
    function guidedItemHtml(item) {
      const answer = guidedAnswers[item.id] || "";
      const details = [
        item.lens,
        item.severity,
        item.status,
        item.audience_label
      ].filter(Boolean).join(" · ");
      const prompt = item.question || item.statement || item.expected_format || item.id;
      const expected = item.expected_format ? `<span><b>Expected format:</b> ${escapeHtml(item.expected_format)}</span>` : "";
      const owner = item.owner || item.risk ? `<span><b>Owner/risk:</b> ${escapeHtml([item.owner, item.risk].filter(Boolean).join(" · "))}</span>` : "";
      const textarea = item.audience === "client" && item.response_needed
        ? `<textarea class="guided-answer" data-guided-id="${escapeHtml(item.id)}" placeholder="Draft local response">${escapeHtml(answer)}</textarea>`
        : "";
      return `<div class="guided-item ${escapeHtml(item.audience)}">
        <a href="#${escapeHtml(item.marker_id || item.section_id || "content")}">${escapeHtml(item.id)}</a>
        <div class="pill-meta">
          <span>${escapeHtml(details)}</span>
          <span>${escapeHtml(prompt)}</span>
          ${expected}
          ${owner}
        </div>
        ${textarea}
      </div>`;
    }
    function loadFeedback() {
      try {
        const value = JSON.parse(localStorage.getItem(feedbackKey) || "[]");
        return Array.isArray(value) ? value : [];
      } catch {
        return [];
      }
    }
    function persistFeedback() {
      try { localStorage.setItem(feedbackKey, JSON.stringify(feedbackComments)); } catch (e) {}
      rememberSourceSha();
    }
    function saveFeedbackComment() {
      const text = $("feedbackText").value.trim();
      if (!text) return;
      const section = sectionForTarget(feedbackTarget);
      const comment = {
        id: "FBC-" + Date.now(),
        target_type: feedbackTarget.type,
        target_id: feedbackTarget.id,
        marker: feedbackTarget.marker || "",
        gap_id: feedbackTarget.gapId || "",
        section_id: section?.id || "",
        section_path: section?.section_path || "",
        line_start: section?.line_start || "",
        line_end: section?.line_end || "",
        owner_source: $("feedbackOwner").value.trim() || "Artifact review comment",
        decision_status: $("feedbackDecision").value,
        text,
        created_at: new Date().toISOString()
      };
      feedbackComments.push(comment);
      persistFeedback();
      $("feedbackText").value = "";
      renderFeedbackList();
    }
    function renderFeedbackTarget() {
      const section = sectionForTarget(feedbackTarget);
      const marker = feedbackTarget.marker ? " / " + feedbackTarget.marker : "";
      $("feedbackTarget").textContent = "Target: " + feedbackTarget.type + " " + feedbackTarget.id + marker + (section ? " · " + section.section_path : "");
    }
    function renderFeedbackList() {
      $("feedbackList").innerHTML = feedbackComments.length
        ? feedbackComments.map(item => `<div class="feedback-item"><strong>${escapeHtml(item.target_type)} ${escapeHtml(item.marker || item.target_id)}</strong>${targetExists(item) ? "" : " <em>(orphaned: target no longer exists)</em>"}<br>${escapeHtml(item.text)}</div>`).join("")
        : `<div class="empty">No local comments saved.</div>`;
    }
    function exportFeedbackMarkdown() {
      const markdown = buildFeedbackExport(feedbackComments);
      $("feedbackExportText").textContent = markdown;
      $("feedbackExportText").classList.add("open");
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${model.project_id}-${model.artifact}-feedback.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }
    function draftFeedbackEmail() {
      // IMP-211 (H10, H-JOSE-1): restore the mailto draft the approved prototype
      // had (it was lost in the runtime). Local-first: it only opens a pre-filled
      // draft in the user's own mail client, it never sends. mailto cannot carry
      // attachments, so remind the reviewer to attach the downloaded .md.
      const hasGuided = (model.guided_response?.items || []).some(item => String(guidedAnswers[item.id] || "").trim());
      if (!feedbackComments.length && !hasGuided) {
        alert("Save at least one comment or guided answer before drafting the email.");
        return;
      }
      const subject = `Artifact review feedback - ${model.project_id} - ${model.artifact}`;
      const body = buildFeedbackExport(feedbackComments) + "\n\n(If possible, also attach the downloaded .md file - mailto cannot include attachments.)";
      const recipient = model.ba_email || "";
      window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    }
    function buildFeedbackExport(comments) {
      const lines = [
        `# Artifact Review Feedback Export - ${model.project_id}`,
        "",
        `- Source artifact: ${model.source_path}`,
        `- Generated at: ${new Date().toISOString()}`,
        `- Resolve gaps command: sentinel /resolve-gaps ${model.project_id} --source PATH`,
        `- Sync command: sentinel /sync ${model.project_id} --source PATH --note "Artifact review feedback"`,
        "",
      ];
      const guidedLines = buildGuidedResponseExport();
      if (!comments.length && !guidedLines.length) {
        lines.push("No local comments or guided responses were saved before export.", "");
        return lines.join("\n");
      }
      comments.forEach(comment => {
        const gapId = comment.gap_id || (String(comment.marker || "").startsWith("GAP-") ? comment.marker : "");
        const evidence = `${model.source_path}#${comment.target_id}${comment.line_start ? " lines " + comment.line_start + "-" + comment.line_end : ""}`;
        if (gapId) {
          lines.push(`### ${gapId}`);
          lines.push(`- Answer: ${singleLine(comment.text)}`);
          lines.push(`- Owner / source: ${singleLine(comment.owner_source || "Artifact review comment")}`);
          lines.push(`- Evidence or reference: ${singleLine(evidence)}`);
          lines.push(`- Decision status: ${singleLine(comment.decision_status || "pending")}`);
          lines.push("");
        } else {
          lines.push(`### Review Comment: ${comment.id}`);
          lines.push(`- Target: ${comment.target_type} \`${comment.target_id}\``);
          lines.push(`- Source artifact: \`${model.source_path}\``);
          if (comment.section_path) lines.push(`- Section: ${comment.section_path}`);
          lines.push(`- Comment: ${singleLine(comment.text)}`);
          lines.push(`- Suggested command: \`sentinel /sync ${model.project_id} --source PATH --note "Artifact review feedback"\``);
          lines.push("");
        }
      });
      if (guidedLines.length) {
        lines.push("## Guided Responses", "");
        guidedLines.forEach(line => lines.push(line));
      }
      return lines.join("\n");
    }
    function buildGuidedResponseExport() {
      // IMP-211 (H10, H-JOSE-1): the client's drafted guided answers used to
      // stay trapped in localStorage — the exported .md only carried
      // feedbackComments. Fold them in so the round-trip to /resolve-gaps works.
      const items = model.guided_response?.items || [];
      const out = [];
      items.forEach(item => {
        const answer = String(guidedAnswers[item.id] || "").trim();
        if (!answer) return;
        const prompt = item.question || item.statement || item.expected_format || item.id;
        if (String(item.id).startsWith("GAP-")) {
          out.push(`### ${item.id}`);
          out.push(`- Question: ${singleLine(prompt)}`);
          out.push(`- Answer: ${singleLine(answer)}`);
          out.push("- Owner / source: Client guided response");
          out.push("- Decision status: pending");
          out.push("");
        } else {
          out.push(`### Guided Response: ${item.id}`);
          out.push(`- Question: ${singleLine(prompt)}`);
          out.push(`- Answer: ${singleLine(answer)}`);
          out.push("");
        }
      });
      return out;
    }
    function sectionForTarget(target) {
      if (target.type === "section") return model.sections.find(section => section.id === target.id);
      const marker = model.markers.find(item => item.id === target.id);
      if (marker) return model.sections.find(section => section.id === marker.section_id);
      return model.sections[0];
    }
    function singleLine(value) {
      return String(value ?? "").replace(/\s+/g, " ").trim();
    }
    function storedSourceSha() {
      try { return localStorage.getItem(sourceShaKey); } catch (e) { return null; }
    }
    function rememberSourceSha() {
      try { localStorage.setItem(sourceShaKey, model.provenance.source_sha256); } catch (e) {}
    }
    function targetExists(item) {
      if (item.target_type === "marker") return model.markers.some(m => m.id === item.target_id && (!item.marker || m.marker === item.marker));
      return model.sections.some(s => s.id === (item.section_id || item.target_id) && (!item.section_path || s.section_path === item.section_path));
    }
    function checkSourceChanged() {
      const stored = storedSourceSha();
      const hasNotes = feedbackComments.length || Object.keys(guidedAnswers).length;
      $("sourceChanged").hidden = !(stored && hasNotes && stored !== model.provenance.source_sha256);
      if (!stored && hasNotes) rememberSourceSha();
    }
    function applyProvenance(show) {
      document.body.classList.toggle("show-prov", show);
      const button = $("provToggle");
      button.textContent = show ? button.dataset.hide : button.dataset.show;
      button.setAttribute("aria-pressed", show ? "true" : "false");
    }
    function storedProvenance() {
      try { return localStorage.getItem(provKey) === "show"; } catch (e) { return false; }
    }
    function revealIfHidden(id) {
      const target = id && document.getElementById(id);
      if (target && target.closest(".prov") && !document.body.classList.contains("show-prov")) applyProvenance(true);
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    function escapeRegExp(value) {
      return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
    function label(key) {
      return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
  
