"""
Day 5-6: Retriever 전략 & 대화형 RAG
04. History-Aware Retrieval - 히스토리 인식 검색 + 완전한 대화형 RAG

학습 목표:
- 03의 한계 해결: 검색 단계에서도 대화 맥락 활용
- 질문 재작성(contextualize) 원리 이해
- create_history_aware_retriever로 히스토리 인식 Retriever 생성
- create_retrieval_chain + RunnableWithMessageHistory로 완전한 대화형 RAG 구현

핵심 개념:
  "그것의 정확도?" → (히스토리 참조) → "CNN 모델의 정확도?"
  → Retriever가 정확한 문서 검색!

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

vectorstore = FAISS.from_documents(docs, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

print(f"PDF: {len(pages)}페이지 → {len(docs)}개 청크 → FAISS 저장 완료")

from langchain_ollama import ChatOllama
llm = ChatOllama(model="llama3.2:3b", temperature=0)

# ============================================================
# 1. 문제 재확인: 검색 단계의 맥락 부재
# ============================================================
print("\n" + "=" * 60)
print("1. 문제 재확인: 검색 단계의 맥락 부재")
print("=" * 60)

print("""
03에서 확인한 문제:
  질문: "What was its accuracy?"

  현재 (03):
    "What was its accuracy?" → Retriever → ??? (its가 뭔지 모름)
    LLM은 히스토리로 이해하지만, 검색 결과가 부정확

  해결 (04, 이번 실습):
    "What was its accuracy?"
    → (히스토리 참조) → "What was the CNN model's accuracy?"
    → Retriever → 정확한 문서 검색!
""")

# 실제 검색 비교
print("📌 검색 비교:")
vague_results = retriever.invoke("What was its accuracy?")
clear_results = retriever.invoke("What was the CNN model's accuracy?")

print(f"\n  모호한 쿼리 ('its accuracy'):")
for i, doc in enumerate(vague_results[:2], 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"    {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

print(f"\n  명확한 쿼리 ('CNN model accuracy'):")
for i, doc in enumerate(clear_results[:2], 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"    {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

print("\n  → 명확한 쿼리가 더 관련성 높은 문서를 검색!")

# ============================================================
# 2. 질문 재작성 원리 (Contextualize)
# ============================================================
print("\n" + "=" * 60)
print("2. 질문 재작성 원리 (Contextualize)")
print("=" * 60)

print("""
Contextualize 프롬프트:
  - 대화 히스토리를 참고하여 후속 질문을 독립적인 질문으로 재작성
  - 대화 맥락 없이도 이해할 수 있는 질문으로 변환
  - 이 재작성된 질문으로 Retriever가 검색
""")

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

# 질문 재작성 프롬프트
contextualize_prompt = ChatPromptTemplate.from_messages([
    ("system", """Given a chat history and the latest user question \
which might reference context in the chat history, \
formulate a standalone question which can be understood \
without the chat history. Do NOT answer the question, \
just reformulate it if needed and otherwise return it as is."""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# 질문 재작성 체인 (데모용)
rewrite_chain = contextualize_prompt | llm | StrOutputParser()

# 재작성 데모
demo_history = [
    HumanMessage(content="What deep learning model was used?"),
    AIMessage(content="The paper uses a CNN (Convolutional Neural Network) model."),
]

demo_questions = [
    "What was its accuracy?",
    "What features did it use?",
    "How does it compare to other methods?",
]

print("📌 대화 히스토리:")
for msg in demo_history:
    role = "사용자" if isinstance(msg, HumanMessage) else "AI"
    print(f"  [{role}] {msg.content}")

print(f"\n📌 질문 재작성 결과:")
for q in demo_questions:
    rewritten = rewrite_chain.invoke({
        "chat_history": demo_history,
        "input": q,
    })
    print(f"  원본:   \"{q}\"")
    print(f"  재작성: \"{rewritten.strip()}\"\n")

# ============================================================
# 3. create_history_aware_retriever
# ============================================================
print("=" * 60)
print("3. create_history_aware_retriever")
print("=" * 60)

print("""
create_history_aware_retriever:
  - contextualize 프롬프트 + LLM + Retriever를 하나로 결합
  - 히스토리가 있으면: 질문 재작성 → 검색
  - 히스토리가 없으면: 원본 질문 그대로 검색

  ⚠️ 주의: 입력 키가 "input"이어야 함 ("question" 아님!)
""")

from langchain_classic.chains import create_history_aware_retriever

# 히스토리 인식 Retriever 생성
history_aware_retriever = create_history_aware_retriever(
    llm,
    retriever,
    contextualize_prompt,
)

# 테스트: 히스토리 없이 (첫 질문)
print("📌 히스토리 없이 (첫 질문):")
result_no_history = history_aware_retriever.invoke({
    "input": "What deep learning model was used?",
    "chat_history": [],
})
print(f"  검색 결과: {len(result_no_history)}개")
for i, doc in enumerate(result_no_history[:2], 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

# 테스트: 히스토리 있을 때 (후속 질문)
print(f"\n📌 히스토리 있을 때 (후속 질문):")
result_with_history = history_aware_retriever.invoke({
    "input": "What was its accuracy?",
    "chat_history": demo_history,
})
print(f"  검색 결과: {len(result_with_history)}개")
for i, doc in enumerate(result_with_history[:2], 1):
    page = int(doc.metadata.get("page", 0)) + 1
    print(f"  {i}. p{page}: {doc.page_content[:70].replace(chr(10), ' ')}...")

print("\n  → 히스토리를 참조하여 'its accuracy' → 'CNN model accuracy'로 재작성 후 검색!")

# ============================================================
# 4. 완전한 대화형 RAG (create_retrieval_chain + History)
# ============================================================
print("\n" + "=" * 60)
print("4. 완전한 대화형 RAG 파이프라인")
print("=" * 60)

print("""
create_retrieval_chain:
  - history_aware_retriever + QA 체인을 하나로 결합
  - 반환값: {"input": ..., "chat_history": ..., "context": ..., "answer": ...}

RunnableWithMessageHistory:
  - 세션별 자동 히스토리 관리 추가
  - output_messages_key="answer" 설정 필수 (딕셔너리 반환이므로)
""")

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

# QA 프롬프트 (검색된 문서 기반 답변)
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful research assistant. Answer the question based on the context below.
If you cannot find the answer in the context, say "The context does not contain this information."
Answer in Korean.

Context:
{context}"""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# QA 체인 생성
qa_chain = create_stuff_documents_chain(llm, qa_prompt)

# Retrieval 체인 = History-Aware Retriever + QA 체인
rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

# 세션 히스토리 관리
session_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

# RunnableWithMessageHistory로 감싸기
conversational_rag = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",  # 딕셔너리 반환 시 필수
)

print("완전한 대화형 RAG 체인 구조:")
print("""
  질문 + 히스토리 ──→ 질문 재작성 (contextualize)
                          │
                     재작성된 질문 ──→ Retriever ──→ 관련 문서
                                                       │
  히스토리 + 질문 + 문서 ──→ QA 프롬프트 ──→ LLM ──→ 답변
                                                       │
                                               히스토리에 자동 저장
""")

# 멀티턴 대화 테스트
session_id = "test_session"

questions = [
    "What deep learning model was used in this study?",
    "What was its accuracy?",
    "What input features did it use?",
    "How was the training data collected?",
]

for i, question in enumerate(questions, 1):
    print(f"\n{'─' * 60}")
    print(f"❓ 질문 {i}: {question}")
    print(f"{'─' * 60}")

    result = conversational_rag.invoke(
        {"input": question},
        config={"configurable": {"session_id": session_id}},
    )

    print(f"\n💬 답변:\n{result['answer']}")

    # 검색된 컨텍스트 출처 표시
    if "context" in result:
        context_pages = [int(d.metadata.get("page", 0)) + 1 for d in result["context"]]
        print(f"\n📚 참조 페이지: {context_pages}")

# 히스토리 확인
print(f"\n{'─' * 60}")
print("📌 전체 대화 히스토리:")
print(f"{'─' * 60}")
stored = get_session_history(session_id)
for msg in stored.messages:
    role = "🧑 사용자" if isinstance(msg, HumanMessage) else "🤖 AI"
    content = msg.content[:120] + "..." if len(msg.content) > 120 else msg.content
    print(f"  {role}: {content}")

# ============================================================
# 03 vs 04 비교
# ============================================================
print("\n" + "=" * 60)
print("03 vs 04 비교")
print("=" * 60)

print("""
┌─────────────────────┬────────────────────────────┬────────────────────────────┐
│                     │ 03 (기본 대화형)           │ 04 (히스토리 인식)         │
├─────────────────────┼────────────────────────────┼────────────────────────────┤
│ LLM 히스토리        │ ✅ 있음                    │ ✅ 있음                    │
│ 검색 히스토리       │ ❌ 없음 (stateless)        │ ✅ 질문 재작성 후 검색     │
│ "its accuracy?" 시  │ "its"로 검색 → 부정확      │ "CNN accuracy"로 검색 → 정확│
│ 핵심 API            │ RunnableWithMessageHistory  │ + create_history_aware_    │
│                     │                            │   retriever                │
│ 반환 형태           │ 문자열                     │ {"answer", "context"} 딕셔너리│
└─────────────────────┴────────────────────────────┴────────────────────────────┘
""")

# ============================================================
# 최종 정리
# ============================================================
print("=" * 60)
print("✅ History-Aware 대화형 RAG 완성!")
print("=" * 60)

print("""
📌 오늘 배운 내용:
  - contextualize 프롬프트: 후속 질문을 독립 질문으로 재작성
  - create_history_aware_retriever: 히스토리 인식 Retriever
  - create_retrieval_chain: Retriever + QA 체인 통합
  - create_stuff_documents_chain: 문서들을 프롬프트에 주입
  - output_messages_key="answer": 딕셔너리 반환 시 필수 설정

📌 핵심 코드 패턴:
  # 1. 히스토리 인식 Retriever
  history_aware_retriever = create_history_aware_retriever(
      llm, retriever, contextualize_prompt
  )

  # 2. QA 체인
  qa_chain = create_stuff_documents_chain(llm, qa_prompt)

  # 3. Retrieval 체인
  rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

  # 4. 히스토리 관리 추가
  conversational_rag = RunnableWithMessageHistory(
      rag_chain, get_session_history,
      input_messages_key="input",
      history_messages_key="chat_history",
      output_messages_key="answer",
  )

🔜 다음 실습: 05_day5_practice.py (종합 실습 - 인터랙티브 챗봇)
""")
