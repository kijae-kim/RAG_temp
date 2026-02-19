"""
Day 5-6: Retriever 전략 & 대화형 RAG
01. Retriever 종류 비교 - Similarity / MMR / MultiQuery

학습 목표:
- VectorStore Retriever의 k 파라미터가 결과에 미치는 영향 이해
- Similarity vs MMR 검색의 차이 실험
- MultiQueryRetriever로 검색 범위 확대
- 동일 질문에 대한 세 Retriever 결과 비교

Retriever 흐름:
  질문 → ★[Retriever 전략 선택]★ → 관련 문서 → LLM → 답변

사용 모델: Ollama (llama3.2:3b)
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# ============================================================
# 0. 데이터 준비 (PDF 로딩 → 분할 → 벡터 저장)
# ============================================================
print("=" * 60)
print("0. 데이터 준비")
print("=" * 60)

pdf_path = os.path.join(os.path.dirname(__file__), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)

pages = PyPDFLoader(pdf_path).load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(pages)

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    collection_name="retriever_compare",
)

print(f"PDF: {len(pages)}페이지 → {len(docs)}개 청크 → ChromaDB 저장 완료")

# ============================================================
# 1. VectorStore Retriever - k 파라미터 실험
# ============================================================
print("\n" + "=" * 60)
print("1. VectorStore Retriever - k 파라미터 실험")
print("=" * 60)

print("""
VectorStore Retriever = 가장 기본적인 검색기
  - vectorstore.as_retriever()로 생성
  - k: 반환할 문서 수 (search_kwargs={"k": N})
  - 질문과 가장 유사한 상위 k개 문서를 반환
""")

query = "How does CNN predict music popularity?"

print(f"쿼리: \"{query}\"\n")

for k in [1, 3, 5, 10]:
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
    results = retriever.invoke(query)
    pages_found = [int(d.metadata.get("page", 0)) + 1 for d in results]
    unique_pages = len(set(pages_found))
    print(f"  k={k:>2} → 결과 {len(results)}개, 페이지 분포: {pages_found} (고유: {unique_pages}개)")

print("""
💡 k가 클수록:
   - 더 많은 컨텍스트를 LLM에 전달 → 포괄적 답변
   - 하지만 노이즈 증가 + 토큰 비용 증가
   - 일반적으로 k=3~5가 적정
""")

# ============================================================
# 2. MMR Retriever - 다양성 + 관련성 균형
# ============================================================
print("=" * 60)
print("2. MMR Retriever - lambda_mult 실험")
print("=" * 60)

print("""
MMR (Maximum Marginal Relevance):
  - 유사도가 높으면서도 서로 다양한 문서를 반환
  - lambda_mult: 유사도 vs 다양성 균형 조절
    0.0 = 최대 다양성 (서로 다른 내용 위주)
    0.5 = 균형 (기본 추천값)
    1.0 = 최대 유사도 (similarity_search와 동일)
  - fetch_k: 후보 문서 수 (k보다 넉넉하게)
""")

# Similarity 검색 (기준)
sim_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4},
)
sim_results = sim_retriever.invoke(query)

print(f"쿼리: \"{query}\"\n")

print("📌 Similarity 검색 (기준):")
for i, doc in enumerate(sim_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# lambda_mult 비교 실험
for lm in [0.0, 0.5, 1.0]:
    mmr_retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": lm},
    )
    mmr_results = mmr_retriever.invoke(query)
    pages_found = [int(d.metadata.get("page", 0)) + 1 for d in mmr_results]
    unique_pages = len(set(pages_found))

    label = {0.0: "최대 다양성", 0.5: "균형", 1.0: "최대 유사도"}[lm]
    print(f"\n📌 MMR (lambda_mult={lm}, {label}):")
    for i, doc in enumerate(mmr_results, 1):
        page = int(doc.metadata.get("page", 0)) + 1
        print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")
    print(f"  → 페이지 분포: {pages_found} (고유: {unique_pages}개)")

print("""
💡 MMR의 핵심:
   - lambda_mult=0.0: 최대한 서로 다른 내용의 문서 반환
   - lambda_mult=1.0: similarity_search와 거의 동일
   - 보통 0.5~0.7이 RAG에 적합 (관련성 유지 + 적당한 다양성)
""")

# ============================================================
# 3. MultiQueryRetriever - LLM 기반 질문 확장
# ============================================================
print("=" * 60)
print("3. MultiQueryRetriever - LLM 기반 질문 확장")
print("=" * 60)

print("""
MultiQueryRetriever:
  - LLM이 원래 질문을 3가지 다른 관점으로 변형
  - 각 변형 질문으로 검색 → 결과를 합침 (중복 제거)
  - 하나의 질문만으로는 놓칠 수 있는 관련 문서까지 검색 가능

  예) "CNN의 정확도?" →
      1. "CNN 모델의 성능 지표는?"
      2. "딥러닝 분류 정확도 결과는?"
      3. "음악 예측 모델의 평가 결과는?"
""")

from langchain_ollama import ChatOllama
from langchain_classic.retrievers import MultiQueryRetriever

llm = ChatOllama(model="llama3.2:3b", temperature=0)

base_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 3},
)

# MultiQueryRetriever 생성
multi_retriever = MultiQueryRetriever.from_llm(
    retriever=base_retriever,
    llm=llm,
)

# 생성된 쿼리 확인을 위한 로깅 설정
logging.basicConfig()
logger = logging.getLogger("langchain.retrievers.multi_query")
logger.setLevel(logging.INFO)

print(f"쿼리: \"{query}\"\n")
print("🔍 MultiQueryRetriever 실행 (LLM이 생성한 쿼리가 로그로 출력됩니다):\n")

multi_results = multi_retriever.invoke(query)

# 로깅 복원
logger.setLevel(logging.WARNING)

print(f"\n검색 결과: {len(multi_results)}개 (중복 제거됨)")
for i, doc in enumerate(multi_results, 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

pages_found = [int(d.metadata.get("page", 0)) + 1 for d in multi_results]
print(f"\n  → 페이지 분포: {pages_found} (고유: {len(set(pages_found))}개)")

print("""
💡 MultiQuery의 장점:
   - 사용자가 애매하게 질문해도 LLM이 보완
   - 단일 쿼리 대비 더 넓은 범위의 관련 문서 검색
   - 단점: LLM 호출이 추가되므로 지연시간(latency) 증가
""")

# ============================================================
# 4. 세 Retriever 비교 정리
# ============================================================
print("=" * 60)
print("4. Retriever 비교 정리")
print("=" * 60)

comparison_query = "What Spotify features were used for prediction?"
print(f"비교 쿼리: \"{comparison_query}\"\n")

# 1) Similarity
sim_ret = vectorstore.as_retriever(search_kwargs={"k": 4})
sim_docs = sim_ret.invoke(comparison_query)
sim_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in sim_docs))

# 2) MMR
mmr_ret = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5},
)
mmr_docs = mmr_ret.invoke(comparison_query)
mmr_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in mmr_docs))

# 3) MultiQuery
multi_docs = multi_retriever.invoke(comparison_query)
multi_pages = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in multi_docs))

print(f"""
┌──────────────────┬───────────┬────────────────────┬─────────────────────────┐
│ Retriever        │ 결과 수   │ 고유 페이지        │ 특징                    │
├──────────────────┼───────────┼────────────────────┼─────────────────────────┤
│ Similarity       │ {len(sim_docs):>4}개   │ {len(sim_pages)}개 {str(sim_pages):<13}│ 가장 유사한 문서 반환   │
│ MMR (λ=0.5)      │ {len(mmr_docs):>4}개   │ {len(mmr_pages)}개 {str(mmr_pages):<13}│ 유사도 + 다양성 균형    │
│ MultiQuery       │ {len(multi_docs):>4}개   │ {len(multi_pages)}개 {str(multi_pages):<13}│ LLM 질문 확장으로 범위↑ │
└──────────────────┴───────────┴────────────────────┴─────────────────────────┘
""")

print("""
📌 Retriever 선택 가이드:
  - Similarity: 정확한 키워드/의미 매칭이 중요할 때 (기본값)
  - MMR: 다양한 관점의 문서가 필요할 때 (요약, 비교 질문)
  - MultiQuery: 질문이 애매하거나 폭넓은 검색이 필요할 때

📌 핵심 코드 패턴:
  # 1. Similarity
  retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

  # 2. MMR
  retriever = vectorstore.as_retriever(
      search_type="mmr",
      search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5}
  )

  # 3. MultiQuery
  retriever = MultiQueryRetriever.from_llm(retriever=base, llm=llm)
""")

# ============================================================
# 최종 정리
# ============================================================
print("=" * 60)
print("✅ Retriever 종류 비교 완료!")
print("=" * 60)

print("""
📌 오늘 배운 내용:
  - k 파라미터: 검색 결과 수 조절 (3~5 권장)
  - Similarity: 코사인 유사도 기반, 가장 기본적
  - MMR: 관련성 + 다양성 (lambda_mult로 조절)
  - MultiQuery: LLM이 질문 변형 → 검색 범위 확대

🔜 다음 실습: 02_ensemble_retriever.py (BM25 + 의미검색 하이브리드)
""")
