/**
 * onboarding.js
 *
 * 첫 실행 온보딩 마법사.
 * /api/onboarding GET으로 완료 여부를 확인하고,
 * 완료되지 않았으면 #pane-onboarding을 표시한다.
 *
 * 단계:
 *   1. 환영
 *   2. LLM 선택 + API 키 입력
 *   3. 연결 테스트
 *   4. 감시 폴더 설정 (선택)
 *   5. 완료
 */

const OB_API = "http://localhost:8765";
let _obStep = 1;
let _obProvider = "ollama";

// ── 진입점: 앱 로드 시 호출 ──────────────────────────────────────────────────
async function checkOnboarding() {
  try {
    const res = await fetch(`${OB_API}/api/onboarding`);
    const data = await res.json();
    if (!data.onboarding_done) {
      _showOnboarding();
    }
  } catch (e) {
    // 서버 미준비 시 재시도 (2초 후)
    setTimeout(checkOnboarding, 2000);
  }
}

function _showOnboarding() {
  // 다른 탭 숨기기
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  document.getElementById("pane-onboarding").classList.remove("hidden");
  // 탭 버튼 비활성화
  document.querySelectorAll(".tab").forEach(el => el.disabled = true);
  _goToStep(1);
}

function _hideOnboarding() {
  document.getElementById("pane-onboarding").classList.add("hidden");
  document.querySelectorAll(".tab").forEach(el => el.disabled = false);
  // 런처 탭으로 전환
  switchTab("launcher");
}

// ── 단계 전환 ─────────────────────────────────────────────────────────────────
function _goToStep(n) {
  _obStep = n;
  document.querySelectorAll(".ob-step").forEach(el => el.classList.add("hidden"));
  const step = document.getElementById(`ob-step-${n}`);
  if (step) step.classList.remove("hidden");
}

// ── Step 1: 환영 ──────────────────────────────────────────────────────────────
function obNext1() {
  _goToStep(2);
}

// ── Step 2: LLM 선택 ──────────────────────────────────────────────────────────
function obSelectProvider(provider) {
  _obProvider = provider;
  document.querySelectorAll(".ob-provider-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.provider === provider);
  });
  const apiKeySection = document.getElementById("ob-apikey-section");
  const ollama_guide = document.getElementById("ob-ollama-guide");
  if (provider === "ollama") {
    apiKeySection.classList.add("hidden");
    ollama_guide.classList.remove("hidden");
  } else {
    apiKeySection.classList.remove("hidden");
    ollama_guide.classList.add("hidden");
  }
}

function obNext2() {
  const apiKey = document.getElementById("ob-api-key").value.trim();
  if (_obProvider !== "ollama" && !apiKey) {
    document.getElementById("ob-step2-msg").textContent = "API 키를 입력해주세요.";
    return;
  }
  document.getElementById("ob-step2-msg").textContent = "";
  _goToStep(3);
}

// ── Step 3: 연결 테스트 ───────────────────────────────────────────────────────
async function obTestConnection() {
  const model = document.getElementById("ob-model-select").value;
  const apiKey = document.getElementById("ob-api-key").value.trim();
  const msgEl = document.getElementById("ob-test-msg");

  // 설정 저장
  await fetch(`${OB_API}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: _obProvider, model, api_key: apiKey }),
  });

  msgEl.textContent = "연결 테스트 중...";
  try {
    const res = await fetch(`${OB_API}/api/settings/test`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      msgEl.textContent = "✅ 연결 성공!";
      document.getElementById("ob-btn-next3").disabled = false;
    } else {
      msgEl.textContent = "❌ " + (data.error || "연결 실패");
    }
  } catch (e) {
    msgEl.textContent = "❌ 서버 오류: " + e.message;
  }
}

function obSkipTest() {
  _goToStep(4);
}

function obNext3() {
  _goToStep(4);
}

// ── Step 4: 감시 폴더 ─────────────────────────────────────────────────────────
function obSkipFolder() {
  _finishOnboarding();
}

async function obSelectFolder() {
  // pywebview 브릿지를 통해 폴더 선택 다이얼로그 열기
  try {
    if (window.pywebview && window.pywebview.api) {
      const folder = await window.pywebview.api.select_watched_folder();
      if (folder) {
        document.getElementById("ob-folder-path").textContent = folder;
        document.getElementById("ob-folder-confirm").classList.remove("hidden");
      }
    }
  } catch (e) {
    console.error("폴더 선택 오류:", e);
  }
}

function obConfirmFolder() {
  _finishOnboarding();
}

// ── Step 5: 완료 ──────────────────────────────────────────────────────────────
async function _finishOnboarding() {
  await fetch(`${OB_API}/api/onboarding/complete`, { method: "POST" });
  _goToStep(5);
}

function obDone() {
  _hideOnboarding();
}
