"""
Day 1-2: LangChain 기초
05. 종합 실습 - 간단한 챗봇 만들기

학습 목표:
- 지금까지 배운 내용을 조합하여 실제 동작하는 챗봇 구현
- 대화 히스토리 관리
- 스트리밍 응답

🎯 실습: 특정 역할을 수행하는 AI 어시스턴트

사용 모델: Ollama (llama3.2:3b)
"""

from dotenv import load_dotenv

load_dotenv()

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

# ============================================================
# 1. 역할 기반 챗봇 클래스
# ============================================================

class RolePlayChatbot:
    """역할을 수행하는 대화형 챗봇"""

    def __init__(self, role: str, model: str = "llama3.2:3b"):
        self.role = role
        self.history = []

        # Ollama 모델 초기화
        self.llm = ChatOllama(model=model, temperature=0.7)

        # 프롬프트 템플릿 (대화 히스토리 포함)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {role}.
Follow these guidelines:
1. Be helpful and professional.
2. Answer clearly and concisely.
3. If you don't know something, say so honestly.
4. Use examples when helpful."""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}")
        ])

        # 체인 구성
        self.chain = self.prompt | self.llm | StrOutputParser()

    def chat(self, question: str, stream: bool = True) -> str:
        """질문에 답변하고 히스토리에 저장"""

        if stream:
            # 스트리밍 응답
            response = ""
            print("\n🤖 ", end="")
            for chunk in self.chain.stream({
                "role": self.role,
                "history": self.history,
                "question": question
            }):
                print(chunk, end="", flush=True)
                response += chunk
            print()
        else:
            # 일반 응답
            response = self.chain.invoke({
                "role": self.role,
                "history": self.history,
                "question": question
            })

        # 대화 히스토리 저장
        self.history.append(HumanMessage(content=question))
        self.history.append(AIMessage(content=response))

        return response

    def clear_history(self):
        """대화 히스토리 초기화"""
        self.history = []
        print("🔄 대화 히스토리가 초기화되었습니다.")

    def show_history(self):
        """대화 히스토리 출력"""
        print("\n📜 대화 히스토리:")
        for i, msg in enumerate(self.history):
            role = "👤" if isinstance(msg, HumanMessage) else "🤖"
            print(f"  {role} {msg.content[:50]}{'...' if len(msg.content) > 50 else ''}")


# ============================================================
# 2. 대화 루프
# ============================================================

def main():
    print("=" * 60)
    print("🎭 역할 기반 AI 챗봇 (Ollama)")
    print("=" * 60)

    # 역할 선택
    print("\n역할을 선택하세요:")
    print("1. Python Tutor")
    print("2. English Teacher")
    print("3. Career Coach")
    print("4. 직접 입력")

    choice = input("\n선택 (1-4): ").strip()

    roles = {
        "1": "a Python programming tutor who explains concepts clearly with code examples",
        "2": "an English teacher who helps with grammar and natural expressions",
        "3": "a career coach with 10 years of IT industry experience, helping with resumes and interviews"
    }

    if choice in roles:
        role = roles[choice]
    elif choice == "4":
        role = input("원하는 역할을 입력하세요: ").strip()
    else:
        role = roles["1"]

    # 챗봇 초기화
    chatbot = RolePlayChatbot(role=role)
    print(f"\n✅ 챗봇이 준비되었습니다!")
    print(f"역할: {role[:50]}...")
    print("\n명령어: 'quit' (종료), 'clear' (히스토리 초기화), 'history' (히스토리 보기)")
    print("-" * 60)

    # 대화 루프
    while True:
        try:
            question = input("\n👤 질문: ").strip()

            if not question:
                continue
            elif question.lower() == 'quit':
                print("👋 종료합니다!")
                break
            elif question.lower() == 'clear':
                chatbot.clear_history()
                continue
            elif question.lower() == 'history':
                chatbot.show_history()
                continue

            chatbot.chat(question)

        except KeyboardInterrupt:
            print("\n👋 종료합니다!")
            break


if __name__ == "__main__":
    main()
