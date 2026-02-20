"""
Day 5-6: Retriever 전략 & 대화형 RAG
02. Ensemble Retriever - BM25 + 의미검색 하이브리드

학습 목표:
- BM25(키워드 기반) 검색의 원리와 강점/약점 이해
- EnsembleRetriever로 BM25 + 벡터 검색 결합
- Reciprocal Rank Fusion(RRF) 개념 이해
- 가중치 조정 실험으로 최적 비율 탐색

필요 패키지: pip install rank_bm25

Retriever 전략:
  ★[BM25(키워드) + Vector(의미)] → Ensemble → 하이브리드 검색★

사용 모델: Ollama (llama3.2:3b)
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# ============================================================
# 0. 데이터 준비
# ============================================================
print("=" * 60)
print("0. 데이터 준비")
print("=" * 60)

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)

pages = PyPDFLoader(pdf_path).load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(pages)

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

print(f"PDF: {len(pages)}페이지 → {len(docs)}개 청크")

# ============================================================
# 1. BM25 Retriever - 키워드 기반 검색
# ============================================================
print("\n" + "=" * 60)
print("1. BM25 Retriever - 키워드 기반 검색")
print("=" * 60)

print("""
BM25 (Best Matching 25):
  - TF-IDF 기반의 전통적인 키워드 검색 알고리즘
  - 문서에 질문의 단어가 얼마나 자주 등장하는지로 순위 결정
  - 임베딩 모델 불필요 → 빠르고 가벼움

  강점: 정확한 용어/고유명사 검색 (예: "CNN", "F1 score", "Spotify")
  약점: 의미적 유사성 무시 (예: "노래 인기" ↔ "music popularity" 연결 못함)
""")

from langchain_community.retrievers import BM25Retriever

# BM25 Retriever 생성 (문서의 page_content를 토큰화하여 인덱스)
bm25_retriever = BM25Retriever.from_documents(docs, k=4)

# 키워드 매칭이 강한 질문
keyword_query = "CNN F1 score accuracy"
print(f"쿼리 (키워드 명확): \"{keyword_query}\"\n")

bm25_results = bm25_retriever.invoke(keyword_query)

print("📌 BM25 검색 결과:")
for i, doc in enumerate(bm25_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# 의미 검색이 필요한 질문
semantic_query = "How well does the model perform?"
print(f"\n쿼리 (의미적): \"{semantic_query}\"\n")

bm25_semantic = bm25_retriever.invoke(semantic_query)

print("📌 BM25 검색 결과 (의미적 질문):")
for i, doc in enumerate(bm25_semantic, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

print("""
💡 BM25는 "CNN", "F1" 같은 정확한 키워드에는 강하지만,
   "모델이 얼마나 잘 작동하나?"처럼 의미적인 질문에는 약합니다.
   → 벡터 검색(의미 검색)과 결합하면 양쪽 강점을 활용 가능!
""")

# ============================================================
# 2. Ensemble Retriever - BM25 + FAISS 결합
# ============================================================
print("=" * 60)
print("2. Ensemble Retriever - 하이브리드 검색")
print("=" * 60)

print("""
EnsembleRetriever:
  - 여러 Retriever의 결과를 결합하는 메타 Retriever
  - Reciprocal Rank Fusion (RRF) 알고리즘으로 순위 통합
  - 각 Retriever에 가중치(weights) 부여 가능

  RRF 개념:
    각 Retriever에서의 순위를 기반으로 점수 계산
    score(d) = Σ 1/(k + rank_i(d))
    → 여러 Retriever에서 상위권인 문서가 최종 상위로
""")

from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers import EnsembleRetriever

# FAISS 벡터스토어 생성
faiss_db = FAISS.from_documents(docs, embeddings)
faiss_retriever = faiss_db.as_retriever(search_kwargs={"k": 4})

# BM25 + FAISS 앙상블
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, faiss_retriever],
    weights=[0.5, 0.5],  # BM25 50% + FAISS 50%
)

query = "What Spotify audio features were used in the CNN model?"
print(f"쿼리: \"{query}\"\n")

# 각 Retriever 개별 결과
bm25_only = bm25_retriever.invoke(query)
faiss_only = faiss_retriever.invoke(query)
ensemble_results = ensemble_retriever.invoke(query)

print("📌 BM25만 (키워드):")
for i, doc in enumerate(bm25_only, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

print(f"\n📌 FAISS만 (의미):")
for i, doc in enumerate(faiss_only, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

print(f"\n📌 Ensemble (BM25 + FAISS):")
for i, doc in enumerate(ensemble_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

# 페이지 분포 비교
bm25_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in bm25_only))
faiss_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in faiss_only))
ens_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in ensemble_results))

print(f"\n  BM25 페이지:     {bm25_pages}")
print(f"  FAISS 페이지:    {faiss_pages}")
print(f"  Ensemble 페이지: {ens_pages}")

# ============================================================
# 3. 가중치 조정 실험
# ============================================================
print("\n" + "=" * 60)
print("3. 가중치 조정 실험")
print("=" * 60)

print("""
weights = [BM25 비중, FAISS 비중]
  - [0.7, 0.3]: 키워드 검색 우선 → 정확한 용어 매칭 강화
  - [0.5, 0.5]: 균형 (기본 추천)
  - [0.3, 0.7]: 의미 검색 우선 → 유사한 의미 검색 강화
""")

weight_configs = [
    ([0.7, 0.3], "키워드 우선"),
    ([0.5, 0.5], "균형"),
    ([0.3, 0.7], "의미 우선"),
]

query = "deep learning architecture for predicting popularity"
print(f"쿼리: \"{query}\"\n")

for weights, label in weight_configs:
    ens = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=weights,
    )
    results = ens.invoke(query)
    pages_found = [int(d.metadata.get("page", 0)) + 1 for d in results]
    unique_pages = len(set(pages_found))

    print(f"📌 weights={weights} ({label}):")
    for i, doc in enumerate(results[:4], 1):
        page = int(doc.metadata.get("page", 0)) + 1
        print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")
    print(f"  → 결과 {len(results)}개, 고유 페이지 {unique_pages}개\n")

print("""
💡 가중치 선택 가이드:
   - 전문 용어가 많은 도메인 (의학, 법률): BM25 비중↑ [0.6, 0.4]
   - 일반적인 질의응답: 균형 [0.5, 0.5]
   - 자연어 질문이 많은 경우: 의미 검색 비중↑ [0.3, 0.7]
""")

# ============================================================
# 4. Hybrid RAG 체인
# ============================================================
print("=" * 60)
print("4. Hybrid RAG 체인 (Ensemble Retriever + LLM)")
print("=" * 60)

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatOllama(model="llama3.2:3b", temperature=0)

rag_prompt = ChatPromptTemplate.from_template("""
You are a helpful research assistant. Answer the question based ONLY on the following context.
If you cannot find the answer in the context, say "The context does not contain this information."

Context:
{context}

Question: {question}

Answer in Korean:
""")

def format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

# Ensemble Retriever로 RAG 체인 구성
hybrid_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, faiss_retriever],
    weights=[0.5, 0.5],
)

hybrid_rag_chain = (
    {
        "context": hybrid_retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | rag_prompt
    | llm
    | StrOutputParser()
)

print("체인 구조:")
print("""
  질문 ──┬── BM25 ──────┐
         │              ├→ Ensemble(RRF) → format_docs → context ──┐
         ├── FAISS ─────┘                                         ├→ prompt → LLM
         └── RunnablePassthrough → question ───────────────────────┘
""")

questions = [
    "What is the accuracy of the CNN model?",
    "What Spotify features were used for prediction?",
    "How was the training data collected?",
]

for i, question in enumerate(questions, 1):
    print(f"{'─' * 60}")
    print(f"❓ 질문 {i}: {question}")
    print(f"{'─' * 60}")
    answer = hybrid_rag_chain.invoke(question)
    print(f"\n💬 답변:\n{answer}\n")

# ============================================================
# 최종 정리
# ============================================================
print("=" * 60)
print("✅ Ensemble Retriever 학습 완료!")
print("=" * 60)

print("""
📌 오늘 배운 내용:
  - BM25: 키워드 기반 검색 (TF-IDF), 정확한 용어에 강함
  - FAISS: 벡터 기반 의미 검색, 유사한 의미에 강함
  - EnsembleRetriever: 두 검색 방식을 RRF로 결합
  - weights: 각 Retriever의 기여도 조절

📌 핵심 코드 패턴:
  bm25 = BM25Retriever.from_documents(docs, k=4)
  faiss_ret = faiss_db.as_retriever(search_kwargs={"k": 4})

  ensemble = EnsembleRetriever(
      retrievers=[bm25, faiss_ret],
      weights=[0.5, 0.5]
  )

🔜 다음 실습: 03_conversational_chain.py (대화 히스토리 유지 RAG)
""")
