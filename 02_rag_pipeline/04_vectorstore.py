"""
Day 3-4: RAG 파이프라인 핵심
04. VectorStore - 벡터 저장 & 유사도 검색

학습 목표:
- ChromaDB로 벡터 저장/검색/영구 보관
- FAISS로 고속 유사도 검색
- similarity_search vs MMR 검색 비교
- 메타데이터 필터링
- Retriever 인터페이스 활용

RAG 파이프라인 네 번째 단계:
  문서 로딩 → 텍스트 분할 → 임베딩 → ★[벡터 저장 & 검색]★ → 답변
"""

import os
import shutil
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# ============================================================
# 0. 준비: PDF 로딩 + 분할 + 임베딩 모델 (이전 실습 복습)
# ============================================================
print("=" * 50)
print("0. 데이터 준비 (이전 실습 복습)")
print("=" * 50)

pdf_path = os.path.join(os.path.dirname(__file__), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)

# PDF 로딩 → 텍스트 분할
pages = PyPDFLoader(pdf_path).load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(pages)

# 임베딩 모델
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

print(f"PDF: {len(pages)}페이지 → {len(docs)}개 청크")
print(f"임베딩 모델: all-MiniLM-L6-v2 (384차원)")

print("""
지금까지의 흐름:
  [PDF] → PyPDFLoader → [12 Documents]
       → RecursiveCharacterTextSplitter → [89 청크]
       → HuggingFaceEmbeddings → [89개의 384차원 벡터]
       → ★ VectorStore에 저장 ★  ← 오늘 배울 내용!
""")

# ============================================================
# 1. ChromaDB - 기본 사용법
# ============================================================
print("=" * 50)
print("1. ChromaDB - 기본 사용법")
print("=" * 50)

from langchain_community.vectorstores import Chroma

# 문서 + 임베딩을 ChromaDB에 저장 (인메모리)
vectorstore = Chroma.from_documents(
    documents=docs,      # 분할된 문서 청크
    embedding=embeddings, # 임베딩 모델
    collection_name="music_paper",  # 컬렉션 이름
)

print(f"ChromaDB 저장 완료!")
print(f"저장된 문서 수: {vectorstore._collection.count()}")

# ============================================================
# 2. similarity_search - 유사도 검색
# ============================================================
print("\n" + "=" * 50)
print("2. similarity_search (유사도 검색)")
print("=" * 50)

# 질문과 가장 유사한 청크 검색
query = "How does CNN predict music popularity?"
results = vectorstore.similarity_search(query, k=3)

print(f"쿼리: \"{query}\"")
print(f"검색 결과: {len(results)}개\n")

for i, doc in enumerate(results):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"--- 결과 {i+1} (페이지 {page}) ---")
    print(doc.page_content[:200])
    print()

# ============================================================
# 3. similarity_search_with_score - 점수 포함 검색
# ============================================================
print("=" * 50)
print("3. similarity_search_with_score (점수 포함)")
print("=" * 50)

# 유사도 점수까지 함께 반환
results_with_score = vectorstore.similarity_search_with_score(query, k=5)

print(f"쿼리: \"{query}\"\n")
print(f"{'순위':<4} {'점수':>8} {'페이지':>6}  내용")
print("-" * 70)

for i, (doc, score) in enumerate(results_with_score, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    content = doc.page_content[:60].replace("\n", " ")
    # ChromaDB는 거리(distance)를 반환 → 낮을수록 유사
    print(f"  {i:<3} {score:>8.4f} {'p'+str(page):>5}  {content}...")

print("\n💡 ChromaDB의 score = L2 거리 (낮을수록 유사)")
print("   → 0에 가까울수록 질문과 의미가 비슷한 청크")

# ============================================================
# 4. MMR 검색 (Maximum Marginal Relevance)
# ============================================================
print("\n" + "=" * 50)
print("4. MMR 검색 (다양성 + 관련성)")
print("=" * 50)

print("""
일반 검색 vs MMR 검색:
  similarity_search → 가장 유사한 것만 반환 (중복 내용 가능)
  MMR               → 유사하면서도 서로 다양한 결과 반환

  fetch_k: 후보 문서 수 (넉넉하게)
  lambda_mult: 다양성 조절 (0=최대 다양성, 1=최대 유사도)
""")

# 일반 검색
sim_results = vectorstore.similarity_search(query, k=4)

# MMR 검색
mmr_results = vectorstore.max_marginal_relevance_search(
    query,
    k=4,              # 반환할 문서 수
    fetch_k=20,        # 후보 문서 수
    lambda_mult=0.5,   # 다양성-유사도 균형 (0.5 = 균형)
)

print("📌 일반 검색 결과 (similarity):")
for i, doc in enumerate(sim_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

print(f"\n📌 MMR 검색 결과 (다양성 고려):")
for i, doc in enumerate(mmr_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# 페이지 분포 비교
sim_pages = [int(d.metadata["page"]) + 1 for d in sim_results]
mmr_pages = [int(d.metadata["page"]) + 1 for d in mmr_results]
print(f"\n  일반 검색 페이지: {sim_pages} (중복 가능)")
print(f"  MMR 검색 페이지:  {mmr_pages} (더 다양한 페이지)")

# ============================================================
# 5. 메타데이터 필터링
# ============================================================
print("\n" + "=" * 50)
print("5. 메타데이터 필터링")
print("=" * 50)

# 특정 페이지에서만 검색
filtered_results = vectorstore.similarity_search(
    query,
    k=3,
    filter={"page": 0},  # 1페이지(인덱스 0)에서만 검색
)

print(f"쿼리: \"{query}\"")
print(f"필터: page=0 (1페이지만)\n")

for i, doc in enumerate(filtered_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:100].replace(chr(10), ' ')}...")

# 여러 조건 필터링
print(f"\n💡 필터 예시:")
print(f'  filter={{"page": 0}}                  → 1페이지만')
print(f'  filter={{"page": {{"$gte": 5}}}}          → 6페이지 이후')
print(f'  filter={{"page": {{"$in": [0, 1, 2]}}}}   → 1~3페이지')

# ============================================================
# 6. ChromaDB 영구 저장 (Persistent)
# ============================================================
print("\n" + "=" * 50)
print("6. ChromaDB 영구 저장")
print("=" * 50)

persist_dir = os.path.join(os.path.dirname(__file__), "chroma_db")

# 기존 DB 정리 (재실행 시)
if os.path.exists(persist_dir):
    shutil.rmtree(persist_dir)

# 영구 저장소에 저장
persistent_db = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    persist_directory=persist_dir,  # 이 경로에 파일로 저장
    collection_name="music_paper_persistent",
)

print(f"저장 경로: {persist_dir}")
print(f"저장된 문서 수: {persistent_db._collection.count()}")

# 저장된 파일 확인
db_files = os.listdir(persist_dir)
print(f"생성된 파일: {db_files}")

# 기존 DB 로드 (재사용)
loaded_db = Chroma(
    persist_directory=persist_dir,
    embedding_function=embeddings,
    collection_name="music_paper_persistent",
)
print(f"\nDB 재로드 성공! 문서 수: {loaded_db._collection.count()}")

# 로드한 DB로 검색
load_results = loaded_db.similarity_search("Spotify audio features", k=2)
print(f"재로드 DB 검색 결과: {len(load_results)}개")

print("\n💡 persist_directory를 지정하면 프로그램 종료 후에도 데이터 유지!")
print("   → 매번 PDF를 다시 로딩/임베딩할 필요 없음 (시간 절약)")

# ============================================================
# 7. FAISS - 고속 벡터 검색
# ============================================================
print("\n" + "=" * 50)
print("7. FAISS - 고속 벡터 검색")
print("=" * 50)

from langchain_community.vectorstores import FAISS

# FAISS 벡터스토어 생성
faiss_db = FAISS.from_documents(
    documents=docs,
    embedding=embeddings,
)

print(f"FAISS 저장 완료! 문서 수: {faiss_db.index.ntotal}")

# 검색
faiss_results = faiss_db.similarity_search_with_score(query, k=3)

print(f"\n쿼리: \"{query}\"\n")
for i, (doc, score) in enumerate(faiss_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. (거리: {score:.4f}) p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# FAISS 저장/로드
faiss_dir = os.path.join(os.path.dirname(__file__), "faiss_index")
faiss_db.save_local(faiss_dir)

loaded_faiss = FAISS.load_local(
    faiss_dir, embeddings, allow_dangerous_deserialization=True
)
print(f"\nFAISS 저장/로드 성공! 문서 수: {loaded_faiss.index.ntotal}")

# ============================================================
# 8. ChromaDB vs FAISS 비교
# ============================================================
print("\n" + "=" * 50)
print("8. ChromaDB vs FAISS 비교")
print("=" * 50)

import time

# 검색 속도 비교
test_queries = [
    "CNN architecture for music",
    "Spotify dataset features",
    "F1 score results",
    "deep learning model training",
    "audio spectrogram analysis",
]

# ChromaDB 검색 시간
start = time.time()
for q in test_queries:
    vectorstore.similarity_search(q, k=3)
chroma_time = time.time() - start

# FAISS 검색 시간
start = time.time()
for q in test_queries:
    faiss_db.similarity_search(q, k=3)
faiss_time = time.time() - start

print(f"검색 속도 비교 ({len(test_queries)}개 쿼리):")
print(f"  ChromaDB: {chroma_time:.4f}초")
print(f"  FAISS:    {faiss_time:.4f}초")

print("""
┌─────────────┬────────────────────┬────────────────────┐
│             │ ChromaDB           │ FAISS              │
├─────────────┼────────────────────┼────────────────────┤
│ 저장 방식   │ 파일 기반 (영구)   │ 인메모리 (파일 저장)│
│ 필터링      │ 메타데이터 필터 지원│ 기본 필터만         │
│ 속도        │ 빠름               │ 매우 빠름 (대규모)  │
│ 적합한 경우 │ 중소규모, 프로토타입│ 대규모, 프로덕션    │
│ 설치        │ pip install chromadb│ pip install faiss-cpu│
│ 특징        │ 사용이 간편        │ Meta(Facebook) 개발 │
└─────────────┴────────────────────┴────────────────────┘
""")

# ============================================================
# 9. Retriever 인터페이스 (체인 연결용)
# ============================================================
print("=" * 50)
print("9. Retriever 인터페이스")
print("=" * 50)

# VectorStore → Retriever 변환 (LCEL 체인에 연결하기 위해)
retriever = vectorstore.as_retriever(
    search_type="similarity",  # "similarity" 또는 "mmr"
    search_kwargs={"k": 3},    # 상위 3개 반환
)

# Retriever로 검색
retriever_results = retriever.invoke("What features does Spotify provide?")

print(f"Retriever 검색 결과: {len(retriever_results)}개\n")
for i, doc in enumerate(retriever_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# MMR Retriever
mmr_retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 3, "fetch_k": 10, "lambda_mult": 0.5},
)

print(f"\nMMR Retriever 검색 결과:")
mmr_ret_results = mmr_retriever.invoke("What features does Spotify provide?")
for i, doc in enumerate(mmr_ret_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

print("""
💡 as_retriever()의 중요성:
   VectorStore.similarity_search() → 직접 검색 (단독 사용)
   VectorStore.as_retriever()      → LCEL 체인에 연결 가능!

   다음 종합 실습에서 이렇게 사용:
   retriever | prompt | llm | output_parser
""")

# ============================================================
# 10. 문서 추가/삭제
# ============================================================
print("=" * 50)
print("10. 문서 추가/삭제")
print("=" * 50)

from langchain_core.documents import Document

# 새 문서 추가
new_docs = [
    Document(
        page_content="Spotify Wrapped는 매년 12월에 제공되는 개인화된 음악 요약 기능입니다.",
        metadata={"source": "manual", "topic": "spotify"}
    ),
    Document(
        page_content="K-pop은 글로벌 음악 시장에서 빠르게 성장하고 있는 장르입니다.",
        metadata={"source": "manual", "topic": "kpop"}
    ),
]

# 추가
ids = vectorstore.add_documents(new_docs)
print(f"문서 추가 완료! ID: {ids}")
print(f"현재 총 문서 수: {vectorstore._collection.count()}")

# 추가한 문서 검색 확인
new_results = vectorstore.similarity_search("Spotify Wrapped 기능", k=1)
print(f"\n추가된 문서 검색: {new_results[0].page_content[:60]}...")

# 삭제
vectorstore.delete(ids=ids)
print(f"\n문서 삭제 완료! 현재 문서 수: {vectorstore._collection.count()}")

# 정리
shutil.rmtree(persist_dir, ignore_errors=True)
shutil.rmtree(faiss_dir, ignore_errors=True)

print("\n" + "=" * 50)
print("✅ VectorStore 실습 완료!")
print("=" * 50)
print("\n📌 핵심 정리:")
print("  - ChromaDB: 간편한 벡터 저장소, 메타데이터 필터링, 영구 저장")
print("  - FAISS: 고속 벡터 검색, 대규모 데이터에 적합")
print("  - similarity_search: 유사도 기반 검색 (기본)")
print("  - MMR: 관련성 + 다양성 균형 (중복 방지)")
print("  - as_retriever(): VectorStore → 체인 연결 가능한 Retriever 변환")
print("  - persist_directory: DB 영구 저장으로 재사용 (매번 임베딩 불필요)")
print("\n🔜 다음 실습: 05_rag_end_to_end.py (전체 RAG 파이프라인 완성!)")
