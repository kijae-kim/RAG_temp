"""
Day 1-2: LangChain 기초
04. Output Parsers (출력 파서)

학습 목표:
- 다양한 OutputParser 종류 이해
- 구조화된 출력 (JSON, Pydantic) 받기
- 실무에서 자주 쓰는 패턴 익히기

사용 모델: Ollama (llama3.2:3b)
"""

from dotenv import load_dotenv
from typing import List

load_dotenv()

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import (
    StrOutputParser,
    JsonOutputParser,
    CommaSeparatedListOutputParser
)
from pydantic import BaseModel, Field

# Ollama 모델 초기화
llm = ChatOllama(model="llama3.2:3b", temperature=0)

# ============================================================
# 1. StrOutputParser (가장 기본)
# ============================================================
print("=" * 50)
print("1. StrOutputParser")
print("=" * 50)

str_parser = StrOutputParser()

chain = (
    ChatPromptTemplate.from_template("Explain {topic} in one sentence.")
    | llm
    | str_parser
)
result = chain.invoke({"topic": "blockchain"})
print(f"결과 (str): {result}")
print(f"타입: {type(result)}")

# ============================================================
# 2. CommaSeparatedListOutputParser
# ============================================================
print("\n" + "=" * 50)
print("2. CommaSeparatedListOutputParser")
print("=" * 50)

list_parser = CommaSeparatedListOutputParser()

# 포맷 지시사항을 프롬프트에 포함
format_instructions = list_parser.get_format_instructions()
print(f"포맷 지시사항:\n{format_instructions}")

prompt = ChatPromptTemplate.from_template(
    "List 5 technologies related to {topic}.\n{format_instructions}"
)

chain = prompt | llm | list_parser

result = chain.invoke({
    "topic": "web development",
    "format_instructions": format_instructions
})
print(f"\n결과: {result}")
print(f"타입: {type(result)}")  # list

# ============================================================
# 3. JsonOutputParser
# ============================================================
print("\n" + "=" * 50)
print("3. JsonOutputParser")
print("=" * 50)

json_parser = JsonOutputParser()

prompt = ChatPromptTemplate.from_template("""
Extract information from the following text and return as JSON.

Text: {text}

Return in this exact format:
{{"name": "name", "age": age_number, "job": "job"}}

Return ONLY the JSON, no other text.
""")

chain = prompt | llm | json_parser

result = chain.invoke({
    "text": "Hi, I'm John Smith, 28 years old, working as a software engineer."
})
print(f"결과: {result}")
print(f"이름: {result.get('name')}, 나이: {result.get('age')}")

# ============================================================
# 4. Pydantic 기반 구조화 출력
# ============================================================
print("\n" + "=" * 50)
print("4. Pydantic 구조화 출력")
print("=" * 50)

# Pydantic 모델 정의
class MovieReview(BaseModel):
    """Movie review analysis result"""
    title: str = Field(description="Movie title")
    sentiment: str = Field(description="Sentiment: positive/negative/neutral")
    score: int = Field(description="Score from 1 to 10")
    keywords: List[str] = Field(description="3 key keywords")

# Pydantic 파서 생성
pydantic_parser = JsonOutputParser(pydantic_object=MovieReview)

print(f"스키마 정보:\n{pydantic_parser.get_format_instructions()[:300]}...")

prompt = ChatPromptTemplate.from_template("""
Analyze the following movie review.

Review: {review}

{format_instructions}

Return ONLY valid JSON.
""")

chain = prompt | llm | pydantic_parser

result = chain.invoke({
    "review": "Inception was amazing! The story was complex but very immersive. A bit hard to understand at first though.",
    "format_instructions": pydantic_parser.get_format_instructions()
})

print(f"\n분석 결과:")
print(f"  제목: {result.get('title')}")
print(f"  감정: {result.get('sentiment')}")
print(f"  점수: {result.get('score')}/10")
print(f"  키워드: {result.get('keywords')}")

# ============================================================
# 5. 수동 JSON 파싱 (Fallback 패턴)
# ============================================================
print("\n" + "=" * 50)
print("5. 수동 JSON 파싱 (Fallback)")
print("=" * 50)

import json
import re

def extract_json(text: str) -> dict:
    """LLM 응답에서 JSON 추출 (로버스트 파싱)"""
    # JSON 블록 찾기
    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"error": "Failed to parse JSON", "raw": text}

# 테스트
test_response = '''Here's the analysis:
{"title": "Inception", "score": 9}
Hope this helps!'''

parsed = extract_json(test_response)
print(f"추출된 JSON: {parsed}")

print("\n✅ Output Parsers 실습 완료!")
print("\n📌 핵심 정리:")
print("  - StrOutputParser: 단순 문자열 (기본)")
print("  - CommaSeparatedListOutputParser: 리스트")
print("  - JsonOutputParser: 딕셔너리")
print("  - Pydantic + JsonOutputParser: 구조화된 출력")
print("  - 수동 파싱: JSON 추출 실패 시 Fallback")
