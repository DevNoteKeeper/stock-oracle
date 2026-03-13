import requests
import json


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"


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
    """스트리밍 방식으로 분석 (실시간 출력용)"""

    prompt = build_prompt(data)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000,
                    "repeat_penalty": 1.2,
                    "top_p": 0.9,
                },
            },
            stream=True,
            timeout=180,
        )

        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("response", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break

    except requests.exceptions.ConnectionError:
        yield "❌ Ollama가 실행되지 않고 있어요. 터미널에서 'ollama serve' 를 먼저 실행해주세요."
    except requests.exceptions.Timeout:
        yield "❌ 분석 시간이 초과됐어요. 다시 시도해주세요."
    except Exception as e:
        yield f"❌ 오류: {str(e)}"


def analyze(data: dict) -> str:
    """단일 응답 방식 (테스트용)"""

    prompt = build_prompt(data)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000,
                    "repeat_penalty": 1.2,
                    "top_p": 0.9,
                },
            },
            timeout=180,
        )

        if response.status_code == 200:
            return response.json().get("response", "분석 결과를 가져올 수 없어요.")
        else:
            return f"Ollama 오류: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return "❌ Ollama가 실행되지 않고 있어요."
    except Exception as e:
        return f"❌ 오류: {str(e)}"


# 테스트
if __name__ == "__main__":
    test_data = {
        "ticker": "005930.KS",
        "company_name": "삼성전자",
        "country": "한국",
        "stock": {
            "current_price": 74000,
            "change": -500,
            "change_pct": -0.67,
            "high_52w": 88800,
            "low_52w": 66600,
            "volume": 15000000,
        },
        "market_indicators": {
            "kospi": {"price": 2650, "change_pct": -0.3},
            "usd_krw": {"price": 1350, "change_pct": 0.2},
            "oil_wti": {"price": 78.5, "change_pct": -1.1},
            "sp500_futures": {"price": 5200, "change_pct": 0.1},
            "nasdaq_futures": {"price": 18000, "change_pct": 0.2},
            "gold": {"price": 2300, "change_pct": 0.3},
        },
        "investor_trading": {
            "available": True,
            "5day_summary": {
                "foreign_net": -25000000,
                "institution_net": 15000000,
            },
            "latest": {
                "date": "2026-03-13",
                "foreign": -5000000,
                "institution": 3000000,
            },
            "history": [
                {"date": "2026-03-09", "foreign": -6000000, "institution": 4000000},
                {"date": "2026-03-10", "foreign": -4000000, "institution": 2000000},
                {"date": "2026-03-11", "foreign": -5000000, "institution": 3000000},
                {"date": "2026-03-12", "foreign": -5000000, "institution": 3000000},
                {"date": "2026-03-13", "foreign": -5000000, "institution": 3000000},
            ],
        },
        "news": {"articles": [{"title": "삼성전자, 반도체 수출 증가세 지속"}]},
    }

    print("🤖 AI 분석 중...\n")
    for token in analyze_stream(test_data):
        print(token, end="", flush=True)
    print("\n\n✅ 분석 완료")