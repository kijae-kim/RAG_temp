# PDFChatbot 배포 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `git tag v1.0.0` 하나로 DMG 빌드 → GitHub Pages 배포까지 자동화하고, 첫 실행 온보딩 마법사를 추가한다.

**Architecture:** Private 소스 레포(RAG_Study)에서 GitHub Actions가 py2app으로 DMG를 빌드하고 Public 레포(pdfchatbot-releases)의 GitHub Pages에 업로드한다. 앱 첫 실행 시 `preferences.json` 부재를 감지해 온보딩 마법사를 표시한다.

**Tech Stack:** py2app, create-dmg, GitHub Actions (macos-14), GitHub Pages, vanilla JS (onboarding wizard), FastAPI (onboarding status API)

---

## 파일 구조 (생성/수정)

| 파일 | 생성/수정 | 역할 |
|---|---|---|
| `05_pdf_agent/menubar_app.py` | 수정 | `__version__` 상수 추가 |
| `05_pdf_agent/setup.py` | 생성 | py2app 빌드 설정 |
| `05_pdf_agent/build.sh` | 생성 | 로컬 빌드 스크립트 |
| `05_pdf_agent/entitlements.plist` | 생성 | 코드 서명용 권한 목록 |
| `05_pdf_agent/ui/onboarding.js` | 생성 | 온보딩 마법사 UI 로직 |
| `05_pdf_agent/ui/index.html` | 수정 | `#pane-onboarding` div 추가 |
| `05_pdf_agent/api/routes/onboarding.py` | 생성 | `GET /api/onboarding` 상태 확인 |
| `05_pdf_agent/api/server.py` | 수정 | onboarding 라우터 등록 |
| `.github/workflows/release.yml` | 생성 | GitHub Actions 릴리스 워크플로우 |
| `pdfchatbot-releases/index.html` | 생성 | GitHub Pages 랜딩 페이지 (별도 레포) |

---

## Task 1: `__version__` 상수 추가

**Files:**
- Modify: `05_pdf_agent/menubar_app.py`

- [ ] **Step 1: `__version__` 상수를 imports 바로 아래에 추가**

`05_pdf_agent/menubar_app.py`의 `import rumps` 다음 줄(현재 약 26번째 줄)에 추가:

```python
__version__ = "1.0.0"
```

- [ ] **Step 2: 동작 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
grep '__version__' 05_pdf_agent/menubar_app.py
```

Expected output:
```
__version__ = "1.0.0"
```

- [ ] **Step 3: 커밋**

```bash
git add 05_pdf_agent/menubar_app.py
git commit -m "Chore: 앱 버전 상수 추가 v1.0.0"
```

---

## Task 2: py2app 설정 파일 작성

**Files:**
- Create: `05_pdf_agent/setup.py`

- [ ] **Step 1: `setup.py` 작성**

```python
"""
setup.py — py2app 빌드 설정

실행:
  cd 05_pdf_agent
  python setup.py py2app
"""
from setuptools import setup

APP = ['menubar_app.py']

DATA_FILES = [
    ('ui', [
        'ui/index.html',
        'ui/chat.js',
        'ui/style.css',
        'ui/settings.js',
        'ui/analysis.js',
        'ui/onboarding.js',
        'ui/floating_button.html',
    ]),
    ('agent', [
        'agent/__init__.py',
        'agent/llm_config.py',
        'agent/tools.py',
        'agent/paper_agent.py',
    ]),
    ('api', [
        'api/__init__.py',
        'api/server.py',
        'api/engine_state.py',
    ]),
    ('api/routes', [
        'api/routes/__init__.py',
        'api/routes/chat.py',
        'api/routes/document.py',
        'api/routes/settings.py',
        'api/routes/onboarding.py',
        'api/routes/agent.py',
        'api/routes/events.py',
        'api/routes/session.py',
    ]),
    ('session', [
        'session/__init__.py',
        'session/session_manager.py',
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'assets/icon.icns',
    'packages': [
        'rumps',
        'uvicorn',
        'fastapi',
        'starlette',
        'pydantic',
        'requests',
        'langchain_core',
        'langchain_ollama',
        'langchain_openai',
        'langchain_anthropic',
        'langchain_google_genai',
        'langchain_classic',
        'langchain_community',
        'langchain_huggingface',
        'faiss',
        'rank_bm25',
        'pypdf',
        'fitz',
        'sentence_transformers',
        'torch',
        'transformers',
        'langgraph',
    ],
    'excludes': [
        'streamlit',
        'ragas',
        'playwright',
        'chromadb',
        'IPython',
        'jupyter',
    ],
    'plist': {
        'CFBundleName':               'PDFChatbot',
        'CFBundleDisplayName':        'PDFChatbot',
        'CFBundleIdentifier':         'com.gimgijae.pdfchatbot',
        'CFBundleVersion':            '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement':                True,
        'NSHighResolutionCapable':    True,
        'NSDownloadsFolderUsageDescription': 'PDF 파일에 접근합니다.',
        'NSDocumentsFolderUsageDescription': 'PDF 파일에 접근합니다.',
        'NSDesktopFolderUsageDescription':   'PDF 파일에 접근합니다.',
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

- [ ] **Step 2: syntax 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study/05_pdf_agent
poetry run python -c "import ast; ast.parse(open('setup.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add 05_pdf_agent/setup.py
git commit -m "Chore: py2app 설정 파일 추가"
```

---

## Task 3: entitlements.plist 작성

**Files:**
- Create: `05_pdf_agent/entitlements.plist`

- [ ] **Step 1: `entitlements.plist` 작성**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.network.client</key>
  <true/>
  <key>com.apple.security.network.server</key>
  <true/>
  <key>com.apple.security.files.user-selected.read-only</key>
  <true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
  <true/>
  <key>com.apple.security.cs.disable-library-validation</key>
  <true/>
</dict>
</plist>
```

- [ ] **Step 2: plist 유효성 확인**

```bash
plutil -lint 05_pdf_agent/entitlements.plist
```

Expected: `05_pdf_agent/entitlements.plist: OK`

- [ ] **Step 3: 커밋**

```bash
git add 05_pdf_agent/entitlements.plist
git commit -m "Chore: 코드서명 entitlements 추가"
```

---

## Task 4: 로컬 빌드 스크립트 작성

**Files:**
- Create: `05_pdf_agent/build.sh`

- [ ] **Step 1: `build.sh` 작성**

```bash
#!/usr/bin/env bash
# build.sh — PDFChatbot 로컬 빌드 스크립트
# 실행: cd 05_pdf_agent && ./build.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 버전 추출 (menubar_app.py의 __version__ = "x.x.x")
VERSION=$(grep '__version__' menubar_app.py | cut -d'"' -f2)
echo "=== PDFChatbot v${VERSION} 빌드 시작 ==="

echo "--- 1. 기존 빌드 정리 ---"
rm -rf build dist

echo "--- 2. py2app 빌드 ---"
# Poetry 가상환경의 Python 사용
PYTHON="$(cd .. && poetry env info --executable)"
$PYTHON setup.py py2app 2>&1

echo "--- 3. 코드 서명 (APPLE_CERT_NAME 환경변수가 있을 때만) ---"
if [ -n "$APPLE_CERT_NAME" ]; then
  echo "서명: $APPLE_CERT_NAME"
  codesign --deep --force --options runtime \
    --sign "$APPLE_CERT_NAME" \
    --entitlements entitlements.plist \
    "dist/PDFChatbot.app"
  echo "서명 완료"
else
  echo "APPLE_CERT_NAME 미설정 — 서명 건너뜀"
fi

echo "--- 4. DMG 생성 ---"
# icon.icns가 없으면 경고 후 계속
ICON_ARG=""
if [ -f "assets/icon.icns" ]; then
  ICON_ARG="--volicon assets/icon.icns"
fi

create-dmg \
  --volname "PDFChatbot" \
  $ICON_ARG \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "PDFChatbot.app" 175 190 \
  --app-drop-link 425 190 \
  "PDFChatbot-${VERSION}.dmg" \
  "dist/"

DMG_SIZE=$(du -sh "PDFChatbot-${VERSION}.dmg" | cut -f1)
echo "=== 빌드 완료: PDFChatbot-${VERSION}.dmg (${DMG_SIZE}) ==="
```

- [ ] **Step 2: 실행 권한 부여**

```bash
chmod +x 05_pdf_agent/build.sh
```

- [ ] **Step 3: `create-dmg` 설치 여부 확인**

```bash
which create-dmg || brew install create-dmg
which py2app || pip install py2app
```

- [ ] **Step 4: 커밋**

```bash
git add 05_pdf_agent/build.sh
git commit -m "Chore: 로컬 빌드 스크립트 추가"
```

---

## Task 5: 온보딩 API 엔드포인트 추가

**Files:**
- Create: `05_pdf_agent/api/routes/onboarding.py`
- Modify: `05_pdf_agent/api/server.py`

- [ ] **Step 1: `api/routes/onboarding.py` 작성**

```python
"""
api/routes/onboarding.py

온보딩 상태 확인 API.

GET  /api/onboarding   preferences.json 존재 여부 + onboarding_done 플래그 반환
POST /api/onboarding/complete   onboarding_done: true 저장
"""
from __future__ import annotations

from fastapi import APIRouter
from agent.llm_config import _PREFS_PATH, _load_prefs, _save_prefs

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("")
async def get_onboarding_status():
    """온보딩 완료 여부를 반환한다."""
    prefs = _load_prefs()
    done = prefs.get("onboarding_done", False)
    return {"onboarding_done": done}


@router.post("/complete")
async def complete_onboarding():
    """온보딩 완료를 저장한다."""
    prefs = _load_prefs()
    prefs["onboarding_done"] = True
    _save_prefs(prefs)
    return {"ok": True}
```

- [ ] **Step 2: `api/server.py`에 onboarding 라우터 등록**

`api/server.py`의 `from api.routes import agent, chat, document, events, session, settings` 줄을 수정:

```python
from api.routes import agent, chat, document, events, onboarding, session, settings
```

그리고 `app.include_router(settings.router)` 다음 줄에 추가:

```python
    app.include_router(onboarding.router)
```

- [ ] **Step 3: 동작 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python -c "
from 05_pdf_agent.api.routes.onboarding import router
print('routes:', [r.path for r in router.routes])
"
```

> 만약 import 경로 오류 시 아래로 대체:
> ```bash
> cd 05_pdf_agent && poetry run python -c "
> import sys; sys.path.insert(0, '.')
> from api.routes.onboarding import router
> print('OK:', [r.path for r in router.routes])
> "
> ```
> Expected: `OK: ['/api/onboarding', '/api/onboarding/complete']`

- [ ] **Step 4: 커밋**

```bash
git add 05_pdf_agent/api/routes/onboarding.py 05_pdf_agent/api/server.py
git commit -m "Feat: 온보딩 상태 API 추가"
```

---

## Task 6: 온보딩 마법사 UI 구현

**Files:**
- Create: `05_pdf_agent/ui/onboarding.js`
- Modify: `05_pdf_agent/ui/index.html`

- [ ] **Step 1: `ui/onboarding.js` 작성**

```javascript
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
  // 채팅 탭으로 전환
  switchTab("chat");
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
```

- [ ] **Step 2: `index.html`에 온보딩 pane 추가**

`index.html`의 `<script src="chat.js"></script>` 바로 위에 아래 HTML 블록을 추가:

```html
  <!-- 온보딩 마법사 탭 -->
  <div class="tab-content hidden" id="pane-onboarding">
    <div class="ob-area">

      <!-- Step 1: 환영 -->
      <div class="ob-step" id="ob-step-1">
        <div class="ob-icon">🤖</div>
        <h2 class="ob-title">PDFChatbot에 오신 것을 환영합니다</h2>
        <p class="ob-desc">논문 PDF를 열면 AI 챗봇이 자동으로 활성화됩니다.<br>먼저 사용할 AI 모델을 설정해주세요.</p>
        <button class="ob-btn-primary" onclick="obNext1()">시작하기</button>
      </div>

      <!-- Step 2: LLM 선택 -->
      <div class="ob-step hidden" id="ob-step-2">
        <h2 class="ob-title">AI 모델 선택</h2>
        <p class="ob-desc">사용할 AI 프로바이더를 선택해주세요.</p>
        <div class="ob-provider-btns">
          <button class="ob-provider-btn active" data-provider="ollama" onclick="obSelectProvider('ollama')">Ollama (로컬·무료)</button>
          <button class="ob-provider-btn" data-provider="openai" onclick="obSelectProvider('openai')">OpenAI</button>
          <button class="ob-provider-btn" data-provider="anthropic" onclick="obSelectProvider('anthropic')">Anthropic</button>
          <button class="ob-provider-btn" data-provider="google" onclick="obSelectProvider('google')">Google</button>
        </div>
        <div id="ob-ollama-guide" class="ob-guide">
          <p>터미널에서 아래 명령어를 실행해 Ollama를 설치하세요:</p>
          <code>brew install ollama<br>ollama pull qwen2.5:7b</code>
        </div>
        <div id="ob-apikey-section" class="hidden">
          <select class="ob-select" id="ob-model-select"></select>
          <input class="ob-input" id="ob-api-key" type="password" placeholder="API 키 입력 (sk-...)" />
        </div>
        <p class="ob-msg" id="ob-step2-msg"></p>
        <button class="ob-btn-primary" onclick="obNext2()">다음</button>
      </div>

      <!-- Step 3: 연결 테스트 -->
      <div class="ob-step hidden" id="ob-step-3">
        <h2 class="ob-title">연결 테스트</h2>
        <p class="ob-desc">설정한 AI 모델과 연결을 확인합니다.</p>
        <button class="ob-btn-secondary" onclick="obTestConnection()">연결 테스트</button>
        <p class="ob-msg" id="ob-test-msg"></p>
        <div class="ob-actions">
          <button class="ob-btn-text" onclick="obSkipTest()">건너뛰기</button>
          <button class="ob-btn-primary" id="ob-btn-next3" onclick="obNext3()" disabled>다음</button>
        </div>
      </div>

      <!-- Step 4: 감시 폴더 -->
      <div class="ob-step hidden" id="ob-step-4">
        <h2 class="ob-title">감시 폴더 설정 (선택)</h2>
        <p class="ob-desc">PDF를 열면 자동으로 챗봇이 활성화될 폴더를 지정하세요.</p>
        <button class="ob-btn-secondary" onclick="obSelectFolder()">폴더 선택</button>
        <p class="ob-folder-path hidden" id="ob-folder-path"></p>
        <div class="ob-actions">
          <button class="ob-btn-text" onclick="obSkipFolder()">나중에 설정</button>
          <button class="ob-btn-primary hidden" id="ob-folder-confirm" onclick="obConfirmFolder()">확인</button>
        </div>
      </div>

      <!-- Step 5: 완료 -->
      <div class="ob-step hidden" id="ob-step-5">
        <div class="ob-icon">✅</div>
        <h2 class="ob-title">설정 완료!</h2>
        <p class="ob-desc">이제 PDF를 열면 AI 챗봇이 자동으로 활성화됩니다.</p>
        <button class="ob-btn-primary" onclick="obDone()">시작하기</button>
      </div>

    </div>
  </div>
```

- [ ] **Step 3: `index.html`의 `<script>` 섹션에 `onboarding.js` 추가 및 자동 실행**

`<script src="chat.js"></script>` 블록에서 `</body>` 바로 위에 추가:

```html
  <script src="onboarding.js"></script>
  <script>
    // DOM 로드 완료 후 온보딩 상태 확인
    document.addEventListener("DOMContentLoaded", () => {
      // settings.js의 모델 옵션으로 온보딩 모델 드롭다운 채우기
      setTimeout(() => {
        const sel = document.getElementById("ob-model-select");
        if (sel && typeof _modelOptions !== "undefined") {
          (_modelOptions["ollama"] || []).forEach(m => {
            const opt = document.createElement("option");
            opt.value = m; opt.textContent = m;
            sel.appendChild(opt);
          });
        }
        checkOnboarding();
      }, 500);
    });
  </script>
```

- [ ] **Step 4: `style.css`에 온보딩 스타일 추가**

`style.css` 파일 맨 끝에 추가:

```css
/* ── 온보딩 마법사 ──────────────────────────────────────────── */
.ob-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 32px 24px;
  text-align: center;
}
.ob-step { width: 100%; }
.ob-icon { font-size: 48px; margin-bottom: 12px; }
.ob-title { font-size: 18px; font-weight: 600; color: #cdd6f4; margin-bottom: 8px; }
.ob-desc { font-size: 13px; color: #a6adc8; margin-bottom: 20px; line-height: 1.6; }
.ob-provider-btns { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-bottom: 16px; }
.ob-provider-btn {
  padding: 8px 16px; border-radius: 8px; border: 1px solid #45475a;
  background: #313244; color: #cdd6f4; cursor: pointer; font-size: 13px;
}
.ob-provider-btn.active { background: #89b4fa; color: #1e1e2e; border-color: #89b4fa; }
.ob-guide { background: #181825; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; text-align: left; }
.ob-guide p { font-size: 12px; color: #a6adc8; margin-bottom: 8px; }
.ob-guide code { font-size: 12px; color: #a6e3a1; display: block; line-height: 1.8; }
.ob-select, .ob-input {
  width: 100%; padding: 8px 12px; border-radius: 8px;
  border: 1px solid #45475a; background: #181825;
  color: #cdd6f4; font-size: 13px; margin-bottom: 10px;
}
.ob-msg { font-size: 12px; color: #f38ba8; min-height: 18px; margin-bottom: 8px; }
.ob-actions { display: flex; gap: 12px; justify-content: center; align-items: center; margin-top: 8px; }
.ob-btn-primary {
  padding: 10px 28px; border-radius: 8px; border: none;
  background: #89b4fa; color: #1e1e2e; font-weight: 600;
  cursor: pointer; font-size: 14px;
}
.ob-btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.ob-btn-secondary {
  padding: 8px 20px; border-radius: 8px; border: 1px solid #89b4fa;
  background: transparent; color: #89b4fa; cursor: pointer; font-size: 13px;
}
.ob-btn-text { background: none; border: none; color: #6c7086; cursor: pointer; font-size: 13px; }
.ob-folder-path { font-size: 12px; color: #a6e3a1; margin: 8px 0; }
```

- [ ] **Step 5: 브라우저에서 시각적 확인 (서버 실행 후)**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
# preferences.json 일시 삭제로 온보딩 트리거 테스트
mv ~/Library/Application\ Support/PDFChatbot/preferences.json \
   ~/Library/Application\ Support/PDFChatbot/preferences.json.bak 2>/dev/null || true
poetry run python 05_pdf_agent/menubar_app.py
```

앱 실행 후 채팅창에서 온보딩 마법사 5단계가 정상 표시되는지 확인.
테스트 후 백업 복원:
```bash
mv ~/Library/Application\ Support/PDFChatbot/preferences.json.bak \
   ~/Library/Application\ Support/PDFChatbot/preferences.json 2>/dev/null || true
```

- [ ] **Step 6: 커밋**

```bash
git add 05_pdf_agent/ui/onboarding.js \
        05_pdf_agent/ui/index.html \
        05_pdf_agent/ui/style.css
git commit -m "Feat: 첫 실행 온보딩 마법사 추가"
```

---

## Task 7: GitHub Actions 릴리스 워크플로우 작성

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: 워크플로우 디렉터리 생성**

```bash
mkdir -p /Users/gimgijae/Desktop/Paper/RAG/RAG_Study/.github/workflows
```

- [ ] **Step 2: `release.yml` 작성**

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build-and-release:
    runs-on: macos-14

    steps:
      - name: 소스 체크아웃
        uses: actions/checkout@v4

      - name: Python 3.11 설치
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Poetry 설치
        run: pip install poetry==2.3.2

      - name: 의존성 설치
        run: |
          poetry install --without dev
          pip install py2app
          brew install create-dmg

      - name: 버전 추출
        id: version
        run: |
          VERSION=$(grep '__version__' 05_pdf_agent/menubar_app.py | cut -d'"' -f2)
          echo "version=$VERSION" >> $GITHUB_OUTPUT
          echo "빌드 버전: $VERSION"

      - name: 코드 서명 인증서 복원 (선택)
        if: ${{ secrets.APPLE_CERT_P12 != '' }}
        run: |
          echo "${{ secrets.APPLE_CERT_P12 }}" | base64 --decode > cert.p12
          security create-keychain -p "" build.keychain
          security import cert.p12 -k build.keychain \
            -P "${{ secrets.APPLE_CERT_PASSWORD }}" \
            -A -t cert -f pkcs12
          security list-keychains -s build.keychain
          security default-keychain -s build.keychain
          security unlock-keychain -p "" build.keychain
          rm cert.p12

      - name: 빌드
        working-directory: 05_pdf_agent
        run: ./build.sh
        env:
          APPLE_CERT_NAME: ${{ secrets.APPLE_CERT_NAME }}

      - name: 공증 (선택)
        if: ${{ secrets.APPLE_ID != '' }}
        working-directory: 05_pdf_agent
        run: |
          VERSION="${{ steps.version.outputs.version }}"
          ditto -c -k --keepParent \
            "PDFChatbot-${VERSION}.dmg" PDFChatbot.zip
          xcrun notarytool submit PDFChatbot.zip \
            --apple-id "${{ secrets.APPLE_ID }}" \
            --team-id "${{ secrets.APPLE_TEAM_ID }}" \
            --password "${{ secrets.APPLE_APP_PASSWORD }}" \
            --wait
          xcrun stapler staple "PDFChatbot-${VERSION}.dmg"
          rm PDFChatbot.zip

      - name: pdfchatbot-releases 레포에 배포
        env:
          RELEASES_TOKEN: ${{ secrets.RELEASES_REPO_TOKEN }}
          RELEASES_REPO: ${{ secrets.RELEASES_REPO_NAME }}
          VERSION: ${{ steps.version.outputs.version }}
        run: |
          git clone "https://x-access-token:${RELEASES_TOKEN}@github.com/${RELEASES_REPO}.git" releases_repo
          cp "05_pdf_agent/PDFChatbot-${VERSION}.dmg" releases_repo/
          cd releases_repo
          # index.html의 DMG 링크와 버전 텍스트 업데이트
          sed -i '' "s/PDFChatbot-[0-9][0-9.]*\.dmg/PDFChatbot-${VERSION}.dmg/g" index.html
          sed -i '' "s/v[0-9][0-9.]*/v${VERSION}/g" index.html
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"
          git add "PDFChatbot-${VERSION}.dmg" index.html
          git commit -m "Release v${VERSION}"
          git push
```

- [ ] **Step 3: 워크플로우 YAML 유효성 확인**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('YAML OK')"
```

Expected: `YAML OK`

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/release.yml
git commit -m "Chore: GitHub Actions 릴리스 워크플로우 추가"
```

---

## Task 8: pdfchatbot-releases 레포 및 GitHub Pages 설정

> 이 Task는 GitHub 웹 UI와 로컬 터미널 작업을 병행한다.

- [ ] **Step 1: GitHub에서 Public 레포 `pdfchatbot-releases` 생성**

1. github.com → New repository
2. Repository name: `pdfchatbot-releases`
3. Public 선택
4. "Add a README file" 체크 해제
5. Create repository

- [ ] **Step 2: `index.html` 로컬에서 작성 후 push**

로컬에서 임시 디렉터리에 작성:

```bash
mkdir -p /tmp/pdfchatbot-releases
cd /tmp/pdfchatbot-releases
git init
git remote add origin https://github.com/YOUR_USERNAME/pdfchatbot-releases.git
```

`/tmp/pdfchatbot-releases/index.html` 내용:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDFChatbot — 논문 AI 챗봇</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #1e1e2e; color: #cdd6f4;
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh; padding: 24px;
    }
    .card {
      background: #313244; border-radius: 16px;
      padding: 48px 40px; max-width: 560px; width: 100%;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      text-align: center;
    }
    .icon { font-size: 64px; margin-bottom: 16px; }
    h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #cdd6f4; }
    .subtitle { font-size: 16px; color: #a6adc8; margin-bottom: 32px; }
    .btn-download {
      display: inline-block; padding: 14px 36px;
      background: #89b4fa; color: #1e1e2e;
      border-radius: 10px; font-size: 16px; font-weight: 700;
      text-decoration: none; margin-bottom: 8px;
    }
    .version { font-size: 12px; color: #6c7086; margin-bottom: 32px; }
    .section { text-align: left; margin-bottom: 24px; }
    .section h2 { font-size: 14px; font-weight: 600; color: #89b4fa; margin-bottom: 10px; }
    .section ul { padding-left: 18px; }
    .section li { font-size: 13px; color: #a6adc8; line-height: 2; }
    .steps { counter-reset: step; padding-left: 0; list-style: none; }
    .steps li { counter-increment: step; padding-left: 28px; position: relative; }
    .steps li::before {
      content: counter(step);
      position: absolute; left: 0;
      background: #89b4fa; color: #1e1e2e;
      width: 20px; height: 20px; border-radius: 50%;
      font-size: 11px; font-weight: 700;
      display: flex; align-items: center; justify-content: center;
      top: 2px;
    }
    .warn {
      background: #1e1e2e; border-radius: 8px;
      padding: 12px 16px; font-size: 12px;
      color: #f9e2af; border-left: 3px solid #f9e2af;
      text-align: left; margin-top: 16px;
    }
    code {
      background: #1e1e2e; padding: 2px 8px;
      border-radius: 4px; font-size: 12px; color: #a6e3a1;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">🤖</div>
    <h1>PDFChatbot</h1>
    <p class="subtitle">논문 PDF를 열면 AI 챗봇이 자동으로 활성화되는 macOS 메뉴바 앱</p>

    <a class="btn-download" href="PDFChatbot-1.0.0.dmg" download>
      DMG 다운로드
    </a>
    <p class="version">최신 버전: v1.0.0 · macOS 13 Ventura 이상</p>

    <div class="section">
      <h2>시스템 요구사항</h2>
      <ul>
        <li>macOS 13 Ventura 이상</li>
        <li>Ollama (로컬 모드) 또는 OpenAI / Anthropic / Google API 키</li>
      </ul>
    </div>

    <div class="section">
      <h2>설치 방법</h2>
      <ol class="steps">
        <li>DMG 파일을 다운로드합니다</li>
        <li>DMG를 마운트하고 PDFChatbot을 Applications 폴더로 드래그합니다</li>
        <li>Applications에서 PDFChatbot을 <strong>Control+클릭 → 열기</strong>로 실행합니다 (최초 1회)</li>
        <li>메뉴바 🤖 아이콘을 클릭해 설정을 완료합니다</li>
      </ol>
    </div>

    <div class="section">
      <h2>Ollama 로컬 모드 설치 (무료)</h2>
      <ul>
        <li><code>brew install ollama</code></li>
        <li><code>ollama pull qwen2.5:7b</code></li>
      </ul>
    </div>

    <div class="warn">
      ⚠️ <strong>"확인되지 않은 개발자" 경고가 뜨는 경우:</strong><br>
      Applications 폴더에서 PDFChatbot을 <strong>Control+클릭 → 열기 → 열기</strong> 클릭
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 3: 레포에 push**

```bash
cd /tmp/pdfchatbot-releases
git add index.html
git commit -m "Init: 랜딩 페이지 추가"
git branch -M main
git push -u origin main
```

- [ ] **Step 4: GitHub Pages 활성화**

GitHub 레포 → Settings → Pages → Source: `Deploy from a branch` → Branch: `main` / `/ (root)` → Save

약 1분 후 `https://YOUR_USERNAME.github.io/pdfchatbot-releases/` 접속 확인.

- [ ] **Step 5: GitHub Secrets 등록**

GitHub RAG_Study 레포 → Settings → Secrets and variables → Actions → New repository secret:

| Name | Value |
|---|---|
| `RELEASES_REPO_TOKEN` | GitHub PAT (Settings → Developer settings → Personal access tokens → Tokens classic → `repo` scope) |
| `RELEASES_REPO_NAME` | `YOUR_USERNAME/pdfchatbot-releases` |

---

## Task 9: 전체 파이프라인 검증

- [ ] **Step 1: 로컬 빌드 테스트 (py2app 설치 확인)**

```bash
pip install py2app create-dmg
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study/05_pdf_agent
./build.sh 2>&1 | tail -20
```

Expected 마지막 줄: `=== 빌드 완료: PDFChatbot-1.0.0.dmg (...) ===`

- [ ] **Step 2: DMG 마운트 및 앱 실행 테스트**

```bash
open PDFChatbot-1.0.0.dmg
# Finder에서 PDFChatbot.app을 Applications로 드래그 후
open /Applications/PDFChatbot.app
```

메뉴바에 🤖 아이콘이 뜨고 채팅창이 열리는지 확인.

- [ ] **Step 3: 온보딩 마법사 E2E 테스트**

```bash
# preferences.json 삭제해 온보딩 강제 트리거
rm ~/Library/Application\ Support/PDFChatbot/preferences.json
open /Applications/PDFChatbot.app
```

5단계 마법사 전체 진행 후 `preferences.json`에 `onboarding_done: true` 확인:
```bash
cat ~/Library/Application\ Support/PDFChatbot/preferences.json | python3 -m json.tool
```

- [ ] **Step 4: GitHub Actions 트리거 테스트**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 탭에서 `Release` 워크플로우 실행 확인.
완료 후 `https://YOUR_USERNAME.github.io/pdfchatbot-releases/` 에서 v1.0.0 DMG 다운로드 버튼 확인.

- [ ] **Step 5: 최종 커밋**

```bash
git add .
git commit -m "Chore: 배포 파이프라인 검증 완료"
```

---

## 자체 검토 결과

**스펙 커버리지:**
- ✅ `__version__` 상수 → Task 1
- ✅ `setup.py` py2app 설정 → Task 2
- ✅ `entitlements.plist` → Task 3
- ✅ `build.sh` 로컬 빌드 → Task 4
- ✅ 온보딩 API → Task 5
- ✅ 온보딩 UI → Task 6
- ✅ GitHub Actions 워크플로우 → Task 7
- ✅ pdfchatbot-releases 레포 + GitHub Pages → Task 8
- ✅ E2E 파이프라인 검증 → Task 9

**주의사항:**
- Task 8 Step 2의 `index.html`에서 `YOUR_USERNAME`을 실제 GitHub 계정명으로 교체 필요
- Task 7의 `release.yml`에서 `sed -i ''` 는 macOS Actions 러너(macos-14)에서만 동작. Linux 러너로 바꿀 경우 `sed -i` (따옴표 없음)로 수정 필요
- `assets/icon.icns`가 없으면 `build.sh`는 아이콘 없이 진행함 (경고만 출력)
