"""
setup.py — py2app 빌드 설정

실행:
  cd 05_pdf_agent
  python setup.py py2app
"""
import sys
import os
sys.setrecursionlimit(10000)

# setup.py가 어느 디렉터리에서 실행되든 05_pdf_agent/ 기준 절대 경로 사용
_HERE = os.path.dirname(os.path.abspath(__file__))

from setuptools import setup

APP = [os.path.join(_HERE, 'menubar_app.py')]

def _p(*parts):
    """_HERE 기준 절대 경로 반환"""
    return os.path.join(_HERE, *parts)

# 04_mini_project 루트 (rag_engine.py 위치)
_MINI_PROJECT = os.path.join(_HERE, '..', '04_mini_project')

DATA_FILES = [
    # rag_engine.py를 Resources/ 루트에 포함 (py2app sys.path에 포함됨)
    ('', [os.path.join(_MINI_PROJECT, 'rag_engine.py')]),
    ('ui', [
        _p('ui', 'index.html'),
        _p('ui', 'chat.js'),
        _p('ui', 'style.css'),
        _p('ui', 'settings.js'),
        _p('ui', 'analysis.js'),
        _p('ui', 'onboarding.js'),
        _p('ui', 'launcher.js'),
        _p('ui', 'floating_button.html'),
    ]),
    ('agent', [
        _p('agent', '__init__.py'),
        _p('agent', 'llm_config.py'),
        _p('agent', 'tools.py'),
        _p('agent', 'paper_agent.py'),
    ]),
    ('api', [
        _p('api', '__init__.py'),
        _p('api', 'server.py'),
        _p('api', 'engine_state.py'),
    ]),
    ('api/routes', [
        _p('api', 'routes', '__init__.py'),
        _p('api', 'routes', 'chat.py'),
        _p('api', 'routes', 'document.py'),
        _p('api', 'routes', 'settings.py'),
        _p('api', 'routes', 'onboarding.py'),
        _p('api', 'routes', 'agent.py'),
        _p('api', 'routes', 'events.py'),
        _p('api', 'routes', 'session.py'),
    ]),
    ('session', [
        _p('session', '__init__.py'),
        _p('session', 'session_manager.py'),
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': os.path.join(_HERE, 'assets', 'icon.icns'),
    'packages': [
        # imp.find_module 호환 패키지만 명시
        # (네임스페이스 패키지는 py2app이 자동 탐지)
        'rumps',
        'uvicorn',
        'fastapi',
        'starlette',
        'pydantic',
        'requests',
        'faiss',
        'rank_bm25',
        'pypdf',
        'fitz',
        'torch',
        'transformers',
        'sentence_transformers',
        'huggingface_hub',
        'tokenizers',
        'safetensors',
        'numpy',
        'scipy',
        'tqdm',
    ],
    # langchain_*, langgraph 등 네임스페이스 패키지는 includes로 강제 포함
    'includes': [
        'langchain_core',
        'langchain_ollama',
        'langchain_openai',
        'langchain_anthropic',
        'langchain_google_genai',
        'langchain_classic',
        'langchain_community',
        'langchain_huggingface',
        'langgraph',
        'sentence_transformers',
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
