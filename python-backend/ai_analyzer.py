import requests
import json
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

# ── 키 목록 로드 ──────────────────────────────────────────────────
def _load_groq_keys() -> list:
    keys = []
    for i in range(1, 4):
        k = os.getenv(f"GROQ_API_KEY_{i}")
        if k and k.strip():
            keys.append(k.strip())
    # GROQ_API_KEY 단일 키도 지원 (중복 제거)
    single = os.getenv("GROQ_API_KEY")
    if single and single.strip() and single.strip() not in keys:
        keys.append(single.strip())
    return keys

GROQ_KEYS = _load_groq_keys()
_key_index = 0   # 현재 사용 중인 키 인덱스

_keys=[
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]

_keys=[k for k in _keys if k] # remove None

def get_groq_key():
    """랜덤으로 키 선택"""
    return random.choice(_keys) if _keys else None
def _next_key() -> str | None:
    """다음 키로 로테이션"""
    global _key_index
    if not GROQ_KEYS:
        return None
    _key_index = (_key_index + 1) % len(GROQ_KEYS)
    return GROQ_KEYS[_key_index]

def _current_key() -> str | None:
    if not GROQ_KEYS:
        return None
    return GROQ_KEYS[_key_index % len(GROQ_KEYS)]

def _is_rate_limit(status_code: int, text: str) -> bool:
    return status_code == 429 or "rate_limit" in text.lower() or "too many" in text.lower()



def build_prompt(data: dict) -> str:
    """분석 프롬프트 생성"""

    stock = data.get("stock", {})
    indicators = data.get("market_indicators", {})
    news = data.get("news", {})
    investor = data.get("investor_trading", {})
    company_name = data.get("company_name", data.get("ticker"))
    country = data.get("country", "")

    # 시장 지표
    kospi = indicators.get("kospi", {})
    usd_krw = indicators.get("usd_krw", {})
    oil = indicators.get("oil_wti", {})
    sp500_futures = indicators.get("sp500_futures", {})
    nasdaq_futures = indicators.get("nasdaq_futures", {})
    gold = indicators.get("gold", {})

    # 뉴스 텍스트
    news_text = ""
    for article in news.get("articles", [])[:5]:
        title = article.get("title", "")
        desc = article.get("description", "")
        if title:
            news_text += f"- {title}\n"
            if desc:
                news_text += f"  {desc}\n"
    if not news_text:
        news_text = "관련 뉴스 없음"

    # 외국인/기관 거래량 텍스트
    investor_text = ""
    if investor.get("available"):
        summary = investor.get("5day_summary", {})
        history = investor.get("history", [])

        foreign_net = summary.get("foreign_net", 0)
        institution_net = summary.get("institution_net", 0)

        def direction(val):
            if val > 0:
                return f"+{val:,}주 (순매수)"
            elif val < 0:
                return f"{val:,}주 (순매도)"
            else:
                return "0주 (중립)"

        investor_text = f"""- 최근 5일 누적 순매수
  · 외국인: {direction(foreign_net)}
  · 기관:   {direction(institution_net)}

- 일별 상세 (최근 5거래일)
"""
        for d in history:
            investor_text += f"  {d['date']}: 외국인 {direction(d['foreign'])}, 기관 {direction(d['institution'])}\n"

        if foreign_net > 0 and institution_net > 0:
            investor_text += "\n  → 외국인·기관 동반 순매수 (강한 매수 신호)"
        elif foreign_net < 0 and institution_net < 0:
            investor_text += "\n  → 외국인·기관 동반 순매도 (강한 매도 신호)"
        elif foreign_net > 0 and institution_net < 0:
            investor_text += "\n  → 외국인 순매수, 기관 순매도 (혼조세)"
        elif foreign_net < 0 and institution_net > 0:
            investor_text += "\n  → 외국인 순매도, 기관 순매수 (혼조세)"
    else:
        investor_text = f"데이터 없음 ({investor.get('reason', '')})"

    prompt = f"""당신은 15년 경력의 전문 주식 애널리스트입니다.
아래 데이터를 바탕으로 내일 {company_name} 주가를 분석하고 예측해주세요.
각 항목을 반드시 구분해서 작성하고, 데이터에 근거한 구체적인 분석을 해주세요.

═══════════════════════════════════
분석 대상: {company_name} ({country}) / {data.get("ticker")}
═══════════════════════════════════

【현재 주가】
- 현재가: {stock.get("current_price"):,}원
- 전일 대비: {stock.get("change"):,}원 ({stock.get("change_pct")}%)
- 52주 최고: {stock.get("high_52w"):,}원
- 52주 최저: {stock.get("low_52w"):,}원
- 오늘 거래량: {stock.get("volume"):,}주

【시장 지표】
- 코스피:        {kospi.get("price")} ({kospi.get("change_pct")}%)
- 달러/원 환율:  {usd_krw.get("price")}원 ({usd_krw.get("change_pct")}%)
- WTI 유가:     ${oil.get("price")} ({oil.get("change_pct")}%)
- S&P500 선물:  {sp500_futures.get("price")} ({sp500_futures.get("change_pct")}%)
- 나스닥 선물:   {nasdaq_futures.get("price")} ({nasdaq_futures.get("change_pct")}%)
- 금:           ${gold.get("price")} ({gold.get("change_pct")}%)

【외국인/기관 거래 동향】
{investor_text}

【최근 뉴스 및 이슈】
{news_text}

═══════════════════════════════════
아래 6가지 항목을 순서대로 분석해주세요:

1. 【종합 시황 분석】
   - 위 지표들이 {company_name}에 미치는 영향을 구체적으로 설명

2. 【긍정 요인】
   - 주가 상승 가능성을 높이는 요인들을 나열

3. 【부정 요인】
   - 주가 하락 위험 요인들을 나열

4. 【외국인/기관 수급 분석】
   - 외국인과 기관의 매매 동향이 의미하는 바를 분석
   - 과거 유사한 수급 패턴에서 주가가 어떻게 움직였는지

5. 【내일 주가 예측】
   - 예측: 상승 / 하락 / 보합 중 하나
   - 예상 등락률: ex) -1% ~ +1%
   - 예측 근거: 핵심 이유 2~3가지

6. 【예측 신뢰도】
   - 신뢰도: 낮음 / 보통 / 높음
   - 신뢰도 판단 이유
   - 주의해야 할 변수

한국어로 작성해주세요.
═══════════════════════════════════"""

    return prompt


def analyze_stream(data: dict):
    """
    스트리밍 분석.
    rate limit(429) 발생 시 다음 키로 자동 전환, 모든 키 소진 시 에러 메시지.
    """
    prompt = build_prompt(data)

    if not GROQ_KEYS:
        yield "❌ GROQ_API_KEY가 설정되지 않았어요. .env 파일을 확인해주세요."
        return

    tried = set()

    while len(tried) < len(GROQ_KEYS):
        key = _current_key()
        if key in tried:
            key = _next_key()
        if key is None or key in tried:
            break
        tried.add(key)

        try:
            response = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {get_groq_key()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                stream=True,
                timeout=120,
            )

            # rate limit 체크 (스트리밍 시작 전)
            if _is_rate_limit(response.status_code, response.text if not response.ok else ""):
                print(f"  ⚠️  키 {GROQ_KEYS.index(key)+1} rate limited → 다음 키로 전환")
                _next_key()
                time.sleep(0.5)
                continue

            if not response.ok:
                yield f"❌ Groq API 오류: {response.status_code}"
                return

            # 정상 스트리밍
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        return
                    try:
                        d = json.loads(chunk)
                        token = d["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except Exception:
                        continue
            return  # 정상 완료

        except requests.exceptions.ConnectionError:
            yield "❌ Groq API에 연결할 수 없어요. 인터넷 연결을 확인해주세요."
            return
        except requests.exceptions.Timeout:
            yield "❌ 분석 시간이 초과됐어요. 다시 시도해주세요."
            return
        except Exception as e:
            # 스트리밍 중 rate limit 에러가 응답 바디로 올 경우
            err_str = str(e)
            if "rate_limit" in err_str.lower() or "429" in err_str:
                print(f"  ⚠️  스트리밍 중 rate limit → 다음 키로 전환")
                _next_key()
                time.sleep(0.5)
                continue
            yield f"❌ 오류: {err_str}"
            return

    # 모든 키 소진
    key_count = len(GROQ_KEYS)
    yield f"❌ 모든 API 키({key_count}개)가 rate limit에 걸렸어요. 잠시 후 다시 시도해주세요."


def analyze(data: dict) -> str:
    """단일 응답 방식 (테스트용). 키 로테이션 포함."""
    prompt = build_prompt(data)

    if not GROQ_KEYS:
        return "❌ GROQ_API_KEY가 설정되지 않았어요."

    tried = set()

    while len(tried) < len(GROQ_KEYS):
        key = _current_key()
        if key in tried:
            key = _next_key()
        if key is None or key in tried:
            break
        tried.add(key)

        try:
            response = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                timeout=120,
            )

            if _is_rate_limit(response.status_code, response.text):
                print(f"  ⚠️  키 {GROQ_KEYS.index(key)+1} rate limited → 다음 키로 전환")
                _next_key()
                time.sleep(0.5)
                continue

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Groq 오류: {response.status_code} {response.text}"

        except Exception as e:
            return f"❌ 오류: {str(e)}"

    return f"❌ 모든 API 키({len(GROQ_KEYS)}개)가 rate limit에 걸렸어요. 잠시 후 다시 시도해주세요."