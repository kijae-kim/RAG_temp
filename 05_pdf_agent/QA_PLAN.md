# 05_pdf_agent QA 계획서

> **대상 논문:** LSTM.pdf (Hochreiter & Schmidhuber, 1997)
> **테스트 환경:** FastAPI 서버 (port 8765) + llama3.2:3b + paraphrase-multilingual-MiniLM-L12-v2
> **특이사항:** 영어 논문 → 한국어 질문 → 한국어 답변 (교차 언어)

---

## 테스트 방법

```bash
# 기본 curl 템플릿
curl -s -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "<질문>", "session_id": "qa_test"}'
```

---

## 판단 기준

| 항목 | 합격 | 불합격 |
|------|------|--------|
| **Faithfulness** | 논문 내용에 근거한 답변 | 논문에 없는 내용 생성 (hallucination) |
| **Relevancy** | 질문에 직접 답변 | 관련 없는 내용 나열 |
| **Language** | 한국어로 답변 | 영어 혼용 과다 |
| **Sources** | 출처 page 포함 | sources 빈 배열 |
| **Intent** | 의도 분류 정확 | qa 질문을 summarize로 분류 등 |

---

## QA 테스트 케이스

### Category 1 — 사실 확인 (qa intent 기대)

논문에 명시된 사실을 직접 묻는 질문. **Faithfulness** 집중 평가.

| # | 질문 | 기대 답변 핵심 | 합격 기준 |
|---|------|--------------|-----------|
| Q1 | LSTM이 뭐야? | Long Short-Term Memory, 장기 의존성 학습 | LSTM 정의 + 구조 포함 |
| Q2 | LSTM은 누가 만들었어? | Hochreiter & Schmidhuber, 1997 | 저자명 + 연도 정확 |
| Q3 | LSTM의 gate가 몇 개야? | forget gate, input gate, output gate (3개) | 3개 명시 |
| Q4 | vanishing gradient problem이 뭐야? | 역전파 시 gradient가 소실되는 문제 | 정의 + LSTM의 해결 방식 포함 |
| Q5 | memory cell이 하는 역할이 뭐야? | 장기 정보 저장, CEC (Constant Error Carousel) | CEC 또는 장기 기억 역할 언급 |

---

### Category 2 — 개념 설명 (explain intent 기대)

"~란?", "~을 설명해줘" 형태. **의도 분류 정확도 + 단계적 설명** 평가.

| # | 질문 | 기대 intent | 기대 답변 핵심 | 합격 기준 |
|---|------|-------------|--------------|-----------|
| Q6 | forget gate를 설명해줘 | explain | 이전 cell state를 얼마나 잊을지 결정 | 핵심 정의 + 수식 or 작동 원리 포함 |
| Q7 | BPTT란 뭐야? | explain | Backpropagation Through Time | 정의 + vanishing gradient와 연결 |
| Q8 | CEC가 뭔지 설명해줘 | explain | Constant Error Carousel, gradient 유지 | CEC 역할 + LSTM에서의 위치 |
| Q9 | input gate와 output gate의 차이가 뭐야? | explain | input: 새 정보 저장 여부, output: cell state 출력 여부 | 두 gate 각각의 역할 비교 |

---

### Category 3 — 비교·분석 (qa intent 기대)

논문에서 다루는 비교 실험 결과 질문.

| # | 질문 | 기대 답변 핵심 | 합격 기준 |
|---|------|--------------|-----------|
| Q10 | LSTM이 기존 RNN보다 나은 이유가 뭐야? | vanishing gradient 해결, 장기 의존성 학습 가능 | 구체적 이유 2개 이상 |
| Q11 | 논문에서 LSTM과 비교한 다른 방법들은 뭐야? | RTRL, Elman net, recurrent cascade-correlation | 최소 2개 언급 |
| Q12 | LSTM 실험에서 어떤 task들을 썼어? | embedded Reber grammar, adding problem 등 | 실험 task명 1개 이상 |

---

### Category 4 — 요약 (summarize intent 기대)

"요약해줘", "핵심이 뭐야" 형태. **의도 분류 + 구조적 요약** 평가.

| # | 질문 | 기대 intent | 합격 기준 |
|---|------|-------------|-----------|
| Q13 | 이 논문 핵심이 뭐야? | summarize | 연구 목적·방법·결론 모두 포함, 3문장 이상 |
| Q14 | 논문 결론 요약해줘 | summarize | LSTM의 기여점 + 향후 연구 방향 포함 |

---

### Category 5 — 퀴즈 (quiz intent 기대)

"퀴즈 내줘", "문제 출제해줘" 형태. **의도 분류 + 문제 형식** 평가.

| # | 질문 | 기대 intent | 합격 기준 |
|---|------|-------------|-----------|
| Q15 | LSTM 관련 퀴즈 내줘 | quiz | 문제 + 선택지 4개 + 정답 + 해설 포함 |
| Q16 | vanishing gradient에 대한 문제 출제해줘 | quiz | 문제 형식 준수 + 논문 기반 |

---

### Category 6 — 경계 케이스 (Edge Case)

논문 범위 밖 질문 또는 모호한 질문. **Hallucination 방지** 평가.

| # | 질문 | 기대 답변 방향 | 합격 기준 |
|---|------|--------------|-----------|
| Q17 | GPT가 뭐야? | 논문에 없는 내용임을 언급 | "이 논문에서는 다루지 않는다" 또는 "정보를 찾을 수 없다" |
| Q18 | LSTM을 PyTorch로 구현하는 법 알려줘 | 논문은 구현 코드 없음을 언급 | 코드를 만들어내지 않음 |
| Q19 | 저자가 몇 살이야? | 논문에 없는 정보 | hallucination 없이 모른다고 답변 |

---

## 결과 기록 양식

테스트 후 아래 표에 결과 기록:

| # | 질문 | intent 분류 | 답변 품질 (1~5) | Faithfulness | sources | 비고 |
|---|------|-------------|----------------|--------------|---------|------|
| Q1 | LSTM이 뭐야? | explain (기대: qa) ⚠️ 오분류 | 4 | ✅ | ✅ p.1,27,30 | 내용은 정확, 3단계 구조로 답변 |
| Q2 | LSTM은 누가 만들었어? | qa ✅ | 4 | ✅ | ✅ p.1,26,45 | 저자 풀네임·연도 정확 |
| Q3 | LSTM의 gate가 몇 개야? | quiz ⚠️ 오분류 | 3 | ✅ | ✅ p.1,15,42 | "몇 개야?" → quiz로 오분류, 퀴즈 형식으로 답변 |
| Q4 | vanishing gradient problem이 뭐야? | explain ✅ | 4 | ✅ | ✅ p.1,5,45 | 정의+원리+LSTM 해결책 포함 |
| Q5 | memory cell이 하는 역할이 뭐야? | explain ✅ | 4 | ✅ | ✅ p.11,1,42 | CEC 역할 설명 포함 |
| Q6 | forget gate를 설명해줘 | explain ✅ | 4 | ✅ | ✅ p.26,1,42 | 3단계 구조로 정확히 설명 |
| Q7 | BPTT란 뭐야? | explain ✅ | 4 | ✅ | ✅ p.1,30,33 | 정의+vanishing gradient 연결 포함 |
| Q8 | CEC가 뭔지 설명해줘 | qa ⚠️ 오분류 | 2 | ❌ | ✅ p.1,33,30 | CEC를 "Cell Embedding and Connectivity"로 hallucination (실제: Constant Error Carousel) |
| Q9 | input gate와 output gate의 차이가 뭐야? | explain ✅ | 4 | ✅ | ✅ p.30,29,9 | 두 gate 역할 비교 상세 |
| Q10 | LSTM이 기존 RNN보다 나은 이유가 뭐야? | summarize ⚠️ 오분류 | 3 | ✅ | ✅ p.42,1,30 | 내용은 맞으나 요약 형식으로 답변 |
| Q11 | 논문에서 LSTM과 비교한 다른 방법들은 뭐야? | summarize ⚠️ 오분류 | 3 | ✅ | ✅ p.1,33,14 | 비교 방법 일부 누락, 요약 형식 |
| Q12 | LSTM 실험에서 어떤 task들을 썼어? | summarize ⚠️ 오분류 | 2 | ❌ | ✅ p.26,30,1 | 실험 task명 미언급, 논문 요약으로 대체 |
| Q13 | 이 논문 핵심이 뭐야? | summarize ✅ | 4 | ✅ | ✅ p.30,1,33 | 연구 목적·방법·결론 포함 |
| Q14 | 논문 결론 요약해줘 | summarize ✅ | 3 | ✅ | ✅ p.30,1,33 | Q13과 동일 답변 출력 (세션 히스토리 영향) |
| Q15 | LSTM 관련 퀴즈 내줘 | quiz ✅ | 4 | ✅ | ✅ p.1,9,30 | 문제+선택지 4개+정답+해설 형식 정확 |
| Q16 | vanishing gradient에 대한 문제 출제해줘 | quiz ✅ | 4 | ✅ | ✅ p.1,27,42 | 퀴즈 형식 정확, 논문 근거 |
| Q17 | GPT가 뭐야? | explain ❌ | 1 | ❌ | ✅ p.14,37,25 | 대형 Hallucination: GPT를 17,000자로 상세 설명 (논문 외 내용) |
| Q18 | LSTM을 PyTorch로 구현하는 법 알려줘 | summarize ⚠️ | 2 | ❌ | ✅ p.12,31,20 | PyTorch 언급 없이 논문 요약으로 대체 |
| Q19 | 저자가 몇 살이야? | qa ✅ | 5 | ✅ | ✅ p.3,13 | "문서에서 찾을 수 없습니다" 정확히 답변, hallucination 없음 |

**답변 품질 기준:**
- 5: 완벽, 논문 근거 + 한국어 자연스러움
- 4: 핵심 내용 포함, 사소한 누락
- 3: 일부 맞으나 중요 내용 누락
- 2: 논문과 다른 내용 혼입
- 1: Hallucination 또는 무관한 답변

---

## 실행 순서

```bash
# 1. 서버 상태 확인
curl -s http://localhost:8765/api/status | python3 -m json.tool

# 2. Q1부터 순서대로 — intent 확인 포인트
#    data: {"type":"intent", "content":"qa"} 줄을 주목

# 3. /api/analyze 실행 (Category 2~4 전에 권장)
curl -s -X POST http://localhost:8765/api/analyze

# 4. /api/session으로 questions_asked 증가 확인
curl -s http://localhost:8765/api/session | python3 -m json.tool
```
