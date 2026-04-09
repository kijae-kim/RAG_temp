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
