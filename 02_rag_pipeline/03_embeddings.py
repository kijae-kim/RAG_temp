"""
Day 3-4: RAG 파이프라인 핵심
03. Embeddings - 텍스트를 벡터로 변환

학습 목표:
- 임베딩이란 무엇이고 왜 필요한지 이해
- HuggingFace 임베딩 (로컬, 무료)
- Ollama 임베딩 (로컬, 무료)
- 코사인 유사도로 의미 검색 원리 체험
- 실제 PDF 청크에 임베딩 적용

RAG 파이프라인 세 번째 단계:
  문서 로딩 → 텍스트 분할 → ★[임베딩]★ → 벡터 저장 → 검색 → 답변
"""

import os
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. 임베딩이란?
# ============================================================
print("=" * 50)
print("1. 임베딩(Embedding) 개념")
print("=" * 50)

print("""
임베딩 = 텍스트를 숫자 벡터(배열)로 변환하는 기술

  "고양이" → [0.12, -0.34, 0.56, 0.78, ...]  (수백~수천 차원)
  "강아지" → [0.11, -0.30, 0.55, 0.80, ...]  ← 고양이와 비슷!
  "자동차" → [-0.45, 0.67, -0.12, 0.23, ...] ← 고양이와 다름!

왜 필요한가?
  컴퓨터는 텍스트를 직접 비교할 수 없음
  → 벡터로 변환하면 '거리'로 의미적 유사도 계산 가능
  → RAG에서 "질문과 가장 유사한 문서 청크"를 찾는 핵심 기술
""")

# ============================================================
# 2. HuggingFace 임베딩 (로컬, 무료)
# ============================================================
print("=" * 50)
print("2. HuggingFace 임베딩 (all-MiniLM-L6-v2)")
print("=" * 50)

from langchain_huggingface import HuggingFaceEmbeddings

# all-MiniLM-L6-v2: 가볍고 빠른 임베딩 모델 (384차원)
# 첫 실행 시 모델 다운로드 (~80MB)
hf_embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},  # GPU 없으면 cpu
)

# 단일 텍스트 임베딩
text = "Music popularity prediction using deep learning"
vector = hf_embeddings.embed_query(text)

print(f"입력 텍스트: {text}")
print(f"벡터 차원: {len(vector)}")
print(f"벡터 앞 10개: {[round(v, 4) for v in vector[:10]]}")
print(f"벡터 타입: {type(vector)}")

# 여러 텍스트 한 번에 임베딩
texts = [
    "Spotify uses machine learning for music recommendation",
    "Deep neural networks predict song popularity",
    "I like to eat pizza on weekends",
]
vectors = hf_embeddings.embed_documents(texts)

print(f"\n여러 텍스트 임베딩:")
for i, (t, v) in enumerate(zip(texts, vectors)):
    print(f"  텍스트 {i+1}: {len(v)}차원 | {t[:50]}")

print("\n💡 embed_query() vs embed_documents():")
print("   embed_query(str)     → 검색 질문 1개 임베딩")
print("   embed_documents(list) → 문서 여러 개 임베딩 (일괄 처리)")

# ============================================================
# 3. 코사인 유사도 - 의미 검색의 원리
# ============================================================
print("\n" + "=" * 50)
print("3. 코사인 유사도 - 의미 검색의 원리")
print("=" * 50)

def cosine_similarity(a, b):
    """두 벡터 간 코사인 유사도 계산 (-1 ~ 1)"""
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# 의미가 비슷한 문장 vs 다른 문장
sentences = {
    "query": "How to predict music popularity?",
    "similar_1": "Predicting song popularity using machine learning",
    "similar_2": "Music hit prediction with neural networks",
    "different_1": "The weather is sunny today",
    "different_2": "I need to buy groceries at the store",
}

# 모든 문장 임베딩
embeddings = {k: hf_embeddings.embed_query(v) for k, v in sentences.items()}

# 쿼리와 각 문장의 유사도 계산
print(f"쿼리: \"{sentences['query']}\"\n")
print(f"{'문장':<55} {'유사도':>8}")
print("-" * 65)

for key in ["similar_1", "similar_2", "different_1", "different_2"]:
    sim = cosine_similarity(embeddings["query"], embeddings[key])
    bar = "█" * int(sim * 30) if sim > 0 else ""
    print(f"  {sentences[key]:<53} {sim:>6.4f} {bar}")

print("""
💡 코사인 유사도:
   1.0  = 완전히 같은 의미
   0.5+ = 관련 있는 내용
   0.0  = 무관한 내용
  -1.0  = 반대 의미

   → RAG에서 질문과 유사도가 높은 청크를 상위 k개 반환!
""")

# ============================================================
# 4. 임베딩으로 간단한 의미 검색 구현
# ============================================================
print("=" * 50)
print("4. 임베딩 기반 의미 검색 (직접 구현)")
print("=" * 50)

# 문서 청크 (미니 지식 베이스)
knowledge_base = [
    "CNN은 이미지 인식에서 뛰어난 성능을 보이는 딥러닝 모델이다.",
    "Spotify는 음악 스트리밍 서비스로 머신러닝 기반 추천 시스템을 사용한다.",
    "Random Forest는 앙상블 학습 방법으로 여러 결정 트리를 결합한다.",
    "음악의 인기도는 tempo, energy, danceability 등의 특성으로 예측할 수 있다.",
    "텍스트 임베딩은 자연어를 벡터 공간에 매핑하는 기술이다.",
    "Spotify의 Discover Weekly는 협업 필터링과 NLP를 결합한 추천 시스템이다.",
]

# 모든 청크 임베딩
kb_vectors = hf_embeddings.embed_documents(knowledge_base)

def simple_search(query, top_k=3):
    """간단한 의미 검색"""
    query_vector = hf_embeddings.embed_query(query)
    # 모든 청크와 유사도 계산
    similarities = [
        (i, cosine_similarity(query_vector, doc_vec))
        for i, doc_vec in enumerate(kb_vectors)
    ]
    # 유사도 내림차순 정렬
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]

# 검색 테스트
queries = [
    "음악 추천 알고리즘은 어떻게 작동하나요?",
    "노래가 인기를 끄는 요인은 무엇인가요?",
    "딥러닝 모델의 종류는?",
]

for query in queries:
    print(f"\n🔍 질문: \"{query}\"")
    results = simple_search(query, top_k=3)
    for rank, (idx, score) in enumerate(results, 1):
        print(f"   {rank}위 (유사도: {score:.4f}): {knowledge_base[idx][:60]}...")

print("\n💡 이것이 VectorStore가 내부적으로 하는 일!")
print("   다음 실습에서 ChromaDB/FAISS가 이 과정을 자동화합니다.")

# ============================================================
# 5. Ollama 임베딩
# ============================================================
print("\n" + "=" * 50)
print("5. Ollama 임베딩 (llama3.2)")
print("=" * 50)

from langchain_ollama import OllamaEmbeddings

ollama_embeddings = OllamaEmbeddings(model="llama3.2:3b")

# Ollama로 임베딩 생성
ollama_vector = ollama_embeddings.embed_query("Music popularity prediction")
print(f"Ollama 임베딩 차원: {len(ollama_vector)}")
print(f"벡터 앞 10개: {[round(v, 4) for v in ollama_vector[:10]]}")

# HuggingFace vs Ollama 비교
print(f"\n임베딩 모델 비교:")
print(f"  HuggingFace (all-MiniLM-L6-v2): {len(vector)}차원 | 빠름, 가벼움")
print(f"  Ollama (llama3.2:3b):            {len(ollama_vector)}차원 | 범용 LLM 기반")

print("""
💡 임베딩 모델 선택 가이드:
   all-MiniLM-L6-v2  : 384차원, 빠름, 영어 특화, 가벼움
   bge-small-en      : 384차원, 빠름, 다국어 지원
   text-embedding-3-small (OpenAI): 1536차원, 고성능, 유료
   Ollama LLM 모델   : 높은 차원, 느림, 범용 모델 기반
""")

# ============================================================
# 6. 실전: PDF 청크에 임베딩 적용
# ============================================================
print("=" * 50)
print("6. 실전: predicting_music.pdf 청크 임베딩")
print("=" * 50)

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# PDF 로딩 + 분할 (이전 실습 복습)
pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)

pages = PyPDFLoader(pdf_path).load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(pages)

print(f"PDF: {len(pages)}페이지 → {len(chunks)}개 청크")

# 처음 10개 청크만 임베딩 (시간 절약)
sample_chunks = chunks[:10]
chunk_texts = [c.page_content for c in sample_chunks]
chunk_vectors = hf_embeddings.embed_documents(chunk_texts)

print(f"임베딩 완료: {len(chunk_vectors)}개 청크 × {len(chunk_vectors[0])}차원\n")

# PDF 내용에 대해 질문 검색
pdf_queries = [
    "What dataset was used in this study?",
    "How does CNN predict music popularity?",
    "What is the F1 score of the model?",
]

for query in pdf_queries:
    query_vec = hf_embeddings.embed_query(query)
    scores = [
        (i, cosine_similarity(query_vec, cv))
        for i, cv in enumerate(chunk_vectors)
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    best_idx, best_score = scores[0]
    print(f"🔍 \"{query}\"")
    print(f"   → 최고 유사도: {best_score:.4f} (청크 {best_idx+1}, p{int(sample_chunks[best_idx].metadata['page'])+1})")
    print(f"   → 내용: {chunk_texts[best_idx][:100]}...")
    print()

# ============================================================
# 7. 임베딩 차원 시각화 (2D 축소)
# ============================================================
print("=" * 50)
print("7. 임베딩 벡터 2D 시각화 (PCA)")
print("=" * 50)

from sklearn.decomposition import PCA

# 시각화할 문장들 (관련 주제끼리 묶임)
viz_texts = [
    # 음악 관련
    "music popularity prediction",
    "song recommendation system",
    "Spotify audio features",
    # ML 관련
    "convolutional neural network",
    "deep learning classification",
    "random forest algorithm",
    # 완전 다른 주제
    "cooking recipe for pasta",
    "weather forecast tomorrow",
]
viz_labels = ["음악1", "음악2", "음악3", "ML1", "ML2", "ML3", "기타1", "기타2"]

viz_vectors = hf_embeddings.embed_documents(viz_texts)

# PCA로 384차원 → 2차원 축소
pca = PCA(n_components=2)
coords = pca.fit_transform(viz_vectors)

print(f"384차원 → 2차원 축소 (PCA)\n")
print(f"{'라벨':<8} {'X':>8} {'Y':>8}  텍스트")
print("-" * 65)
for label, (x, y), text in zip(viz_labels, coords, viz_texts):
    print(f"  {label:<6} {x:>8.4f} {y:>8.4f}  {text}")

# 그룹별 중심 거리 계산
music_center = np.mean(coords[:3], axis=0)
ml_center = np.mean(coords[3:6], axis=0)
other_center = np.mean(coords[6:], axis=0)

dist_music_ml = np.linalg.norm(music_center - ml_center)
dist_music_other = np.linalg.norm(music_center - other_center)

print(f"\n그룹 간 거리:")
print(f"  음악 ↔ ML:   {dist_music_ml:.4f} (비교적 가까움)")
print(f"  음악 ↔ 기타: {dist_music_other:.4f} (먼 거리)")
print("\n💡 의미적으로 관련된 텍스트는 벡터 공간에서 가까이 위치!")

print("\n" + "=" * 50)
print("✅ Embeddings 실습 완료!")
print("=" * 50)
print("\n📌 핵심 정리:")
print("  - 임베딩 = 텍스트를 숫자 벡터로 변환 (의미를 수치화)")
print("  - HuggingFace all-MiniLM-L6-v2: 무료, 빠름, 384차원")
print("  - embed_query() = 질문 1개, embed_documents() = 문서 여러 개")
print("  - 코사인 유사도로 '의미적 거리' 측정 (1에 가까울수록 유사)")
print("  - 관련 텍스트는 벡터 공간에서 가까이 클러스터링됨")
print("\n🔜 다음 실습: 04_vectorstore.py (벡터 저장 & 유사도 검색)")
