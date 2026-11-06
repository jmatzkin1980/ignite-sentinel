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
// ----
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
