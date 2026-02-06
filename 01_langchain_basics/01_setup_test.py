"""
Day 1-2: LangChain 기초
01. 환경설정 및 연결 테스트

학습 목표:
- API 키 설정 방법 이해
- LangChain 기본 구조 파악
- 첫 번째 LLM 호출 성공

사용 모델: Ollama (llama3.2:3b) - 로컬 무료 모델
"""

import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# 환경 설정 확인
print("=" * 50)
print("환경 설정 확인")
print("=" * 50)

langsmith_key = os.getenv("LANGCHAIN_API_KEY")
langsmith_tracing = os.getenv("LANGCHAIN_TRACING_V2")

print(f"LangSmith API Key: {'✅ 설정됨' if langsmith_key else '❌ 미설정'}")
print(f"LangSmith Tracing: {'✅ 활성화' if langsmith_tracing == 'true' else '❌ 비활성화'}")

# ============================================================
# 1. Ollama 로컬 모델 테스트
# ============================================================
print("\n" + "=" * 50)
print("Ollama 로컬 모델 테스트 (llama3.2:3b)")
print("=" * 50)

from langchain_ollama import ChatOllama

# ChatOllama 모델 초기화
# temperature: 0 = 결정적, 1 = 창의적
llm = ChatOllama(
    model="llama3.2:3b",  # 로컬 모델
    temperature=0.7
)

# 간단한 호출 테스트
print("\n[테스트 1] 기본 호출")
response = llm.invoke("What is Python? Answer in one sentence.")
print(f"응답: {response.content}")

# ============================================================
# 2. 한국어 테스트
# ============================================================
print("\n[테스트 2] 한국어 응답")
response = llm.invoke("Python의 장점을 3가지만 간단히 알려주세요.")
print(f"응답: {response.content}")

# ============================================================
# 3. LangChain 메시지 타입 이해
# ============================================================
print("\n" + "=" * 50)
print("LangChain 메시지 타입")
print("=" * 50)

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 메시지 리스트로 호출 (ChatML 형식)
messages = [
    SystemMessage(content="You are a helpful Python tutor. Answer concisely."),
    HumanMessage(content="What is a list comprehension?")
]

response = llm.invoke(messages)
print(f"\n시스템 메시지 + 사용자 메시지 조합:")
print(f"응답: {response.content[:200]}...")

# 응답 객체 구조 확인
print(f"\n응답 객체 타입: {type(response)}")
print(f"응답 내용: response.content")
print(f"메타데이터: {response.response_metadata}")

print("\n" + "=" * 50)
print("✅ 설정 테스트 완료!")
print("=" * 50)
print("\n📌 다음 단계: 02_prompt_template.py 실행")
