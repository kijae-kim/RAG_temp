/**
 * analysis.js
 *
 * 분석 탭 렌더링.
 * - paper_ready 이벤트 수신 시 /api/analyze 자동 호출
 * - summary, concepts, progress 이벤트 처리
 */

const ANALYSIS_API = "http://localhost:8765";

// ── 분석 탭 자동 트리거 ─────────────────────────────────────────────────────
function triggerAnalyze() {
  const progressBar = document.getElementById("analysis-progress");
  const progressText = document.getElementById("analysis-progress-text");
  const summaryBox = document.getElementById("analysis-summary");
  const conceptsBox = document.getElementById("analysis-concepts");

  if (progressBar) progressBar.style.width = "10%";
  if (progressText) progressText.textContent = "분석 시작...";

  fetch(`${ANALYSIS_API}/api/analyze`, { method: "POST" })
    .then((res) => {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) return;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              handleAnalysisEvent(ev);
            } catch (_) {}
          }
          read();
        });
      }
      read();
    })
    .catch((err) => {
      if (progressText) progressText.textContent = `⚠️ 분석 실패: ${err.message}`;
    });
}

function markConceptDone(tag) {
  tag.style.background = "var(--success)";
  tag.style.borderColor = "var(--success)";
  tag.style.color = "#1e1e2e";
  tag.title = "이해 완료 ✓";
}

function markConceptUnderstood(tag, concept) {
  fetch(`${ANALYSIS_API}/api/session/concept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ concept }),
  })
    .then((r) => r.ok ? r.json() : null)
    .then((res) => {
      if (res && res.marked) markConceptDone(tag);
    })
    .catch(() => {});
}

function handleAnalysisEvent(ev) {
  const progressBar  = document.getElementById("analysis-progress");
  const progressText = document.getElementById("analysis-progress-text");
  const summaryBox   = document.getElementById("analysis-summary");
  const conceptsBox  = document.getElementById("analysis-concepts");

  switch (ev.type) {
    case "progress":
      if (progressBar)  progressBar.style.width = `${ev.pct}%`;
      if (progressText) {
        const labels = { start: "분석 시작...", summary: "요약 생성 중...", concepts: "개념 추출 중...", saving: "저장 중..." };
        progressText.textContent = labels[ev.step] || `${ev.pct}%`;
      }
      break;

    case "summary":
      if (summaryBox) {
        summaryBox.classList.remove("hidden");
        document.getElementById("summary-text").textContent = ev.content;
      }
      break;

    case "concepts":
      if (conceptsBox && ev.content?.length) {
        conceptsBox.classList.remove("hidden");
        const container = document.getElementById("concepts-tags");
        container.innerHTML = "";
        ev.content.forEach((concept) => {
          const tag = document.createElement("span");
          tag.className = "concept-tag";
          tag.textContent = concept;
          tag.title = "클릭하면 이해 완료로 마킹";
          tag.style.cursor = "pointer";
          tag.addEventListener("click", () => markConceptUnderstood(tag, concept));
          container.appendChild(tag);
        });
      }
      break;

    case "done":
      if (progressText) progressText.textContent = "분석 완료 ✓";
      if (progressBar)  progressBar.style.background = "var(--success)";
      // 저장된 세션에서 이해 완료 개념 표시 복원
      fetch(`${ANALYSIS_API}/api/session`)
        .then((r) => r.ok ? r.json() : null)
        .then((session) => {
          if (!session) return;
          const understood = new Set(
            (session.concepts_learned || []).filter((c) => c.understood).map((c) => c.concept)
          );
          document.querySelectorAll(".concept-tag").forEach((tag) => {
            if (understood.has(tag.textContent)) markConceptDone(tag);
          });
        })
        .catch(() => {});
      break;

    case "error":
      if (progressText) progressText.textContent = `⚠️ ${ev.content}`;
      break;
  }
}
