"""
Day 1-2: LangChain 기초
02. PromptTemplate 마스터

학습 목표:
- PromptTemplate vs ChatPromptTemplate 차이 이해
- 변수 바인딩 방법
- 다양한 프롬프트 패턴 실습
"""

from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# ============================================================
# 1. 기본 PromptTemplate
# ============================================================
print("=" * 50)
print("1. 기본 PromptTemplate")
print("=" * 50)

# 방법 1: from_template 사용 (추천)
template1 = PromptTemplate.from_template(
    "{product}에 대한 {length}자 이내의 광고 문구를 작성해주세요."
)

# 변수 확인
print(f"입력 변수: {template1.input_variables}")

# 프롬프트 생성
prompt = template1.format(product="아이폰 16", length="50")
print(f"\n생성된 프롬프트:\n{prompt}")

# 방법 2: 직접 생성
template2 = PromptTemplate(
    input_variables=["country", "food"],
    template="{country}의 대표적인 {food} 요리 3가지를 알려주세요."
)

print(f"\n{template2.format(country='일본', food='면')}")

# ============================================================
# 2. ChatPromptTemplate (대화형)
# ============================================================
print("\n" + "=" * 50)
print("2. ChatPromptTemplate")
print("=" * 50)

# 방법 1: 튜플 리스트 사용 (간단)
chat_template = ChatPromptTemplate.from_messages([
    ("system", "당신은 {role} 전문가입니다. 친절하게 답변해주세요."),
    ("human", "{question}")
])

messages = chat_template.format_messages(
    role="Python 프로그래밍",
    question="리스트 컴프리헨션이 뭔가요?"
)

print("생성된 메시지:")
for msg in messages:
    print(f"  [{msg.type}]: {msg.content[:50]}...")

# 방법 2: MessagePromptTemplate 사용 (더 명시적)
chat_template2 = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "당신은 {language} 번역가입니다."
    ),
    HumanMessagePromptTemplate.from_template(
        "다음을 번역해주세요: {text}"
    )
])

messages2 = chat_template2.format_messages(
    language="영어",
    text="오늘 날씨가 좋네요."
)
print(f"\n번역 프롬프트: {messages2}")

# ============================================================
# 3. MessagesPlaceholder (대화 히스토리용)
# ============================================================
print("\n" + "=" * 50)
print("3. MessagesPlaceholder")
print("=" * 50)

# 대화 히스토리를 포함하는 템플릿
chat_with_history = ChatPromptTemplate.from_messages([
    ("system", "당신은 도움이 되는 AI 어시스턴트입니다."),
    MessagesPlaceholder(variable_name="history"),  # 여기에 이전 대화가 들어감
    ("human", "{question}")
])

# 대화 히스토리 예시
history = [
    HumanMessage(content="안녕하세요"),
    AIMessage(content="안녕하세요! 무엇을 도와드릴까요?"),
    HumanMessage(content="Python 배우고 싶어요"),
    AIMessage(content="좋습니다! Python은 입문자에게 좋은 언어입니다.")
]

messages = chat_with_history.format_messages(
    history=history,
    question="어디서 시작하면 좋을까요?"
)

print("대화 히스토리 포함 메시지:")
for i, msg in enumerate(messages):
    print(f"  {i+1}. [{msg.type}]: {msg.content[:40]}...")

# ============================================================
# 4. 실전 패턴: Few-shot Prompting
# ============================================================
print("\n" + "=" * 50)
print("4. Few-shot Prompting")
print("=" * 50)

few_shot_template = ChatPromptTemplate.from_messages([
    ("system", """당신은 감정 분석 전문가입니다.
텍스트를 분석하고 긍정/부정/중립 중 하나로 분류하세요.

예시:
- "이 제품 정말 좋아요!" -> 긍정
- "별로예요, 실망했습니다" -> 부정
- "그냥 그래요" -> 중립"""),
    ("human", "다음 텍스트를 분석하세요: {text}")
])

result = few_shot_template.format_messages(text="오늘 산 책이 너무 재미있어서 밤새 읽었어요!")
print(f"Few-shot 프롬프트 생성 완료")
print(f"메시지 수: {len(result)}")

# ============================================================
# 5. 프롬프트 저장 및 로드
# ============================================================
print("\n" + "=" * 50)
print("5. 프롬프트 저장/로드")
print("=" * 50)

# JSON으로 저장
template1.save("01_langchain_basics/prompts/product_ad.json")
print("프롬프트 저장 완료: prompts/product_ad.json")

# 로드
from langchain_core.prompts import load_prompt
loaded = load_prompt("01_langchain_basics/prompts/product_ad.json")
print(f"로드된 프롬프트 변수: {loaded.input_variables}")

print("\n✅ PromptTemplate 실습 완료!")
