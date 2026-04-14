/**
 * launcher.js
 *
 * 런처 pane (#pane-launcher) 로직.
 * - 앱 시작 시 세션 목록 표시
 * - 새 PDF 열기 / 논문 폴더 설정 / 이어서 읽기
 */

const LAUNCHER_API = "http://localhost:8765";
let _launcherPollId = null;

// ── 진입점: switchTab('launcher') 시 호출 ──────────────────────────────────
async function loadLauncher() {
  // 이미 폴링 중이면 재시작 방지
  if (_launcherPollId) clearInterval(_launcherPollId);

  await _refreshSessionList();
  await _refreshFolderButton();

  // 논문이 로드되면 채팅으로 자동 전환
  _launcherPollId = setInterval(async () => {
    try {
      const res = await fetch(`${LAUNCHER_API}/api/status`);
      const data = await res.json();
      if (data.status === "loading" || data.status === "ready") {
        clearInterval(_launcherPollId);
        _launcherPollId = null;
        switchTab("chat");
      }
    } catch (e) { /* 서버 준비 중 */ }
  }, 1000);
}

// ── 세션 목록 새로 고침 ────────────────────────────────────────────────────
async function _refreshSessionList() {
  const container = document.getElementById("launcher-sessions");
  try {
    const res = await fetch(`${LAUNCHER_API}/api/sessions`);
    const data = await res.json();
    _renderSessions(data.sessions || []);
  } catch (e) {
    container.innerHTML = '<p class="launcher-empty">세션 목록을 불러오지 못했습니다.</p>';
  }
}

function _renderSessions(sessions) {
  const container = document.getElementById("launcher-sessions");
  if (!sessions.length) {
    container.innerHTML = '<p class="launcher-empty">저장된 세션이 없습니다.<br>새 PDF를 열어 시작하세요.</p>';
    return;
  }
  container.innerHTML = sessions.map(s => `
    <div class="launcher-card${s.missing ? " launcher-card-missing" : ""}">
      <div class="launcher-card-name">📄 ${_escLauncher(s.pdf_name)}</div>
      <div class="launcher-card-meta">${_fmtDate(s.last_accessed)} · ${s.total_sessions}회</div>
      ${s.missing
        ? '<div class="launcher-missing-label">파일 없음</div>'
        : `<button class="launcher-btn-resume" onclick="resumeSession('${s.pdf_hash}')">이어서 읽기</button>`
      }
    </div>
  `).join("");
}

// ── 논문 폴더 버튼 텍스트 갱신 ───────────────────────────────────────────
async function _refreshFolderButton() {
  try {
    const res = await fetch(`${LAUNCHER_API}/api/settings`);
    const data = await res.json();
    const btn = document.getElementById("btn-paper-folder");
    if (!btn) return;
    if (data.watched_folder) {
      const name = data.watched_folder.split("/").pop();
      btn.textContent = `📁 논문 폴더: ${name}`;
    } else {
      btn.textContent = "📁 논문 폴더 설정...";
    }
  } catch (e) { /* 무시 */ }
}

// ── 새 PDF 열기 ───────────────────────────────────────────────────────────
async function openNewPdf() {
  let path;
  try {
    path = await window.pywebview.api.open_file_dialog();
  } catch (e) {
    // 개발 모드(pywebview 없음): 경로 수동 입력
    path = prompt("PDF 경로 입력 (개발 모드):");
  }
  if (!path) return;

  // 인덱싱과 병렬로 즉시 PDF 열기 — 사용자가 읽으면서 로딩 기다릴 수 있음
  if (window.pywebview?.api?.open_pdf) {
    window.pywebview.api.open_pdf(path);
  }

  const res = await fetch(`${LAUNCHER_API}/api/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "PDF 로드 실패");
  }
  // 성공 시 상태 폴링이 paper_ready 감지해 자동으로 switchTab('chat') 호출
}

// ── 논문 폴더 설정 ────────────────────────────────────────────────────────
async function setPaperFolder() {
  let path;
  try {
    path = await window.pywebview.api.set_paper_folder();
  } catch (e) {
    path = prompt("논문 폴더 경로 입력 (개발 모드):");
  }
  if (!path) return;
  const name = path.split("/").pop();
  document.getElementById("btn-paper-folder").textContent = `📁 논문 폴더: ${name}`;
}

// ── 세션 재개 ─────────────────────────────────────────────────────────────
async function resumeSession(hash) {
  const res = await fetch(`${LAUNCHER_API}/api/sessions/${hash}/resume`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "세션 재개 실패: PDF 파일을 찾을 수 없습니다.");
    await _refreshSessionList();
    return;
  }
  const data = await res.json();

  // 채팅 기록 복원
  if (data.chat_messages && data.chat_messages.length) {
    _restoreChatHistory(data.chat_messages);
  }

  // 이전에 읽던 PDF를 Preview에서 열기
  if (data.pdf_path && window.pywebview?.api?.open_pdf) {
    window.pywebview.api.open_pdf(data.pdf_path);
  }

  clearInterval(_launcherPollId);
  _launcherPollId = null;
  switchTab("chat");
}

function _restoreChatHistory(messages) {
  const area = document.getElementById("chat-area");
  area.innerHTML = "";
  messages.forEach(m => {
    const div = document.createElement("div");
    div.className = `message ${m.role === "user" ? "user" : "bot"}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = m.content;
    div.appendChild(bubble);
    area.appendChild(div);
  });
  area.scrollTop = area.scrollHeight;
}

// ── 유틸 ─────────────────────────────────────────────────────────────────
function _fmtDate(iso) {
  return iso ? iso.slice(0, 10) : "";
}

function _escLauncher(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
