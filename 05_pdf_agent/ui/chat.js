/**
 * chat.js
 *
 * - GET /api/events SSE 구독 → 논문 상태 변경 즉시 반영
 * - POST /api/chat SSE 스트리밍 → 타이핑 애니메이션
 * - paper_ready 이벤트 수신 시 /api/analyze 자동 호출 (Phase 2)
 */

const API = "http://localhost:8765";
let isSending = false;
let currentStyle = "default";

// ── SSE 이벤트 채널 구독 ────────────────────────────────────────────────────
function connectEventStream() {
  const es = new EventSource(`${API}/api/events`);

  es.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleServerEvent(event);
  };

  es.onerror = () => {
    // 연결 끊기면 3초 후 재연결
    es.close();
    setTimeout(connectEventStream, 3000);
  };
}

function handleServerEvent(event) {
  switch (event.type) {
    case "connected":
      updateBannerFromStatus(event.status);
      break;

    case "model_loading":
      showStatusBanner(event.msg, false);
      break;

    case "model_ready":
      hideStatusBanner();
      break;

    case "paper_changed":
      document.getElementById("banner-text").textContent =
        `📄 ${event.paper_name} — 인덱싱 중...`;
      showStatusBanner("인덱싱 중...", false);
      setBtnEnabled(false);
      break;

    case "loading_progress":
      showStatusBanner(`인덱싱 중... ${event.pct}%`, false);
      break;

    case "paper_ready":
      document.getElementById("banner-text").textContent =
        `📄 ${event.paper_name}  ${event.chunks}청크`;
      hideStatusBanner();
      setBtnEnabled(true);
      appendBotMessage(`**${event.paper_name}** 로드 완료 (${event.chunks}청크)\n분석 탭에서 요약과 핵심 개념을 확인하세요.`);
      // 분석 탭 자동 트리거
      if (typeof triggerAnalyze === "function") triggerAnalyze();
      break;

    case "error":
      showStatusBanner(`⚠️ ${event.msg}`, true);
      break;

    case "ollama_error":
      showStatusBanner("⚠️ Ollama가 실행되지 않았습니다. 터미널에서 'ollama serve'를 실행하세요.", true);
      break;

    case "session_resume":
      showResumeCard(event.session);
      break;
  }
}

function updateBannerFromStatus(status) {
  if (status === "ready") {
    setBtnEnabled(true);
  } else if (status === "loading") {
    setBtnEnabled(false);
    showStatusBanner("인덱싱 중...", false);
  } else if (status === "no_paper") {
    setBtnEnabled(false);
  } else if (status === "error") {
    showStatusBanner("⚠️ 오류가 발생했습니다.", true);
  }
}

// ── 채팅 전송 ───────────────────────────────────────────────────────────────
function sendMessage() {
  const input = document.getElementById("question-input");
  const question = input.value.trim();
  if (!question || isSending) return;

  input.value = "";
  isSending = true;
  setBtnEnabled(false);

  appendUserMessage(question);
  const botBubble = appendBotMessage("");
  const cursor = document.createElement("span");
  cursor.className = "cursor";
  botBubble.appendChild(cursor);

  fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: getSessionId(), style: currentStyle }),
  })
    .then((res) => {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            cursor.remove();
            isSending = false;
            setBtnEnabled(true);
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              if (ev.type === "intent_classifying") showIntentBadge(botBubble, "분류 중...");
              if (ev.type === "intent")             showIntentBadge(botBubble, ev.content);
              if (ev.type === "token") appendToken(botBubble, cursor, ev.content);
              if (ev.type === "sources") renderSources(botBubble, ev.content);
              if (ev.type === "error") appendToken(botBubble, cursor, `⚠️ ${ev.content}`);
              if (ev.type === "done") {
                cursor.remove();
                isSending = false;
                setBtnEnabled(true);
              }
            } catch (_) {}
          }

          read();
        });
      }
      read();
    })
    .catch((err) => {
      cursor.remove();
      appendToken(botBubble, null, `⚠️ 연결 오류: ${err.message}`);
      isSending = false;
      setBtnEnabled(true);
    });
}

// ── 세션 초기화 ─────────────────────────────────────────────────────────────
async function clearSession() {
  await fetch(`${API}/api/session/clear`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: getSessionId() }),
  }).catch(() => {});
  document.getElementById("chat-area").innerHTML = "";
  appendBotMessage("대화가 초기화되었습니다.");
}

// ── 탭 전환 ─────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((p) => p.classList.add("hidden"));
  document.getElementById(`tab-${name}`).classList.add("active");
  document.getElementById(`pane-${name}`).classList.remove("hidden");
  if (name === "settings" && typeof loadSettings === "function") loadSettings();
}

// ── DOM 헬퍼 ────────────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const area = document.getElementById("chat-area");
  const msg = document.createElement("div");
  msg.className = "message user";
  msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  area.appendChild(msg);
  area.scrollTop = area.scrollHeight;
}

function appendBotMessage(text) {
  const area = document.getElementById("chat-area");
  const msg = document.createElement("div");
  msg.className = "message bot";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  area.appendChild(msg);
  area.scrollTop = area.scrollHeight;
  return bubble;
}

function appendToken(bubble, cursor, token) {
  if (cursor && cursor.parentNode === bubble) {
    bubble.insertBefore(document.createTextNode(token), cursor);
  } else {
    bubble.appendChild(document.createTextNode(token));
  }
  const area = document.getElementById("chat-area");
  area.scrollTop = area.scrollHeight;
}

function renderSources(bubble, sources) {
  if (!sources || sources.length === 0) return;
  const msgEl = bubble.parentElement;

  // 출처 칩 목록
  const container = document.createElement("div");
  container.className = "sources";

  // 인용 카드 (클릭 시 표시/숨김)
  const quoteCard = document.createElement("div");
  quoteCard.className = "source-quote hidden";

  sources.forEach((s, idx) => {
    const chip = document.createElement("span");
    chip.className = "source-chip";
    chip.textContent = `p.${s.page}`;
    chip.title = s.text ? s.text.slice(0, 120) + "…" : "";

    if (s.pdf_path || s.text) {
      chip.classList.add("clickable");
      chip.onclick = () => {
        const alreadyActive = chip.classList.contains("active");

        // 모든 칩 active 해제
        container.querySelectorAll(".source-chip").forEach((c) =>
          c.classList.remove("active")
        );

        if (alreadyActive) {
          // 같은 칩 재클릭 → 카드 닫기
          quoteCard.classList.add("hidden");
        } else {
          // 인용 카드 업데이트
          chip.classList.add("active");
          quoteCard.innerHTML = `
            <div class="source-quote-meta">📄 p.${s.page}</div>
            <div class="source-quote-text">${escapeHtml(s.text || "")}</div>
          `;
          quoteCard.classList.remove("hidden");
          // PDF 페이지 이동
          if (s.pdf_path && window.pywebview && window.pywebview.api) {
            window.pywebview.api.open_pdf_at_page(s.pdf_path, s.page, s.text || "");
          }
        }
        document.getElementById("chat-area").scrollTop =
          document.getElementById("chat-area").scrollHeight;
      };
    }
    container.appendChild(chip);
  });

  msgEl.appendChild(container);
  msgEl.appendChild(quoteCard);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showStatusBanner(msg, isError) {
  const banner = document.getElementById("status-banner");
  document.getElementById("status-banner-text").textContent = msg;
  banner.className = "status-banner" + (isError ? " error" : "");
}

function hideStatusBanner() {
  document.getElementById("status-banner").className = "status-banner hidden";
}

function setBtnEnabled(enabled) {
  document.getElementById("btn-send").disabled = !enabled;
}

function getSessionId() {
  if (!sessionStorage.getItem("sid")) {
    sessionStorage.setItem("sid", `session_${Date.now()}`);
  }
  return sessionStorage.getItem("sid");
}

function showIntentBadge(bubble, intent) {
  let badge = bubble.parentElement.querySelector(".intent-badge");
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "intent-badge";
    bubble.parentElement.insertBefore(badge, bubble);
  }
  const labels = { qa: "🔍 검색", explain: "📖 설명", quiz: "📝 퀴즈", summarize: "📋 요약", out_of_scope: "🚫 범위 밖", "분류 중...": "⏳ 분류 중..." };
  badge.textContent = labels[intent] || `🔧 ${intent}`;
}

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showResumeCard(session) {
  const understood = (session.concepts_learned || []).filter((c) => c.understood).length;
  const total = (session.concepts_learned || []).length;
  const infoLines = [
    `📚 이전 학습 기록 (${session.total_sessions}번째 세션)`,
    `🕐 마지막 학습: ${session.last_accessed.replace("T", " ")}`,
    `💬 누적 질문: ${session.questions_asked}회`,
    total > 0 ? `💡 개념 이해: ${understood}/${total}개` : null,
  ].filter(Boolean).join("\n");

  const area = document.getElementById("chat-area");
  const msg = document.createElement("div");
  msg.className = "message bot";

  const card = document.createElement("div");
  card.className = "resume-card";
  card.textContent = infoLines;

  const actions = document.createElement("div");
  actions.className = "resume-card-actions";

  const btnResume = document.createElement("button");
  btnResume.className = "btn-resume primary";
  btnResume.textContent = "이어서 학습하기";
  btnResume.onclick = () => {
    msg.remove();
    appendBotMessage("이전 학습을 이어서 진행합니다. 질문을 입력해주세요!");
  };

  const btnRestart = document.createElement("button");
  btnRestart.className = "btn-resume secondary";
  btnRestart.textContent = "처음부터";
  btnRestart.onclick = () => {
    msg.remove();
    clearSession();
  };

  actions.appendChild(btnResume);
  actions.appendChild(btnRestart);
  card.appendChild(actions);
  msg.appendChild(card);
  area.appendChild(msg);
  area.scrollTop = area.scrollHeight;
}

function setStyle(style) {
  currentStyle = style;
  document.querySelectorAll(".style-btn").forEach((btn) => {
    btn.classList.remove("active");
    if (btn.textContent === { brief: "간결", default: "기본", detailed: "상세" }[style]) {
      btn.classList.add("active");
    }
  });
}

// ── 창 닫기 ──────────────────────────────────────────────────────────────────
async function closeWindow() {
  try {
    await window.pywebview.api.close_window();
  } catch (_) {
    window.close();  // pywebview 브릿지 없을 때 폴백
  }
}

// ── 키보드 단축키 ────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  connectEventStream();

  document.getElementById("question-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
