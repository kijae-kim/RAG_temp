"""
Day 3-4: RAG 파이프라인 핵심
05. End-to-End RAG 파이프라인 - 종합 실습

학습 목표:
- 4단계(로딩→분할→임베딩→저장)를 하나로 연결
- LCEL 체인으로 Retriever + Prompt + LLM 구성
- PDF 논문에 질문하고 근거 기반 답변 받기
- 웹 데이터 기반 RAG도 구현
- 출처(Source) 표시 포함

RAG 파이프라인 전체 흐름:
  ★[문서 로딩 → 분할 → 임베딩 → 벡터 저장 → 검색 → LLM 답변]★

사용 모델: Ollama (llama3.2:3b)
"""

import os
import shutil
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. RAG 파이프라인 구축: PDF 논문
# ============================================================
print("=" * 60)
print("PART 1: PDF 논문 RAG 파이프라인")
print("=" * 60)

# --- Step 1: 문서 로딩 ---
print("\n📄 Step 1: 문서 로딩")
from langchain_community.document_loaders import PyPDFLoader

pdf_path = os.path.join(os.path.dirname(__file__), "..", "..", "predicting_music.pdf")
pdf_path = os.path.abspath(pdf_path)
pages = PyPDFLoader(pdf_path).load()
print(f"   로드 완료: {len(pages)}페이지")

# --- Step 2: 텍스트 분할 ---
print("\n✂️  Step 2: 텍스트 분할")
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(pages)
print(f"   분할 완료: {len(docs)}개 청크")

# --- Step 3: 임베딩 + 벡터 저장 ---
print("\n🔢 Step 3: 임베딩 & 벡터 저장 (ChromaDB)")
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

# ChromaDB에 저장
persist_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
if os.path.exists(persist_dir):
    shutil.rmtree(persist_dir)

vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    persist_directory=persist_dir,
    collection_name="music_paper",
)
print(f"   저장 완료: {vectorstore._collection.count()}개 벡터")

# --- Step 4: Retriever ---
print("\n🔍 Step 4: Retriever 생성")
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 10},
)
print(f"   MMR Retriever 준비 완료 (k=4)")

# --- Step 5: RAG 체인 구성 (LCEL) ---
print("\n🔗 Step 5: RAG 체인 구성")
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatOllama(model="llama3.2:3b", temperature=0)

# RAG 프롬프트 템플릿
rag_prompt = ChatPromptTemplate.from_template("""
You are a helpful research assistant. Answer the question based ONLY on the following context.
If you cannot find the answer in the context, say "The context does not contain this information."

Context:
{context}

Question: {question}

Answer in Korean:
""")

# 검색된 문서를 하나의 문자열로 합치는 함수
def format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

# LCEL RAG 체인 구성
# retriever → 검색된 문서 → format_docs → 프롬프트 → LLM → 문자열 출력
rag_chain = (
    {
        "context": retriever | format_docs,   # 질문 → 검색 → 텍스트 변환
        "question": RunnablePassthrough(),     # 질문 그대로 전달
    }
    | rag_prompt
    | llm
    | StrOutputParser()
)

print("   체인 구성 완료!")
print("""
   체인 구조:
   질문 ──┬── retriever → format_docs → context ──┐
          │                                       ├→ prompt → LLM → 답변
          └── RunnablePassthrough → question ──────┘
""")

# ============================================================
# 2. PDF RAG 테스트
# ============================================================
print("=" * 60)
print("PART 2: PDF 논문에 질문하기")
print("=" * 60)

questions = [
    "What is the main goal of this research?",
    "What accuracy did the CNN model achieve?",
    "What Spotify features were used in this study?",
    "How was the dataset collected?",
]

for i, question in enumerate(questions, 1):
    print(f"\n{'─' * 60}")
    print(f"❓ 질문 {i}: {question}")
    print(f"{'─' * 60}")

    answer = rag_chain.invoke(question)
    print(f"\n💬 답변:\n{answer}")

# ============================================================
# 3. 출처(Source) 포함 RAG 체인
# ============================================================
print("\n" + "=" * 60)
print("PART 3: 출처 표시 RAG 체인")
print("=" * 60)

from langchain_core.runnables import RunnableParallel

# 답변과 출처를 동시에 반환하는 체인
rag_chain_with_source = RunnableParallel(
    answer=rag_chain,
    source_docs=retriever,  # 검색된 원본 문서도 반환
)

question = "What deep learning architecture was used?"
print(f"\n❓ 질문: {question}\n")

result = rag_chain_with_source.invoke(question)

print(f"💬 답변:\n{result['answer']}\n")
print(f"📚 출처 ({len(result['source_docs'])}개 청크):")
for i, doc in enumerate(result["source_docs"], 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"   [{i}] 페이지 {page}: {doc.page_content[:80].replace(chr(10), ' ')}...")

# ============================================================
# 4. 스트리밍 RAG
# ============================================================
print("\n" + "=" * 60)
print("PART 4: 스트리밍 RAG (실시간 답변)")
print("=" * 60)

question = "Summarize the key findings of this paper."
print(f"\n❓ 질문: {question}\n")
print("💬 답변 (스트리밍):")

for chunk in rag_chain.stream(question):
    print(chunk, end="", flush=True)
print("\n")

# ============================================================
# 5. 웹 데이터 RAG
# ============================================================
print("=" * 60)
print("PART 5: 웹 데이터 RAG (Spotify Research)")
print("=" * 60)

from langchain_community.document_loaders import WebBaseLoader

# Spotify Research 블로그 로딩
print("\n🌐 웹 페이지 로딩...")
web_loader = WebBaseLoader([
    "https://research.atspotify.com/",
    "https://research.atspotify.com/blog/",
])
web_pages = web_loader.load()
print(f"   로드 완료: {len(web_pages)}개 페이지")

# 분할 + 벡터 저장
web_docs = splitter.split_documents(web_pages)
print(f"   분할 완료: {len(web_docs)}개 청크")

web_vectorstore = Chroma.from_documents(
    documents=web_docs,
    embedding=embeddings,
    collection_name="spotify_research",
)

web_retriever = web_vectorstore.as_retriever(search_kwargs={"k": 3})

# 웹 RAG 체인
web_rag_chain = (
    {
        "context": web_retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | rag_prompt
    | llm
    | StrOutputParser()
)

# 웹 데이터에 질문
web_questions = [
    "What research areas does Spotify focus on?",
    "What recent topics has Spotify published about?",
]

for i, question in enumerate(web_questions, 1):
    print(f"\n{'─' * 60}")
    print(f"❓ 질문 {i}: {question}")
    print(f"{'─' * 60}")
    answer = web_rag_chain.invoke(question)
    print(f"\n💬 답변:\n{answer}")

# ============================================================
# 6. PDF + 웹 통합 RAG (멀티 소스)
# ============================================================
print("\n" + "=" * 60)
print("PART 6: 멀티 소스 RAG (PDF + 웹 통합)")
print("=" * 60)

from langchain_community.vectorstores import FAISS

# 모든 문서를 하나의 벡터스토어에 통합
all_docs = docs + web_docs
print(f"\n통합 문서: PDF {len(docs)}개 + 웹 {len(web_docs)}개 = {len(all_docs)}개")

# FAISS로 통합 저장 (빠른 검색)
unified_db = FAISS.from_documents(all_docs, embeddings)
unified_retriever = unified_db.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 15},
)

# 통합 RAG 체인
unified_chain = RunnableParallel(
    answer=(
        {
            "context": unified_retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    ),
    source_docs=unified_retriever,
)

question = "How does Spotify use AI and machine learning for music?"
print(f"\n❓ 질문: {question}\n")

result = unified_chain.invoke(question)
print(f"💬 답변:\n{result['answer']}\n")

print(f"📚 출처 (PDF + 웹 통합 검색):")
for i, doc in enumerate(result["source_docs"], 1):
    source = doc.metadata.get("source", "?")
    if "predicting_music" in source:
        src_label = "PDF 논문"
        page = f"p{int(doc.metadata.get('page', 0)) + 1}"
    else:
        src_label = "웹"
        page = source[:50]
    print(f"   [{i}] {src_label} ({page}): {doc.page_content[:60].replace(chr(10), ' ')}...")

# 정리
shutil.rmtree(persist_dir, ignore_errors=True)

# ============================================================
# 최종 정리
# ============================================================
print("\n" + "=" * 60)
print("✅ Day 3-4 RAG 파이프라인 학습 완료!")
print("=" * 60)

print("""
📌 오늘 배운 전체 흐름:

  [PDF/웹] → PyPDFLoader / WebBaseLoader     ← 01_document_loaders.py
           → RecursiveCharacterTextSplitter   ← 02_text_splitters.py
           → HuggingFaceEmbeddings            ← 03_embeddings.py
           → ChromaDB / FAISS                 ← 04_vectorstore.py
           → Retriever | Prompt | LLM         ← 05_rag_end_to_end.py (오늘!)

📌 핵심 코드 패턴 (외워두세요!):

  # RAG 체인 구성
  rag_chain = (
      {"context": retriever | format_docs,
       "question": RunnablePassthrough()}
      | prompt
      | llm
      | StrOutputParser()
  )

  # 실행
  answer = rag_chain.invoke("질문")

📌 Day 3-4 핵심 키워드:
  - Document = page_content + metadata
  - chunk_size=500, overlap=50 (범용)
  - embed_query() / embed_documents()
  - ChromaDB: 간편, 영구 저장 / FAISS: 고속, 대규모
  - MMR: 다양성 + 관련성 균형
  - as_retriever(): 체인 연결의 핵심
  - RunnablePassthrough: 입력 그대로 전달
  - format_docs: 검색 결과를 문자열로 변환

🔜 다음 학습 (Day 5-6): Retriever 심화 & Chain 패턴
   → MultiQuery, Ensemble Retriever
   → ConversationalRetrievalChain (대화 맥락 유지)
""")
