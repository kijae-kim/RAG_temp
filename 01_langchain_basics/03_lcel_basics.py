"""
Day 1-2: LangChain 기초
03. LCEL (LangChain Expression Language) 마스터

학습 목표:
- 파이프(|) 연산자로 체인 구성
- RunnablePassthrough, RunnableLambda 활용
- invoke, stream, batch 실행 방식 이해

⭐ LCEL은 LangChain의 핵심! 반드시 마스터해야 함

사용 모델: Ollama (llama3.2:3b)
"""

from dotenv import load_dotenv

load_dotenv()

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnablePassthrough,
    RunnableLambda,
    RunnableParallel
)

# Ollama 모델 초기화
llm = ChatOllama(model="llama3.2:3b", temperature=0)

# ============================================================
# 1. 기본 체인 구성: Prompt | Model | OutputParser
# ============================================================
print("=" * 50)
print("1. 기본 LCEL 체인")
print("=" * 50)

prompt = ChatPromptTemplate.from_template(
    "{topic}에 대해 한 문장으로 설명해주세요."
)

# 체인 구성 (파이프 연산자 사용)
# prompt -> llm -> 문자열 파싱
chain = prompt | llm | StrOutputParser()

# 실행
result = chain.invoke({"topic": "Machine Learning"})
print(f"결과: {result}")

# ============================================================
# 2. 스트리밍 출력
# ============================================================
print("\n" + "=" * 50)
print("2. 스트리밍 (실시간 출력)")
print("=" * 50)

prompt2 = ChatPromptTemplate.from_template(
    "List 3 advantages of {topic}. Be concise."
)
chain2 = prompt2 | llm | StrOutputParser()

print("스트리밍 출력:")
for chunk in chain2.stream({"topic": "Python"}):
    print(chunk, end="", flush=True)
print()

# ============================================================
# 3. 배치 처리
# ============================================================
print("\n" + "=" * 50)
print("3. 배치 처리")
print("=" * 50)

topics = [
    {"topic": "JavaScript"},
    {"topic": "Rust"},
    {"topic": "Go"}
]

# 병렬로 여러 입력 처리
results = chain.batch(topics)
for topic, result in zip(topics, results):
    print(f"- {topic['topic']}: {result[:80]}...")

# ============================================================
# 4. RunnablePassthrough (입력 그대로 전달)
# ============================================================
print("\n" + "=" * 50)
print("4. RunnablePassthrough")
print("=" * 50)

# RAG 패턴의 핵심: context는 검색에서, question은 그대로 전달
prompt3 = ChatPromptTemplate.from_template("""
Context: {context}
Question: {question}

Answer the question based on the context above.
""")

# 검색 시뮬레이션 (실제로는 VectorStore에서 검색)
def fake_retriever(query):
    return "Python was created by Guido van Rossum and released in 1991."

# 체인 구성: question은 그대로, context는 retriever에서
chain3 = (
    {
        "context": lambda x: fake_retriever(x["question"]),
        "question": lambda x: x["question"]
    }
    | prompt3
    | llm
    | StrOutputParser()
)

result = chain3.invoke({"question": "When was Python created?"})
print(f"결과: {result}")

# ============================================================
# 5. RunnableLambda (커스텀 함수 체인에 포함)
# ============================================================
print("\n" + "=" * 50)
print("5. RunnableLambda")
print("=" * 50)

def clean_text(text: str) -> str:
    """텍스트 전처리 함수"""
    return text.strip().lower()

def add_prefix(text: str) -> str:
    """접두사 추가"""
    return f"[처리됨] {text}"

# 함수를 체인에 포함
text_chain = (
    RunnableLambda(clean_text)
    | RunnableLambda(add_prefix)
)

result = text_chain.invoke("  Hello World!  ")
print(f"결과: {result}")

# ============================================================
# 6. RunnableParallel (병렬 실행)
# ============================================================
print("\n" + "=" * 50)
print("6. RunnableParallel")
print("=" * 50)

# 하나의 입력으로 여러 작업을 동시에 수행
parallel_chain = RunnableParallel(
    summary=ChatPromptTemplate.from_template(
        "Summarize {topic} in one sentence."
    ) | llm | StrOutputParser(),

    keywords=ChatPromptTemplate.from_template(
        "List 3 keywords for {topic}, separated by commas."
    ) | llm | StrOutputParser()
)

result = parallel_chain.invoke({"topic": "Artificial Intelligence"})
print(f"요약: {result['summary'][:100]}...")
print(f"키워드: {result['keywords'][:100]}...")

# ============================================================
# 7. 체인 시각화
# ============================================================
print("\n" + "=" * 50)
print("7. 체인 구조 확인")
print("=" * 50)

# 체인 구조 출력
print(f"체인 구조:")
print(chain)

# ASCII 그래프
try:
    print(f"\n체인 그래프:\n{chain.get_graph().draw_ascii()}")
except Exception:
    print("(그래프 시각화는 추가 설정 필요)")

print("\n✅ LCEL 기초 실습 완료!")
print("\n📌 핵심 정리:")
print("  - | : 체인 연결 (파이프 연산자)")
print("  - invoke(): 단일 실행")
print("  - stream(): 스트리밍 (실시간 출력)")
print("  - batch(): 병렬 배치 처리")
print("  - RunnablePassthrough: 입력 그대로 전달")
print("  - RunnableLambda: 커스텀 함수 래핑")
print("  - RunnableParallel: 병렬 실행")
