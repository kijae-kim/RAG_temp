"""
Day 5-6: Retriever 전략 & 대화형 RAG
05. 종합 실습 - 인터랙티브 대화형 RAG 챗봇

학습 목표:
- Retriever 전략 선택 (Similarity / MMR / Ensemble)
- History-Aware 대화형 RAG 파이프라인 조립
- JsonOutputParser로 구조화 출력
- 인터랙티브 챗봇 루프 구현

전체 흐름:
  ★[문서 로딩 → 벡터 저장 → Retriever 선택 → 히스토리 인식 RAG → 인터랙티브 챗봇]★

사용 모델: Ollama (llama3.2:3b)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PART 1: 환경 설정 & FAISS 벡터스토어 구축
# ============================================================
print("=" * 60)
print("PART 1: 환경 설정 & 벡터스토어 구축")
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

# --- Step 3: 임베딩 + 벡터 저장 (FAISS) ---
print("\n🔢 Step 3: 임베딩 & FAISS 벡터 저장")
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

vectorstore = FAISS.from_documents(docs, embeddings)
print(f"   FAISS 저장 완료: {vectorstore.index.ntotal}개 벡터")

# --- Step 4: LLM ---
print("\n🤖 Step 4: LLM 준비")
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3.2:3b", temperature=0)
print("   llama3.2:3b 준비 완료")

# ============================================================
# PART 2: Retriever 전략 선택
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Retriever 전략 선택")
print("=" * 60)

from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

# 3가지 Retriever 준비
similarity_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

mmr_retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5},
)

bm25_retriever = BM25Retriever.from_documents(docs, k=4)
faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, faiss_retriever],
    weights=[0.5, 0.5],
)

retrievers = {
    "similarity": similarity_retriever,
    "mmr": mmr_retriever,
    "ensemble": ensemble_retriever,
}

print("""
사용 가능한 Retriever 전략:

  1. similarity - 코사인 유사도 기반 (기본, 가장 빠름)
  2. mmr        - 관련성 + 다양성 균형 (중복 방지)
  3. ensemble   - BM25(키워드) + FAISS(의미) 하이브리드

선택된 기본 전략: ensemble (하이브리드)
""")

# 기본 Retriever 선택
selected_retriever = ensemble_retriever
selected_name = "ensemble"

# 성능 비교 (간단 테스트)
test_query = "What accuracy did the CNN model achieve?"
print(f"📌 Retriever 비교 (쿼리: \"{test_query}\")\n")

for name, ret in retrievers.items():
    results = ret.invoke(test_query)
    pages_found = sorted(set(int(d.metadata.get("page", 0)) + 1 for d in results))
    print(f"  {name:>12}: {len(results)}개 결과, 페이지 {pages_found}")

# ============================================================
# PART 3: History-Aware 대화형 RAG 파이프라인
# ============================================================
print("\n" + "=" * 60)
print("PART 3: History-Aware 대화형 RAG 파이프라인 조립")
print("=" * 60)

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# --- 질문 재작성 프롬프트 ---
contextualize_prompt = ChatPromptTemplate.from_messages([
    ("system", """Given a chat history and the latest user question \
which might reference context in the chat history, \
formulate a standalone question which can be understood \
without the chat history. Do NOT answer the question, \
just reformulate it if needed and otherwise return it as is."""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# --- QA 프롬프트 ---
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful research assistant analyzing a paper about predicting music popularity using CNN.
Answer the question based on the context below.
If you cannot find the answer in the context, say "The context does not contain this information."
Answer in Korean. Be concise and specific.

Context:
{context}"""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# --- 체인 조립 ---
history_aware_retriever = create_history_aware_retriever(
    llm, selected_retriever, contextualize_prompt
)
qa_chain = create_stuff_documents_chain(llm, qa_prompt)
rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

# --- 세션 관리 ---
session_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

conversational_rag = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",
)

print("✅ 대화형 RAG 파이프라인 조립 완료!")
print("""
  파이프라인 구조:
    질문 + 히스토리 → 질문 재작성 → Ensemble Retriever → 관련 문서
                                                           ↓
    히스토리 + 질문 + 문서 → QA 프롬프트 → LLM → 답변 → 히스토리 저장
""")

# 자동 데모: 3턴 대화
print("📌 자동 데모 (3턴 대화):")
demo_session = "auto_demo"
demo_questions = [
    "What deep learning model does this paper use?",
    "What was its accuracy?",
    "What input features were used?",
]

for i, q in enumerate(demo_questions, 1):
    print(f"\n{'─' * 50}")
    print(f"❓ 질문 {i}: {q}")
    result = conversational_rag.invoke(
        {"input": q},
        config={"configurable": {"session_id": demo_session}},
    )
    answer = result["answer"][:200]
    print(f"💬 답변: {answer}")

# ============================================================
# PART 4: JsonOutputParser 구조화 출력
# ============================================================
print("\n\n" + "=" * 60)
print("PART 4: 구조화 출력 (JSON 형식)")
print("=" * 60)

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

class StructuredAnswer(BaseModel):
    """구조화된 RAG 답변"""
    answer: str = Field(description="질문에 대한 답변 (한국어)")
    confidence: str = Field(description="답변 신뢰도: high/medium/low")
    key_points: List[str] = Field(description="핵심 포인트 3개 이내")
    source_pages: List[int] = Field(description="참조한 페이지 번호 리스트")

json_parser = JsonOutputParser(pydantic_object=StructuredAnswer)

json_prompt = ChatPromptTemplate.from_template("""
You are a research assistant. Answer the question based on the context.

Context:
{context}

Question: {question}

{format_instructions}
""")

def format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

from langchain_core.runnables import RunnablePassthrough

json_chain = (
    {
        "context": selected_retriever | format_docs,
        "question": RunnablePassthrough(),
        "format_instructions": lambda _: json_parser.get_format_instructions(),
    }
    | json_prompt
    | llm
    | json_parser
)

print("📌 JSON 구조화 출력 데모:")
json_query = "What is the main contribution of this paper?"
print(f"\n❓ 질문: {json_query}\n")

try:
    json_result = json_chain.invoke(json_query)
    print("💬 구조화 답변:")
    print(f"   답변: {json_result.get('answer', 'N/A')}")
    print(f"   신뢰도: {json_result.get('confidence', 'N/A')}")
    print(f"   핵심 포인트:")
    for kp in json_result.get("key_points", []):
        print(f"     - {kp}")
    print(f"   참조 페이지: {json_result.get('source_pages', [])}")
except Exception as e:
    print(f"   ⚠️ JSON 파싱 실패 (작은 LLM의 한계): {type(e).__name__}")
    print(f"   → 더 큰 모델(GPT-4, Claude 등)에서는 안정적으로 작동합니다.")

# ============================================================
# 인터랙티브 챗봇 루프
# ============================================================
print("\n" + "=" * 60)
print("🤖 인터랙티브 대화형 RAG 챗봇")
print("=" * 60)

print("""
명령어:
  quit   - 종료
  clear  - 대화 히스토리 초기화
  history - 대화 히스토리 보기
  json   - 다음 질문을 JSON 구조화 출력으로 답변

아무 질문이나 입력하세요! (논문에 관한 질문 추천)
예: What is the main goal of this research?
""")

chat_session = "interactive"
json_mode = False

while True:
    try:
        user_input = input("\n🧑 질문: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n👋 챗봇을 종료합니다.")
        break

    if not user_input:
        continue

    # 명령어 처리
    if user_input.lower() == "quit":
        print("\n👋 챗봇을 종료합니다.")
        break

    elif user_input.lower() == "clear":
        session_store.pop(chat_session, None)
        print("🗑️  대화 히스토리가 초기화되었습니다.")
        continue

    elif user_input.lower() == "history":
        hist = get_session_history(chat_session)
        if not hist.messages:
            print("📭 대화 히스토리가 비어있습니다.")
        else:
            print(f"\n📜 대화 히스토리 ({len(hist.messages)//2}턴):")
            for msg in hist.messages:
                role = "🧑" if isinstance(msg, HumanMessage) else "🤖"
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"  {role} {content}")
        continue

    elif user_input.lower() == "json":
        json_mode = True
        print("📋 다음 질문은 JSON 구조화 출력으로 답변합니다.")
        continue

    # JSON 모드
    if json_mode:
        json_mode = False
        print("\n💬 답변 (JSON 구조화):")
        try:
            json_result = json_chain.invoke(user_input)
            print(f"   답변: {json_result.get('answer', 'N/A')}")
            print(f"   신뢰도: {json_result.get('confidence', 'N/A')}")
            print(f"   핵심 포인트:")
            for kp in json_result.get("key_points", []):
                print(f"     - {kp}")
            print(f"   참조 페이지: {json_result.get('source_pages', [])}")
        except Exception:
            print("   ⚠️ JSON 파싱 실패. 일반 모드로 답변합니다.")
            result = conversational_rag.invoke(
                {"input": user_input},
                config={"configurable": {"session_id": chat_session}},
            )
            print(f"   {result['answer']}")
        continue

    # 일반 대화형 RAG
    result = conversational_rag.invoke(
        {"input": user_input},
        config={"configurable": {"session_id": chat_session}},
    )

    print(f"\n🤖 답변:\n{result['answer']}")

    # 출처 표시
    if "context" in result and result["context"]:
        pages_ref = sorted(set(
            int(d.metadata.get("page", 0)) + 1 for d in result["context"]
        ))
        print(f"\n📚 참조 페이지: {pages_ref}")
