"""
Day 3-4: RAG 파이프라인 핵심
01. Document Loaders - 다양한 소스에서 문서 로딩

학습 목표:
- Document 객체의 구조 이해 (page_content + metadata)
- PyPDFLoader로 PDF 문서 로딩
- WebBaseLoader로 웹 페이지 크롤링
- 여러 Loader의 특징과 사용법 비교

RAG 파이프라인 첫 번째 단계:
  ★[문서 로딩]★ → 텍스트 분할 → 임베딩 → 벡터 저장 → 검색 → 답변
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. Document 객체란?
# ============================================================
print("=" * 50)
print("1. Document 객체 구조 이해")
print("=" * 50)

from langchain_core.documents import Document

# Document는 LangChain에서 문서를 표현하는 기본 단위
# page_content: 실제 텍스트 내용
# metadata: 출처, 페이지 번호 등 부가 정보
doc = Document(
    page_content="RAG는 Retrieval-Augmented Generation의 약자입니다.",
    metadata={"source": "manual", "topic": "RAG", "page": 1}
)

print(f"내용: {doc.page_content}")
print(f"메타데이터: {doc.metadata}")
print(f"타입: {type(doc)}")

# ============================================================
# 2. PyPDFLoader - PDF 문서 로딩
# ============================================================
print("\n" + "=" * 50)
print("2. PyPDFLoader - PDF 로딩")
print("=" * 50)

from langchain_community.document_loaders import PyPDFLoader

# PDF 파일 경로 (predicting_music.pdf)
pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)

print(f"PDF 경로: {pdf_path}")
print(f"파일 존재: {os.path.exists(pdf_path)}")

# PDF 로딩 - 페이지별로 Document 객체가 생성됨
loader = PyPDFLoader(pdf_path)
pages = loader.load()

print(f"\n총 페이지 수: {len(pages)}")
print(f"각 페이지 타입: {type(pages[0])}")

# 첫 번째 페이지 확인
print(f"\n--- 1페이지 메타데이터 ---")
print(f"메타데이터: {pages[0].metadata}")

print(f"\n--- 1페이지 내용 (앞 500자) ---")
print(pages[0].page_content[:500])

# 모든 페이지의 메타데이터 확인
print(f"\n--- 전체 페이지 메타데이터 ---")
for i, page in enumerate(pages):
    content_length = len(page.page_content)
    print(f"  페이지 {i+1}: {content_length}자 | metadata: {page.metadata}")

# ============================================================
# 3. PyPDFLoader - lazy_load() vs load()
# ============================================================
print("\n" + "=" * 50)
print("3. lazy_load() vs load()")
print("=" * 50)

# load(): 모든 문서를 한 번에 메모리에 로드 (소규모 문서에 적합)
# lazy_load(): 제너레이터로 하나씩 로드 (대용량 문서에 적합)

loader2 = PyPDFLoader(pdf_path)

print("lazy_load() 사용 - 메모리 효율적:")
for i, page in enumerate(loader2.lazy_load()):
    print(f"  페이지 {i+1} 로드됨: {len(page.page_content)}자")
    if i >= 2:  # 처음 3페이지만 출력
        print(f"  ... (나머지 {len(pages) - 3}페이지 생략)")
        break

print("\n💡 Tip: 대용량 PDF(100페이지+)에서는 lazy_load() 권장")

# ============================================================
# 4. WebBaseLoader - 웹 페이지 크롤링
# ============================================================
print("\n" + "=" * 50)
print("4. WebBaseLoader - 웹 페이지 로딩")
print("=" * 50)

from langchain_community.document_loaders import WebBaseLoader

# Spotify Research 블로그 로딩
url = "https://research.atspotify.com/"
print(f"로딩 URL: {url}")

web_loader = WebBaseLoader(url)
web_docs = web_loader.load()

print(f"\n로드된 문서 수: {len(web_docs)}")
print(f"메타데이터: {web_docs[0].metadata}")

# 웹 페이지 내용 확인 (앞 800자)
print(f"\n--- 웹 페이지 내용 (앞 800자) ---")
print(web_docs[0].page_content[:800])

# 전체 텍스트 길이
total_length = len(web_docs[0].page_content)
print(f"\n전체 텍스트 길이: {total_length}자")

# ============================================================
# 5. WebBaseLoader - 여러 URL 동시 로딩
# ============================================================
print("\n" + "=" * 50)
print("5. 여러 URL 동시 로딩")
print("=" * 50)

urls = [
    "https://research.atspotify.com/",
    "https://research.atspotify.com/blog/",
]

multi_loader = WebBaseLoader(urls)
multi_docs = multi_loader.load()

print(f"로드된 문서 수: {len(multi_docs)}")
for i, doc in enumerate(multi_docs):
    print(f"  문서 {i+1}: {doc.metadata.get('source', 'N/A')}")
    print(f"    길이: {len(doc.page_content)}자")
    print(f"    제목: {doc.metadata.get('title', 'N/A')[:60]}")

# ============================================================
# 6. TextLoader - 텍스트 파일 로딩
# ============================================================
print("\n" + "=" * 50)
print("6. TextLoader - 텍스트 파일 로딩")
print("=" * 50)

from langchain_community.document_loaders import TextLoader

# 테스트용 텍스트 파일 생성
sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
os.makedirs(sample_dir, exist_ok=True)

sample_text_path = os.path.join(sample_dir, "sample.txt")
with open(sample_text_path, "w", encoding="utf-8") as f:
    f.write("""RAG (Retrieval-Augmented Generation) 개요

RAG는 대규모 언어 모델(LLM)의 한계를 보완하는 기술입니다.
LLM은 학습 데이터에 포함되지 않은 최신 정보나 특정 도메인 지식에 대해
정확한 답변을 제공하기 어렵습니다.

RAG는 이 문제를 해결하기 위해:
1. 외부 지식 소스에서 관련 문서를 검색(Retrieval)하고
2. 검색된 문서를 컨텍스트로 활용하여
3. LLM이 더 정확하고 근거 있는 답변을 생성(Generation)하도록 합니다.

이를 통해 환각(Hallucination)을 줄이고,
출처를 명시한 신뢰할 수 있는 답변을 제공할 수 있습니다.
""")

text_loader = TextLoader(sample_text_path, encoding="utf-8")
text_docs = text_loader.load()

print(f"로드된 문서 수: {len(text_docs)}")
print(f"메타데이터: {text_docs[0].metadata}")
print(f"\n내용:\n{text_docs[0].page_content}")

# ============================================================
# 7. DirectoryLoader - 폴더 내 여러 파일 로딩
# ============================================================
print("\n" + "=" * 50)
print("7. DirectoryLoader - 폴더 일괄 로딩")
print("=" * 50)

from langchain_community.document_loaders import DirectoryLoader

# sample_data 폴더에 추가 파일 생성
with open(os.path.join(sample_dir, "music_tech.txt"), "w", encoding="utf-8") as f:
    f.write("""음악 기술과 AI

최근 AI 기술은 음악 산업에 큰 변화를 가져오고 있습니다.
Spotify, Apple Music 등의 스트리밍 플랫폼은 추천 알고리즘에
머신러닝을 적극 활용하고 있으며, 사용자의 청취 패턴을 분석하여
개인화된 플레이리스트를 생성합니다.
""")

with open(os.path.join(sample_dir, "embedding.txt"), "w", encoding="utf-8") as f:
    f.write("""임베딩(Embedding)이란?

임베딩은 텍스트, 이미지 등의 데이터를 고정 길이의 벡터(숫자 배열)로 변환하는 기술입니다.
의미적으로 유사한 텍스트는 벡터 공간에서 가까운 위치에 배치됩니다.

예시:
- "고양이"와 "강아지"의 임베딩 벡터는 가까움 (둘 다 동물)
- "고양이"와 "자동차"의 임베딩 벡터는 먼 거리 (관련 없음)

RAG에서 임베딩은 문서 검색의 핵심 기술로 사용됩니다.
""")

# 특정 확장자만 로딩 (*.txt)
dir_loader = DirectoryLoader(
    sample_dir,
    glob="*.txt",             # .txt 파일만 로딩
    loader_cls=TextLoader,     # 각 파일에 사용할 Loader
    loader_kwargs={"encoding": "utf-8"}
)

dir_docs = dir_loader.load()

print(f"로드된 문서 수: {len(dir_docs)}")
for doc in dir_docs:
    filename = os.path.basename(doc.metadata["source"])
    print(f"  📄 {filename}: {len(doc.page_content)}자")

# ============================================================
# 8. 각 Loader 비교 정리
# ============================================================
print("\n" + "=" * 50)
print("8. Document Loader 비교 정리")
print("=" * 50)

print("""
┌──────────────────┬──────────────────┬─────────────────────────┐
│ Loader           │ 대상             │ 특징                    │
├──────────────────┼──────────────────┼─────────────────────────┤
│ PyPDFLoader      │ PDF 파일         │ 페이지별 Document 생성  │
│ TextLoader       │ 텍스트 파일      │ 파일 전체가 1개 Document│
│ WebBaseLoader    │ 웹 페이지        │ HTML → 텍스트 변환      │
│ DirectoryLoader  │ 폴더 내 파일들   │ glob 패턴으로 필터링    │
│ CSVLoader        │ CSV 파일         │ 행별 Document 생성      │
│ Docx2txtLoader   │ Word 문서        │ .docx 파일 로딩         │
│ UnstructuredLoader│ 다양한 형식     │ 범용 (느리지만 강력)    │
└──────────────────┴──────────────────┴─────────────────────────┘
""")

# ============================================================
# 9. 실전: PDF 내용 요약해보기 (Loader + LLM 연결)
# ============================================================
print("=" * 50)
print("9. 실전: PDF 내용을 LLM에게 전달하기")
print("=" * 50)

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2:3b", temperature=0)

# PDF 첫 페이지 내용을 LLM에게 전달
prompt = ChatPromptTemplate.from_template("""
다음 논문의 내용을 한국어로 3줄 요약해주세요.

논문 내용:
{content}

요약:
""")

chain = prompt | llm | StrOutputParser()

# 첫 페이지 내용으로 요약 요청
summary = chain.invoke({"content": pages[0].page_content[:2000]})
print(f"📄 논문: predicting_music.pdf")
print(f"\n요약 결과:\n{summary}")

print("\n" + "=" * 50)
print("✅ Document Loaders 실습 완료!")
print("=" * 50)
print("\n📌 핵심 정리:")
print("  - Document = page_content(텍스트) + metadata(메타 정보)")
print("  - PyPDFLoader: PDF를 페이지별로 분할 로딩")
print("  - WebBaseLoader: 웹 페이지를 텍스트로 변환")
print("  - TextLoader: 텍스트 파일 전체를 하나의 Document로 로딩")
print("  - DirectoryLoader: 폴더 내 파일을 일괄 로딩")
print("  - load() vs lazy_load(): 메모리 전략에 따라 선택")
print("\n🔜 다음 실습: 02_text_splitters.py (텍스트 분할)")
