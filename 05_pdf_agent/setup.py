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
