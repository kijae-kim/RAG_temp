/**
 * settings.js
 *
 * LLM 프로바이더 설정 탭 UI.
 * /api/settings GET/POST + /api/settings/test POST를 사용한다.
 */

const API = "http://localhost:8765";

// 서버 응답 전에도 드롭다운이 동작하도록 기본값을 하드코딩
let _modelOptions = {
  ollama:    ["qwen2.5:7b", "llama3.2:3b", "gemma3:4b", "phi4-mini"],
  openai:    ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
  anthropic: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
  google:    ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
};
let _currentProvider = "ollama";

// ── 초기 로드 ────────────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const res = await fetch(`${API}/api/settings`);
    const data = await res.json();

    if (data.model_options) _modelOptions = data.model_options;
    _currentProvider = data.provider || "ollama";

    _renderProviderBtns(_currentProvider);
    _renderModelSelect(_currentProvider, data.model);

    const apikeySection = document.getElementById("apikey-section");
    const apikeyInput = document.getElementById("api-key-input");
    const apikeyHint = document.getElementById("apikey-hint");

    if (_currentProvider === "ollama") {
      apikeySection.classList.add("hidden");
    } else {
      apikeySection.classList.remove("hidden");
      apikeyInput.value = "";
      apikeyHint.textContent = data.api_key_saved
        ? "✅ API 키가 저장되어 있습니다. 변경하려면 새로 입력하세요."
        : "API 키를 입력해주세요.";
    }
  } catch (e) {
    console.error("설정 로드 실패:", e);
  }
}

// ── 프로바이더 버튼 렌더링 ────────────────────────────────────────────────────
function _renderProviderBtns(active) {
  document.querySelectorAll(".provider-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.provider === active);
  });
}

// ── 모델 셀렉트 렌더링 ────────────────────────────────────────────────────────
function _renderModelSelect(provider, selected) {
  const sel = document.getElementById("model-select");
  sel.innerHTML = "";
  const models = _modelOptions[provider] || [];
  models.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    if (m === selected) opt.selected = true;
    sel.appendChild(opt);
  });
}

// ── 프로바이더 선택 ───────────────────────────────────────────────────────────
function selectProvider(provider) {
  _currentProvider = provider;
  _renderProviderBtns(provider);
  _renderModelSelect(provider, _modelOptions[provider]?.[0]);

  const apikeySection = document.getElementById("apikey-section");
  const apikeyInput = document.getElementById("api-key-input");
  const apikeyHint = document.getElementById("apikey-hint");

  if (provider === "ollama") {
    apikeySection.classList.add("hidden");
  } else {
    apikeySection.classList.remove("hidden");
    apikeyInput.value = "";
    apikeyHint.textContent = "API 키를 입력해주세요.";
  }

  _hideMsg();
}

// ── 저장 ─────────────────────────────────────────────────────────────────────
async function saveSettings() {
  const model = document.getElementById("model-select").value;
  const apiKey = document.getElementById("api-key-input").value.trim();

  if (_currentProvider !== "ollama" && !apiKey) {
    _showMsg("API 키를 입력해주세요.", "error");
    return;
  }

  try {
    const res = await fetch(`${API}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: _currentProvider, model, api_key: apiKey }),
    });
    const data = await res.json();

    if (data.ok) {
      _showMsg("설정이 저장되었습니다. 다음 PDF 로드 시 적용됩니다.", "success");
      if (apiKey) {
        document.getElementById("api-key-input").value = "";
        document.getElementById("apikey-hint").textContent = "✅ API 키가 저장되어 있습니다. 변경하려면 새로 입력하세요.";
      }
      // 채팅 화면의 모델 뱃지 갱신
      if (typeof loadModelBadge === "function") loadModelBadge();
    } else {
      _showMsg(data.error || "저장 실패", "error");
    }
  } catch (e) {
    _showMsg("서버 오류: " + e.message, "error");
  }
}

// ── 연결 테스트 ───────────────────────────────────────────────────────────────
async function testConnection() {
  // 먼저 저장
  const model = document.getElementById("model-select").value;
  const apiKey = document.getElementById("api-key-input").value.trim();

  if (_currentProvider !== "ollama" && !apiKey) {
    _showMsg("API 키를 먼저 입력해주세요.", "error");
    return;
  }

  await fetch(`${API}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: _currentProvider, model, api_key: apiKey }),
  });

  _showMsg("연결 테스트 중...", "info");

  try {
    const res = await fetch(`${API}/api/settings/test`, { method: "POST" });
    const data = await res.json();

    if (data.ok) {
      _showMsg("✅ 연결 성공!", "success");
    } else {
      _showMsg("❌ " + (data.error || "연결 실패"), "error");
    }
  } catch (e) {
    _showMsg("❌ 서버 오류: " + e.message, "error");
  }
}

// ── 메시지 표시 ───────────────────────────────────────────────────────────────
function _showMsg(text, type) {
  const el = document.getElementById("settings-msg");
  el.textContent = text;
  el.className = `settings-msg settings-msg--${type}`;
  el.classList.remove("hidden");
}

function _hideMsg() {
  document.getElementById("settings-msg").classList.add("hidden");
}

