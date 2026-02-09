"""
Day 3-4: RAG 파이프라인 핵심
02. Text Splitters - 문서를 청크로 분할

학습 목표:
- 왜 텍스트 분할이 필요한지 이해
- CharacterTextSplitter vs RecursiveCharacterTextSplitter 비교
- chunk_size와 chunk_overlap 전략
- 실제 PDF 논문에 적용하여 분할 결과 비교

RAG 파이프라인 두 번째 단계:
  문서 로딩 → ★[텍스트 분할]★ → 임베딩 → 벡터 저장 → 검색 → 답변
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader

# 이전 실습에서 사용한 PDF 로딩
pdf_path = os.path.join(os.path.dirname(__file__), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)
pages = PyPDFLoader(pdf_path).load()

print(f"원본 PDF: {len(pages)}페이지")
total_chars = sum(len(p.page_content) for p in pages)
print(f"전체 텍스트: {total_chars}자")

# ============================================================
# 1. 왜 텍스트 분할이 필요한가?
# ============================================================
print("\n" + "=" * 50)
print("1. 왜 텍스트 분할이 필요한가?")
print("=" * 50)

print("""
문제: LLM의 컨텍스트 윈도우는 제한적 + 긴 텍스트는 검색 정확도 저하

[12페이지 논문 전체] → LLM에 넣기엔 너무 길고, 검색도 부정확

해결: 적절한 크기의 청크(chunk)로 분할

[논문] → [청크1] [청크2] [청크3] ... → 질문과 관련된 청크만 검색!

핵심 파라미터:
  - chunk_size: 각 청크의 최대 크기 (보통 500~1500자)
  - chunk_overlap: 청크 간 겹치는 부분 (문맥 유지용, 보통 chunk_size의 10~20%)
""")

# 페이지별 텍스트 크기 확인
print("페이지별 텍스트 크기:")
for i, page in enumerate(pages):
    bar = "█" * (len(page.page_content) // 200)
    print(f"  p{i+1:2d}: {len(page.page_content):5d}자 {bar}")

# ============================================================
# 2. CharacterTextSplitter (기본)
# ============================================================
print("\n" + "=" * 50)
print("2. CharacterTextSplitter (기본 분할기)")
print("=" * 50)

from langchain_text_splitters import CharacterTextSplitter

# separator 기준으로 분할 → chunk_size에 맞게 병합
char_splitter = CharacterTextSplitter(
    separator="\n",       # 줄바꿈 기준으로 분할
    chunk_size=500,       # 각 청크 최대 500자
    chunk_overlap=50,     # 청크 간 50자 겹침
    length_function=len,  # 길이 측정 함수
)

# 2페이지 텍스트로 테스트
sample_text = pages[1].page_content
char_chunks = char_splitter.split_text(sample_text)

print(f"원본 텍스트: {len(sample_text)}자")
print(f"분할 결과: {len(char_chunks)}개 청크\n")

for i, chunk in enumerate(char_chunks):
    print(f"--- 청크 {i+1} ({len(chunk)}자) ---")
    print(chunk[:150] + "..." if len(chunk) > 150 else chunk)
    print()

# ============================================================
# 3. RecursiveCharacterTextSplitter (권장!)
# ============================================================
print("=" * 50)
print("3. RecursiveCharacterTextSplitter (핵심 분할기)")
print("=" * 50)

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 여러 구분자를 순서대로 시도 → 의미 단위를 최대한 보존
recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""],  # 우선순위 순서
    # 1순위: 빈 줄(문단) → 2순위: 줄바꿈 → 3순위: 문장 → 4순위: 공백 → 5순위: 글자
)

recursive_chunks = recursive_splitter.split_text(sample_text)

print(f"원본 텍스트: {len(sample_text)}자")
print(f"분할 결과: {len(recursive_chunks)}개 청크\n")

for i, chunk in enumerate(recursive_chunks):
    print(f"--- 청크 {i+1} ({len(chunk)}자) ---")
    print(chunk[:150] + "..." if len(chunk) > 150 else chunk)
    print()

print("💡 CharacterTextSplitter vs RecursiveCharacterTextSplitter:")
print(f"   Character:  {len(char_chunks)}개 청크 (단일 구분자)")
print(f"   Recursive:  {len(recursive_chunks)}개 청크 (다중 구분자 → 의미 보존)")

# ============================================================
# 4. chunk_size & chunk_overlap 전략
# ============================================================
print("\n" + "=" * 50)
print("4. chunk_size & chunk_overlap 비교 실험")
print("=" * 50)

# 다양한 설정으로 비교
configs = [
    {"chunk_size": 200, "chunk_overlap": 0,   "label": "작은 청크, 겹침 없음"},
    {"chunk_size": 200, "chunk_overlap": 50,  "label": "작은 청크, 겹침 있음"},
    {"chunk_size": 500, "chunk_overlap": 50,  "label": "중간 청크 (권장)"},
    {"chunk_size": 1000, "chunk_overlap": 100, "label": "큰 청크"},
]

# 전체 PDF 텍스트로 실험
full_text = "\n\n".join([p.page_content for p in pages])
print(f"전체 PDF 텍스트: {len(full_text)}자\n")

for config in configs:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
    )
    chunks = splitter.split_text(full_text)
    avg_len = sum(len(c) for c in chunks) / len(chunks)
    print(f"  {config['label']}")
    print(f"    size={config['chunk_size']}, overlap={config['chunk_overlap']}")
    print(f"    → {len(chunks)}개 청크, 평균 {avg_len:.0f}자\n")

print("""💡 chunk_size 선택 가이드:
   200~300자: 정밀 검색 (짧은 QA)
   500~800자: 범용 (논문, 기술문서) ← 가장 많이 사용
   1000자+:   넓은 맥락 필요 시 (요약, 분석)

💡 chunk_overlap 가이드:
   chunk_size의 10~20%가 적절
   너무 크면 → 중복 데이터 증가, 저장 공간 낭비
   너무 작으면 → 청크 경계에서 문맥 단절
""")

# ============================================================
# 5. Document 단위로 분할 (메타데이터 보존)
# ============================================================
print("=" * 50)
print("5. Document 단위 분할 (메타데이터 보존)")
print("=" * 50)

# split_documents()는 메타데이터를 유지한 채 분할
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)

# PDF의 Document 리스트를 직접 분할
split_docs = splitter.split_documents(pages)

print(f"원본: {len(pages)}개 Document (페이지)")
print(f"분할 후: {len(split_docs)}개 Document (청크)\n")

# 메타데이터가 보존되는지 확인
print("분할된 청크의 메타데이터 확인 (처음 5개):")
for i, doc in enumerate(split_docs[:5]):
    page_num = doc.metadata.get("page", "?")
    print(f"  청크 {i+1}: 페이지 {int(page_num)+1} | {len(doc.page_content)}자")
    print(f"    내용: {doc.page_content[:80]}...")
    print()

print("💡 split_text() vs split_documents():")
print("   split_text(str)       → 문자열 리스트 반환")
print("   split_documents(docs) → Document 리스트 반환 (메타데이터 보존!)")

# ============================================================
# 6. Overlap이 실제로 어떻게 작동하는지 시각화
# ============================================================
print("\n" + "=" * 50)
print("6. chunk_overlap 시각화")
print("=" * 50)

# 간단한 예시 텍스트로 overlap 확인
demo_text = "A" * 100 + "B" * 100 + "C" * 100 + "D" * 100 + "E" * 100

demo_splitter = RecursiveCharacterTextSplitter(
    chunk_size=120,
    chunk_overlap=30,
    separators=[""],  # 글자 단위로 강제 분할
)
demo_chunks = demo_splitter.split_text(demo_text)

print(f"원본: {'A'*5}...({'A'*100}){'B'*5}...({'B'*100})... (총 500자)")
print(f"chunk_size=120, overlap=30 → {len(demo_chunks)}개 청크\n")

for i, chunk in enumerate(demo_chunks):
    # 각 문자의 분포 표시
    counts = {ch: chunk.count(ch) for ch in "ABCDE" if chunk.count(ch) > 0}
    bar = "".join(f"{ch}({n})" for ch, n in counts.items())
    print(f"  청크 {i+1}: [{bar}] = {len(chunk)}자")

print("\n  → 겹침(overlap) 덕분에 A→B, B→C 경계의 문맥이 보존됨")

# ============================================================
# 7. 토큰 기반 분할 (TokenTextSplitter)
# ============================================================
print("\n" + "=" * 50)
print("7. 토큰 기반 분할")
print("=" * 50)

from langchain_text_splitters import RecursiveCharacterTextSplitter

# tiktoken을 이용한 토큰 기반 분할
# LLM은 '글자 수'가 아닌 '토큰 수'로 처리하므로 더 정확
token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    model_name="gpt-4",     # 토큰화 기준 모델
    chunk_size=200,          # 200 토큰
    chunk_overlap=20,        # 20 토큰 겹침
)

token_chunks = token_splitter.split_text(full_text)

print(f"토큰 기반 분할: {len(token_chunks)}개 청크")
print(f"  (chunk_size=200 tokens, overlap=20 tokens)\n")

# 글자 수 기반과 비교
char_splitter2 = RecursiveCharacterTextSplitter(
    chunk_size=800,     # 영문 기준 약 200 토큰 ≈ 800자
    chunk_overlap=80,
)
char_chunks2 = char_splitter2.split_text(full_text)

print(f"비교:")
print(f"  토큰 기반 (200 tokens): {len(token_chunks)}개 청크")
print(f"  글자 기반 (800 chars):  {len(char_chunks2)}개 청크")
print("\n💡 토큰 기반 분할이 LLM 입력 한도 관리에 더 정확")
print("   영어: ~1 토큰 ≈ 4자 / 한국어: ~1 토큰 ≈ 1.5~2자")

# ============================================================
# 8. 최종 실전: PDF 분할 + 통계 분석
# ============================================================
print("\n" + "=" * 50)
print("8. 실전: predicting_music.pdf 최적 분할")
print("=" * 50)

# 실전에서 가장 많이 쓰는 설정
final_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""],
)

final_docs = final_splitter.split_documents(pages)

print(f"원본: {len(pages)}페이지, {total_chars}자")
print(f"분할: {len(final_docs)}개 청크\n")

# 통계 분석
chunk_lengths = [len(doc.page_content) for doc in final_docs]
print(f"청크 크기 통계:")
print(f"  최소: {min(chunk_lengths)}자")
print(f"  최대: {max(chunk_lengths)}자")
print(f"  평균: {sum(chunk_lengths)/len(chunk_lengths):.0f}자")

# 페이지별 청크 분포
print(f"\n페이지별 청크 수:")
from collections import Counter
page_counts = Counter(doc.metadata["page"] for doc in final_docs)
for page_num in sorted(page_counts.keys()):
    bar = "█" * page_counts[page_num]
    print(f"  p{int(page_num)+1:2d}: {page_counts[page_num]:2d}개 {bar}")

print("\n" + "=" * 50)
print("✅ Text Splitters 실습 완료!")
print("=" * 50)
print("\n📌 핵심 정리:")
print("  - RecursiveCharacterTextSplitter가 가장 범용적 (권장)")
print("  - chunk_size=500, overlap=50이 논문/기술문서에 적합")
print("  - split_documents()로 메타데이터 보존 필수")
print("  - 토큰 기반 분할 → LLM 입력 한도 관리에 유리")
print("  - overlap → 청크 경계의 문맥 단절 방지")
print("\n🔜 다음 실습: 03_embeddings.py (텍스트 → 벡터 변환)")
