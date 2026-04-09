# PDFChatbot 배포 파이프라인 설계

- **날짜:** 2026-04-09
- **상태:** 승인됨
- **대상:** 소수(10~50명) 배포, 기술 수준 혼합

---

## 1. 목표

- Private 소스 레포를 유지하면서 소수 사용자에게 DMG를 배포한다.
- `git tag` 하나로 빌드 → 서명 → 랜딩 페이지 업데이트까지 자동화한다.
- 비개발자도 URL 접속 → DMG 다운로드 → 더블클릭 설치로 완료할 수 있다.
- 첫 실행 시 온보딩 마법사로 LLM 설정을 안내한다.

---

## 2. 레포 구조

| 레포 | 공개 여부 | 용도 |
|---|---|---|
| `RAG_Study` | Private | 소스 코드, GitHub Actions 워크플로우 |
| `pdfchatbot-releases` | Public | GitHub Pages 랜딩 페이지 + DMG 파일 호스팅 |

---

## 3. 전체 배포 흐름

```
개발자
  git tag v1.x.x && git push origin v1.x.x
        ↓
GitHub Actions (RAG_Study, macos-14 러너)
  1. checkout + Python 3.11 + Poetry 설치
  2. poetry install --without dev
  3. pip install py2app create-dmg
  4. ./05_pdf_agent/build.sh → PDFChatbot-x.x.x.dmg 생성
  5. codesign (APPLE_CERT_P12 Secret 있으면 서명, 없으면 skip)
  6. notarize (APPLE_ID Secret 있으면 공증, 없으면 skip)
  7. pdfchatbot-releases 레포에 DMG 커밋 (RELEASES_REPO_TOKEN 사용)
  8. index.html 버전 문자열 업데이트
        ↓
GitHub Pages (pdfchatbot-releases)
  랜딩 페이지 자동 갱신
        ↓
사용자
  URL 접속 → DMG 다운로드 → 설치
```

---

## 4. 로컬 빌드 스크립트 (`05_pdf_agent/build.sh`)

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

VERSION=$(grep '__version__' menubar_app.py | cut -d'"' -f2)

echo "=== 1. 정리 ==="
rm -rf build dist

echo "=== 2. py2app 빌드 ==="
PYTHON="$(poetry env info --executable)"
$PYTHON setup.py py2app

echo "=== 3. 서명 (Developer ID 있으면) ==="
if [ -n "$APPLE_CERT_NAME" ]; then
  codesign --deep --force --options runtime \
    --sign "$APPLE_CERT_NAME" \
    --entitlements entitlements.plist \
    dist/PDFChatbot.app
fi

echo "=== 4. DMG 생성 ==="
create-dmg \
  --volname "PDFChatbot" \
  --volicon "assets/icon.icns" \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "PDFChatbot.app" 175 190 \
  --app-drop-link 425 190 \
  "PDFChatbot-${VERSION}.dmg" \
  "dist/"

echo "완료: PDFChatbot-${VERSION}.dmg ($(du -sh PDFChatbot-${VERSION}.dmg | cut -f1))"
```

---

## 5. GitHub Actions 워크플로우 (`.github/workflows/release.yml`)

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Python 3.11 설치
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Poetry 설치
        run: pip install poetry

      - name: 의존성 설치
        run: |
          poetry install --without dev
          pip install py2app create-dmg

      - name: 빌드
        run: ./05_pdf_agent/build.sh
        env:
          APPLE_CERT_NAME: ${{ secrets.APPLE_CERT_NAME }}

      - name: 코드 서명 인증서 복원 (선택)
        if: secrets.APPLE_CERT_P12 != ''
        run: |
          echo "${{ secrets.APPLE_CERT_P12 }}" | base64 --decode > cert.p12
          security import cert.p12 -P "${{ secrets.APPLE_CERT_PASSWORD }}" \
            -A -t cert -f pkcs12
          rm cert.p12

      - name: 공증 (선택)
        if: secrets.APPLE_ID != ''
        run: |
          VERSION=$(grep '__version__' 05_pdf_agent/menubar_app.py | cut -d'"' -f2)
          ditto -c -k --keepParent \
            05_pdf_agent/PDFChatbot-${VERSION}.dmg PDFChatbot.zip
          xcrun notarytool submit PDFChatbot.zip \
            --apple-id "${{ secrets.APPLE_ID }}" \
            --team-id "${{ secrets.APPLE_TEAM_ID }}" \
            --password "${{ secrets.APPLE_APP_PASSWORD }}" \
            --wait
          xcrun stapler staple 05_pdf_agent/PDFChatbot-${VERSION}.dmg

      - name: pdfchatbot-releases에 배포
        run: |
          VERSION=$(grep '__version__' 05_pdf_agent/menubar_app.py | cut -d'"' -f2)
          git clone https://x-access-token:${{ secrets.RELEASES_REPO_TOKEN }}@github.com/USERNAME/pdfchatbot-releases.git releases_repo
          cp 05_pdf_agent/PDFChatbot-${VERSION}.dmg releases_repo/
          cd releases_repo
          sed -i '' "s/PDFChatbot-[0-9.]*.dmg/PDFChatbot-${VERSION}.dmg/g" index.html
          sed -i '' "s/v[0-9.]*/v${VERSION}/g" index.html
          git config user.email "actions@github.com"
          git config user.name "GitHub Actions"
          git add .
          git commit -m "Release v${VERSION}"
          git push
```

---

## 6. GitHub Secrets 목록

| Secret | 필수 여부 | 용도 |
|---|---|---|
| `RELEASES_REPO_TOKEN` | 필수 | pdfchatbot-releases 레포 push용 PAT |
| `APPLE_CERT_NAME` | 선택 | Developer ID 인증서 이름 |
| `APPLE_CERT_P12` | 선택 | 인증서 파일 (base64 인코딩) |
| `APPLE_CERT_PASSWORD` | 선택 | 인증서 비밀번호 |
| `APPLE_ID` | 선택 | 공증용 Apple ID 이메일 |
| `APPLE_TEAM_ID` | 선택 | Apple Developer Team ID |
| `APPLE_APP_PASSWORD` | 선택 | Apple ID 앱 전용 암호 |

---

## 7. GitHub Pages 랜딩 페이지 (`pdfchatbot-releases/index.html`)

**구성 요소:**
- 앱 이름 + 한 줄 설명
- DMG 다운로드 버튼 (버전 자동 갱신)
- 시스템 요구사항 (macOS 13+, Ollama 또는 API 키)
- 설치 3단계 (DMG 마운트 → Applications 드래그 → Control+클릭 열기)
- Ollama 설치 명령어 코드 블록

---

## 8. 첫 실행 온보딩 마법사

**트리거 조건:** `~/Library/Application Support/PDFChatbot/preferences.json`이 없거나 `onboarding_done` 키가 `false`

**마법사 5단계:**

| 단계 | 화면 내용 | 완료 조건 |
|---|---|---|
| 1. 환영 | 앱 소개, [시작하기] 버튼 | 버튼 클릭 |
| 2. LLM 선택 | Ollama / OpenAI / Anthropic / Google 선택 + API 키 입력 | 프로바이더 선택 |
| 3. 연결 테스트 | [테스트] 버튼 → 성공/실패 표시 | 연결 성공 (또는 skip) |
| 4. 감시 폴더 | [폴더 선택] 또는 [나중에] | 선택 또는 skip |
| 5. 완료 | 완료 메시지, 채팅 탭으로 전환 | 자동 |

**구현:**
- `ui/onboarding.js`: 마법사 상태 관리, 단계 전환
- `index.html`: `#pane-onboarding` div 추가
- `menubar_app.py` 또는 `api/engine_state.py`: 앱 시작 시 onboarding 상태 확인 후 프론트엔드에 플래그 전달

---

## 9. 비서명 배포 시 사용자 안내 문구

Apple Developer 가입 전까지 DMG에 서명이 없어 첫 실행 시 경고가 표시된다.
랜딩 페이지에 아래 안내를 포함한다:

> **처음 실행 시 "확인되지 않은 개발자" 경고가 뜨는 경우:**
> Applications 폴더에서 PDFChatbot을 **Control+클릭** → **열기** → 열기 확인

---

## 10. 구현 순서

1. `menubar_app.py`에 `__version__` 상수 추가
2. `05_pdf_agent/setup.py` 작성 (py2app 설정)
3. `05_pdf_agent/assets/icon.icns` 생성
4. `05_pdf_agent/build.sh` 작성 + 로컬 빌드 테스트
5. `pdfchatbot-releases` Public 레포 생성 + GitHub Pages 활성화
6. `pdfchatbot-releases/index.html` 랜딩 페이지 작성
7. `.github/workflows/release.yml` 작성
8. GitHub Secrets 등록 (`RELEASES_REPO_TOKEN` 필수)
9. 온보딩 마법사 구현 (`ui/onboarding.js`)
10. `git tag v1.0.0` → 전체 파이프라인 검증
