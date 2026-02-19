"""
Day 5-6: Retriever 전략 & 대화형 RAG
03. 대화형 RAG - ChatMessageHistory + RunnableWithMessageHistory

학습 목표:
- 기존 RAG의 한계 이해 (stateless → 후속 질문 실패)
- ChatMessageHistory로 대화 기록 관리
- RunnableWithMessageHistory로 대화 맥락 유지 RAG 구현
- 멀티턴 대화 데모 & 남은 한계점 확인

대화형 RAG 흐름:
  ★[대화 히스토리 + 질문 + 검색 결과] → LLM → 답변★

사용 모델: Ollama (llama3.2:3b)
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# ============================================================
# 0. 데이터 준비 (PDF → FAISS)
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

vectorstore = FAISS.from_documents(docs, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

print(f"PDF: {len(pages)}페이지 → {len(docs)}개 청크 → FAISS 저장 완료")

# ============================================================
# 1. 문제 시연: Stateless RAG의 한계
# ============================================================
print("\n" + "=" * 60)
print("1. 문제 시연: Stateless RAG의 한계")
print("=" * 60)

print("""
기존 RAG 체인의 문제:
  - 매 질문마다 독립적으로 처리 (이전 대화 기억 못함)
  - "그것의 정확도는?" 같은 후속 질문에 "그것"이 뭔지 모름
""")

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatOllama(model="llama3.2:3b", temperature=0)

def format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

# 기존 stateless RAG 체인
stateless_prompt = ChatPromptTemplate.from_template("""
Answer the question based ONLY on the following context.

Context:
{context}

Question: {question}

Answer in Korean:
""")

stateless_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | stateless_prompt
    | llm
    | StrOutputParser()
)

# 첫 번째 질문 - 정상 작동
print("❓ 질문 1: What deep learning model was used in this study?")
answer1 = stateless_chain.invoke("What deep learning model was used in this study?")
print(f"💬 답변: {answer1[:200]}\n")

# 후속 질문 - "그것"의 정확도? → 문맥 없이 실패
print("❓ 질문 2 (후속): What was its accuracy?")
answer2 = stateless_chain.invoke("What was its accuracy?")
print(f"💬 답변: {answer2[:200]}")

print("""
⚠️ 문제점:
   - "its"가 무엇을 가리키는지 모름 (이전 대화 기억 없음)
   - Retriever도 "its accuracy"로 검색 → 관련 없는 결과
   - 해결: 대화 히스토리를 체인에 포함시켜야 함
""")

# ============================================================
# 2. ChatMessageHistory - 대화 기록 저장소
# ============================================================
print("=" * 60)
print("2. ChatMessageHistory - 대화 기록 관리")
print("=" * 60)

print("""
ChatMessageHistory:
  - 대화 내용(HumanMessage, AIMessage)을 리스트로 저장
  - 세션별로 별도 히스토리 관리 가능
  - add_user_message() / add_ai_message() 로 수동 추가
""")

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# 히스토리 수동 사용 예제
history = ChatMessageHistory()

history.add_user_message("이 논문에서 사용한 딥러닝 모델은 뭐야?")
history.add_ai_message("이 논문에서는 CNN(Convolutional Neural Network) 모델을 사용했습니다.")
history.add_user_message("그 모델의 정확도는?")

print("📌 저장된 대화 히스토리:")
for msg in history.messages:
    role = "사용자" if isinstance(msg, HumanMessage) else "AI"
    print(f"  [{role}] {msg.content}")

print(f"\n  총 {len(history.messages)}개 메시지 저장됨")

# ============================================================
# 3. RunnableWithMessageHistory - 대화 맥락 유지 RAG
# ============================================================
print("\n" + "=" * 60)
print("3. RunnableWithMessageHistory - 대화 맥락 유지 RAG")
print("=" * 60)

print("""
RunnableWithMessageHistory:
  - 기존 체인에 대화 히스토리를 자동으로 주입
  - session_id로 사용자별 대화 관리
  - 프롬프트에 MessagesPlaceholder("chat_history")로 히스토리 삽입 위치 지정
""")

from langchain_core.prompts import MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

# 대화 히스토리 포함 프롬프트
conversational_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful research assistant. Answer the question based on the context and chat history.
If the chat history contains relevant information, use it to understand the context of the question.
If you cannot find the answer, say "The context does not contain this information."

Context:
{context}"""),
    MessagesPlaceholder("chat_history"),  # 여기에 대화 기록 삽입
    ("human", "{question}"),
])

# RAG 체인 (히스토리 포함)
conversational_chain = (
    {
        "context": (lambda x: x["question"]) | retriever | format_docs,
        "question": lambda x: x["question"],
        "chat_history": lambda x: x["chat_history"],
    }
    | conversational_prompt
    | llm
    | StrOutputParser()
)

# 세션별 히스토리 저장소
session_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

# RunnableWithMessageHistory로 감싸기
chain_with_history = RunnableWithMessageHistory(
    conversational_chain,
    get_session_history,
    input_messages_key="question",
    history_messages_key="chat_history",
)

print("체인 구조:")
print("""
  ┌─ chat_history (자동 주입) ─┐
  │                            ↓
  질문 → retriever → context → prompt(system + history + human) → LLM → 답변
                                                                       │
                                                         히스토리에 자동 저장
""")

# ============================================================
# 4. 멀티턴 대화 데모
# ============================================================
print("=" * 60)
print("4. 멀티턴 대화 데모")
print("=" * 60)

session_id = "demo_session"

questions = [
    "What deep learning model was used in this study?",
    "What was its accuracy?",
    "What features did it use as input?",
    "Can you summarize the main findings?",
]

for i, question in enumerate(questions, 1):
    print(f"\n{'─' * 60}")
    print(f"❓ 질문 {i}: {question}")
    print(f"{'─' * 60}")

    answer = chain_with_history.invoke(
        {"question": question},
        config={"configurable": {"session_id": session_id}},
    )
    print(f"\n💬 답변:\n{answer}")

# 저장된 히스토리 확인
print(f"\n{'─' * 60}")
print("📌 저장된 대화 히스토리:")
print(f"{'─' * 60}")
stored_history = get_session_history(session_id)
for msg in stored_history.messages:
    role = "🧑 사용자" if isinstance(msg, HumanMessage) else "🤖 AI"
    content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
    print(f"  {role}: {content}")

print(f"\n  총 {len(stored_history.messages)}개 메시지 ({len(stored_history.messages)//2}턴 대화)")

# ============================================================
# 한계점 분석
# ============================================================
print("\n" + "=" * 60)
print("⚠️ 현재 방식의 한계")
print("=" * 60)

print("""
문제: 검색(Retriever)은 여전히 stateless!

  질문 2: "What was its accuracy?"
  → Retriever는 "its accuracy"로 검색 (대화 맥락 모름)
  → LLM은 히스토리로 "its = CNN"을 이해하지만,
     검색된 컨텍스트가 부정확할 수 있음

  현재 흐름:
    "What was its accuracy?" ──→ Retriever (its? 뭐지?) ──→ 부정확한 결과
                              ↘ LLM (히스토리에서 its=CNN 파악) → 대답은 시도

  이상적인 흐름 (04에서 구현):
    "What was its accuracy?" ──→ 질문 재작성 ("CNN model accuracy?")
                              ──→ Retriever (정확한 검색!) ──→ 정확한 결과

💡 해결: History-Aware Retriever (04_history_aware_retrieval.py)
   → 질문을 대화 맥락에 맞게 재작성한 후 검색!
""")

# ============================================================
# 최종 정리
# ============================================================
print("=" * 60)
print("✅ 대화형 RAG 기본 구현 완료!")
print("=" * 60)

print("""
📌 오늘 배운 내용:
  - ChatMessageHistory: 대화 기록 저장소
  - MessagesPlaceholder: 프롬프트에 히스토리 삽입 위치 지정
  - RunnableWithMessageHistory: 체인에 자동 히스토리 관리 추가
  - session_id: 사용자/세션별 독립적인 대화 관리

📌 핵심 코드 패턴:
  chain_with_history = RunnableWithMessageHistory(
      chain,
      get_session_history,        # 세션 히스토리 반환 함수
      input_messages_key="question",
      history_messages_key="chat_history",
  )

  answer = chain_with_history.invoke(
      {"question": "질문"},
      config={"configurable": {"session_id": "user_1"}},
  )

⚠️ 남은 과제: Retriever가 대화 맥락을 모르는 문제
🔜 다음 실습: 04_history_aware_retrieval.py (히스토리 인식 검색)
""")
