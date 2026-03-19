"""
backtest.py — StockOracle 백테스트
====================================
사용법:
  python backtest.py --ticker 005930.KS --name 삼성전자 --country 한국 \
                     --start 2025-01-15 --end 2025-03-01 --period tomorrow

  python backtest.py --ticker AAPL --name Apple --country 미국 \
                     --start 2025-02-01 --end 2025-03-10

옵션:
  --ticker    티커 (예: 005930.KS, AAPL)
  --name      회사명
  --country   한국 / 미국 / 일본
  --start     백테스트 시작일 (YYYY-MM-DD)
  --end       백테스트 종료일 (YYYY-MM-DD)
  --period    예측 기간: tomorrow(기본) / week / month
  --interval  테스트 간격 (영업일 기준, 기본 1 = 매일)
  --out       결과 저장 파일 (기본: backtest_result.json)
  --no-ai     AI 호출 없이 데이터 수집만 테스트
  --no-review 틀린 예측 자기분석 생략
  --sleep     AI 호출 간 대기 시간(초, 기본 3)

결과 파일:
  backtest_result.json  — 누적 테스트 결과 (test_id별)
  backtest_result.txt   — 전체 정확도 요약 (누적)
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests as req_lib
import yfinance as yf


# ── 날짜 유틸 ─────────────────────────────────────────────────────────

def next_business_day(dt: datetime) -> datetime:
    d = dt + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d

def business_days_between(start: datetime, end: datetime, interval: int = 1):
    """start~end 사이 영업일을 interval 간격으로 반환"""
    days = []
    cur = start
    while cur.weekday() >= 5:
        cur += timedelta(days=1)
    while cur <= end:
        days.append(cur)
        step = 0
        while step < interval:
            cur += timedelta(days=1)
            if cur.weekday() < 5:
                step += 1
    return days


# ── 과거 날짜 기준 데이터 수집 ────────────────────────────────────────

def get_stock_data_as_of(ticker: str, as_of: datetime) -> dict:
    """as_of 날짜의 종가를 현재가로 사용, 이전 3개월 데이터만 제공"""
    try:
        t = yf.Ticker(ticker)
        end_dt = as_of + timedelta(days=1)
        hist = t.history(
            start=(as_of - timedelta(days=120)).strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
        )
        if hist.empty:
            return {"error": f"'{ticker}' 데이터 없음 (날짜: {as_of.date()})"}

        hist = hist[hist.index.date <= as_of.date()]
        if hist.empty:
            return {"error": f"'{ticker}' 해당 날짜 데이터 없음"}

        latest = hist.iloc[-1]
        prev   = hist.iloc[-2] if len(hist) > 1 else latest
        change     = latest["Close"] - prev["Close"]
        change_pct = (change / prev["Close"]) * 100

        try:
            year_hist = t.history(
                start=(as_of - timedelta(days=365)).strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
            )
            high_52w = float(year_hist["High"].max()) if not year_hist.empty else 0
            low_52w  = float(year_hist["Low"].min())  if not year_hist.empty else 0
        except Exception:
            high_52w = low_52w = 0

        history_30 = hist.tail(30)
        return {
            "ticker":        ticker,
            "current_price": round(float(latest["Close"]), 2),
            "prev_price":    round(float(prev["Close"]), 2),
            "change":        round(float(change), 2),
            "change_pct":    round(float(change_pct), 2),
            "volume":        int(latest["Volume"]),
            "high_52w":      round(high_52w, 2),
            "low_52w":       round(low_52w, 2),
            "history": [
                {
                    "date":   str(idx.date()),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
                for idx, row in history_30.iterrows()
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def get_technicals_as_of(ticker: str, as_of: datetime) -> dict:
    """as_of 이전 데이터로 기술적 지표 계산"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(
            start=(as_of - timedelta(days=200)).strftime("%Y-%m-%d"),
            end=(as_of + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        if hist.empty or len(hist) < 30:
            return {"available": False, "reason": "데이터 부족"}

        hist    = hist[hist.index.date <= as_of.date()]
        closes  = hist["Close"].tolist()
        n       = len(closes)
        cur     = closes[-1]

        def sma(data, p):
            return round(sum(data[-p:]) / p, 2) if len(data) >= p else None

        def ema_series(data, p):
            if len(data) < p: return []
            k = 2 / (p + 1)
            vals = [sum(data[:p]) / p]
            for price in data[p:]:
                vals.append(price * k + vals[-1] * (1 - k))
            return vals

        ma5  = sma(closes, 5)
        ma20 = sma(closes, 20)
        ma60 = sma(closes, 60)

        def calc_rsi(data, p=14):
            if len(data) < p + 1: return None
            deltas = [data[i] - data[i-1] for i in range(1, len(data))]
            gains  = [max(d, 0) for d in deltas]
            losses = [abs(min(d, 0)) for d in deltas]
            ag = sum(gains[:p]) / p
            al = sum(losses[:p]) / p
            for i in range(p, len(gains)):
                ag = (ag * (p-1) + gains[i]) / p
                al = (al * (p-1) + losses[i]) / p
            if al == 0: return 100.0
            return round(100 - 100 / (1 + ag / al), 2)

        rsi = calc_rsi(closes)

        ema12 = ema_series(closes, 12)
        ema26 = ema_series(closes, 26)
        macd_line = signal_line = histogram = None
        if ema12 and ema26:
            min_len   = min(len(ema12), len(ema26))
            macd_vals = [ema12[-min_len + i] - ema26[-min_len + i] for i in range(min_len)]
            if len(macd_vals) >= 9:
                sig         = ema_series(macd_vals, 9)
                macd_line   = round(macd_vals[-1], 4)
                signal_line = round(sig[-1], 4)
                histogram   = round(macd_line - signal_line, 4)

        bb_pct_b = None
        if n >= 20:
            window   = closes[-20:]
            mean     = sum(window) / 20
            std      = (sum((x - mean) ** 2 for x in window) / 20) ** 0.5
            bb_upper = mean + 2 * std
            bb_lower = mean - 2 * std
            band     = bb_upper - bb_lower
            bb_pct_b = round((cur - bb_lower) / band, 4) if band > 0 else 0.5

        def rsi_label(v):
            if v is None: return ""
            if v >= 70: return "과매수"
            if v >= 60: return "강세"
            if v >= 40: return "중립"
            if v >= 30: return "약세"
            return "과매도"

        def macd_label(line, signal):
            if line is None or signal is None: return ""
            if line > 0 and line > signal: return "상승 모멘텀"
            if line > 0: return "상승 둔화"
            if line < signal: return "하락 모멘텀"
            return "하락 둔화"

        return {
            "available":  True,
            "ma5": ma5, "ma20": ma20, "ma60": ma60,
            "rsi": rsi, "rsi_label": rsi_label(rsi),
            "macd_line": macd_line, "signal_line": signal_line,
            "histogram": histogram,
            "macd_label": macd_label(macd_line, signal_line),
            "bb_pct_b": bb_pct_b,
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def get_market_indicators_as_of(as_of: datetime) -> dict:
    """과거 날짜 기준 시장 지표"""
    targets = {
        "kospi":         "^KS11",
        "usd_krw":       "USDKRW=X",
        "oil_wti":       "CL=F",
        "sp500_futures": "ES=F",
        "gold":          "GC=F",
    }
    indicators = {}
    end_dt   = (as_of + timedelta(days=1)).strftime("%Y-%m-%d")
    start_dt = (as_of - timedelta(days=10)).strftime("%Y-%m-%d")
    for key, tkr in targets.items():
        try:
            hist = yf.Ticker(tkr).history(start=start_dt, end=end_dt)
            hist = hist[hist.index.date <= as_of.date()]
            if hist.empty:
                indicators[key] = {}
                continue
            latest  = hist.iloc[-1]
            prev    = hist.iloc[-2] if len(hist) > 1 else latest
            chg_pct = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
            indicators[key] = {
                "price":      round(float(latest["Close"]), 2),
                "change_pct": round(float(chg_pct), 2),
            }
        except Exception:
            indicators[key] = {}
    return indicators


def get_actual_next_price(ticker: str, as_of: datetime) -> dict | None:
    """as_of 다음 영업일 실제 종가 조회 (정답)"""
    target = next_business_day(as_of)
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(
            start=target.strftime("%Y-%m-%d"),
            end=(target + timedelta(days=5)).strftime("%Y-%m-%d"),
        )
        if hist.empty:
            return None
        return {
            "date":  str(hist.index[0].date()),
            "price": round(float(hist.iloc[0]["Close"]), 2),
        }
    except Exception:
        return None


# ── 데이터 조립 ───────────────────────────────────────────────────────

def collect_historical_data(ticker: str, company_name: str, country: str,
                             as_of: datetime, period: str = "tomorrow") -> dict:
    """as_of 날짜 기준으로 과거 데이터만 수집"""
    print(f"    📊 데이터 수집 중... ({as_of.date()})")
    stock      = get_stock_data_as_of(ticker, as_of)
    indicators = get_market_indicators_as_of(as_of)
    technicals = get_technicals_as_of(ticker, as_of)
    return {
        "ticker":            ticker,
        "company_name":      company_name,
        "country":           country,
        "period":            period,
        "collected_at":      as_of.isoformat(),
        "stock":             stock,
        "market_indicators": indicators,
        "technicals":        technicals,
        "financials":        {"available": False, "reason": "백테스트 시 재무 지표 제외"},
        "investor_trading":  {"available": False, "reason": "백테스트 시 수급 데이터 제외"},
        "news":              {"articles": [], "sentiment_summary": {"score": 0},
                              "category_counts": {}, "top_keywords": []},
    }


# ── 시장 급변 override ────────────────────────────────────────────────

def market_override(pred: dict, data: dict) -> tuple[dict, str | None]:
    """외부 시장 급변 시 AI 보합 예측을 방향성으로 보정"""
    if pred["direction"] != "보합":
        return pred, None

    ind       = data.get("market_indicators", {})
    sp500_pct = float(ind.get("sp500_futures", {}).get("change_pct", 0) or 0)
    kospi_pct = float(ind.get("kospi",         {}).get("change_pct", 0) or 0)
    usd_pct   = float(ind.get("usd_krw",        {}).get("change_pct", 0) or 0)
    atr       = (pred["pct_high"] - pred["pct_low"]) / 2

    # 하락 override
    dn_reasons = []
    if sp500_pct <= -1.5: dn_reasons.append(f"S&P500선물 {sp500_pct:+.2f}%")
    if kospi_pct <= -1.5: dn_reasons.append(f"코스피 {kospi_pct:+.2f}%")
    if usd_pct >= 0.8:    dn_reasons.append(f"달러/원 {usd_pct:+.2f}%")
    if dn_reasons and (sp500_pct <= -1.5 or kospi_pct <= -1.5):
        new_pred = dict(pred)
        new_pred["direction"] = "하락"
        new_pred["pct_low"]   = round(-atr * 2, 1)
        new_pred["pct_high"]  = round(-atr * 0.3, 1)
        return new_pred, "시장급락override: " + " / ".join(dn_reasons)

    # 상승 override
    up_reasons = []
    if sp500_pct >= 1.5: up_reasons.append(f"S&P500선물 {sp500_pct:+.2f}%")
    if kospi_pct >= 1.5: up_reasons.append(f"코스피 {kospi_pct:+.2f}%")
    if up_reasons and (sp500_pct >= 1.5 or kospi_pct >= 1.5):
        new_pred = dict(pred)
        new_pred["direction"] = "상승"
        new_pred["pct_low"]   = round(atr * 0.3, 1)
        new_pred["pct_high"]  = round(atr * 2, 1)
        return new_pred, "시장급등override: " + " / ".join(up_reasons)

    return pred, None


# ── AI 예측 파싱 ──────────────────────────────────────────────────────

def parse_prediction(text: str) -> dict | None:
    # 방향: **볼드** 있든 없든, 공백 유연하게
    dir_match = re.search(
        r"\*{0,2}예측\s*방향\*{0,2}\s*[:：]\s*(상승|하락|보합)", text
    )
    # 등락률: +/- 기호, ~·∼ 구분자 모두 허용
    rng_match = re.search(
        r"\*{0,2}예상\s*등락률\*{0,2}\s*[:：][^\n]*?([+-]?\d+\.?\d*)\s*%\s*[~～·∼]\s*([+-]?\d+\.?\d*)\s*%",
        text
    )
    # fallback
    if not dir_match:
        dir_match = re.search(r"(?:방향|Direction)\s*[:：]\s*(상승|하락|보합)", text)
    if not rng_match:
        rng_match = re.search(
            r"(?:등락률|변동률|예상\s*범위)\s*[:：][^\n]*?([+-]?\d+\.?\d*)\s*%\s*[~～·∼]\s*([+-]?\d+\.?\d*)\s*%",
            text
        )
    if not dir_match or not rng_match:
        return None
    direction = dir_match.group(1)
    low  = float(rng_match.group(1))
    high = float(rng_match.group(2))
    if low > high:
        low, high = high, low
    return {"direction": direction, "pct_low": low, "pct_high": high}


def run_ai_prediction(data: dict, sleep_sec: int = 3) -> tuple[str, dict | None]:
    """AI 분석 실행 → (전체 텍스트, 파싱된 예측) 반환. rate limit 시 재시도 1회."""
    from ai_analyzer import build_prompt, _call_groq_stream, GROQ_KEYS

    prompt = build_prompt(data)
    for attempt in range(len(GROQ_KEYS) + 1):
        tokens    = []
        has_error = False
        for token in _call_groq_stream(prompt):
            if token.startswith("❌ 모든 API 키"):
                has_error = True
                print(f"    ⏳ 모든 키 rate limit — {sleep_sec * 4}초 대기 후 재시도...")
                time.sleep(sleep_sec * 4)
                break
            tokens.append(token)

        if has_error:
            continue

        full_text = "".join(tokens)
        pred = parse_prediction(full_text)
        return full_text, pred

    return "❌ rate limit 재시도 초과", None


# ── 틀린 예측 자기분석 ────────────────────────────────────────────────

def run_self_review(result: dict) -> str:
    """틀린 예측에 대해 AI가 스스로 왜 틀렸는지 분석"""
    pred  = result["pred"]
    ev    = result["eval"]
    data  = result.get("collected_data", {})
    ind   = data.get("market_indicators", {})
    tech  = data.get("technicals", {})
    stock = data.get("stock", {})

    sp500_pct = ind.get("sp500_futures", {}).get("change_pct", "N/A")
    kospi_pct = ind.get("kospi",         {}).get("change_pct", "N/A")
    usd_pct   = ind.get("usd_krw",       {}).get("change_pct", "N/A")
    rsi       = tech.get("rsi",       "N/A")
    macd_hist = tech.get("histogram", "N/A")

    history  = stock.get("history", [])
    chg5_str = "N/A"
    if len(history) >= 5:
        closes5  = [d["close"] for d in history[-5:]]
        chg5     = (closes5[-1] - closes5[0]) / closes5[0] * 100
        chg5_str = f"{chg5:+.2f}%"

    review_prompt = f"""당신은 주식 예측 AI 시스템의 성능 분석 전문가입니다.
아래 예측이 틀린 이유를 데이터 기반으로 분석하고, 향후 같은 실수를 방지할 규칙을 제시하세요.

[예측 정보]
- 예측 방향: {pred['direction']} ({pred['pct_low']:+.1f}% ~ {pred['pct_high']:+.1f}%)
- 실제 결과: {ev['actual_dir']} ({ev['actual_pct']:+.2f}%)

[당시 보유 데이터]
- 코스피: {kospi_pct}%
- S&P500 선물: {sp500_pct}%
- 달러/원 변동: {usd_pct}%
- RSI: {rsi}
- MACD 히스토그램: {macd_hist}
- 최근 5일 누적 등락: {chg5_str}

[분석 요청]
1. 어떤 데이터를 놓쳤거나 잘못 해석했는가? (구체적 수치 언급)
2. 이 예측이 틀린 근본 원인은? (1~2줄)
3. 향후 같은 상황에서 적용할 예측 규칙 1가지 (if-then 형식)

반드시 한국어로 간결하게 답변하세요. 총 200자 이내."""

    try:
        from ai_analyzer import GROQ_KEYS, GROQ_URL, _get_key, _rotate_key, _is_rate_limit
        key = _get_key() or os.getenv("GROQ_API_KEY", "")
        if not key:
            return "  (API 키 없음)"

        resp = req_lib.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": review_prompt}],
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=30,
        )
        if _is_rate_limit(resp.status_code, resp.text):
            _rotate_key()
            return "  (rate limit — 자기분석 생략)"
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"  (API 오류: {resp.status_code})"
    except Exception as e:
        return f"  (자기분석 오류: {e})"


# ── 결과 평가 ─────────────────────────────────────────────────────────

def evaluate(pred: dict, base_price: float, actual_price: float) -> dict:
    actual_pct = round((actual_price - base_price) / base_price * 100, 2)
    actual_dir = "상승" if actual_pct > 1.0 else "하락" if actual_pct < -1.0 else "보합"
    hit        = (actual_dir == pred["direction"])
    in_range   = pred["pct_low"] <= actual_pct <= pred["pct_high"]
    return {
        "actual_price": actual_price,
        "actual_pct":   actual_pct,
        "actual_dir":   actual_dir,
        "hit":          hit,
        "in_range":     in_range,
    }


# ── 요약 출력 ─────────────────────────────────────────────────────────

def print_summary(results: list[dict], reviews: dict | None = None) -> str:
    verified   = [r for r in results if r.get("eval") is not None and r.get("pred")]
    total      = len(verified)
    lines      = []

    lines.append("=" * 65)
    lines.append("  StockOracle 백테스트 결과")
    lines.append("=" * 65)

    if total == 0:
        lines.append("  검증 가능한 결과 없음 (실제 가격 조회 실패 또는 파싱 실패)")
        summary = "\n".join(lines)
        print(summary)
        return summary

    hits       = sum(1 for r in verified if r["eval"]["hit"])
    in_ranges  = sum(1 for r in verified if r["eval"]["in_range"])
    overridden = sum(1 for r in verified if r.get("override_reason"))
    up_preds   = [r for r in verified if r["pred"]["direction"] == "상승"]
    dn_preds   = [r for r in verified if r["pred"]["direction"] == "하락"]
    flat_preds = [r for r in verified if r["pred"]["direction"] == "보합"]

    lines.append(f"  테스트 건수:     {total}건  (시장override: {overridden}건)")
    lines.append(f"  방향 정확도:     {hits}/{total} = {round(hits/total*100,1)}%")
    lines.append(f"  범위 정확도:     {in_ranges}/{total} = {round(in_ranges/total*100,1)}%")
    lines.append("")
    lines.append("  방향별 분석:")
    for label, preds in [("상승", up_preds), ("하락", dn_preds), ("보합", flat_preds)]:
        if preds:
            h = sum(1 for r in preds if r["eval"]["hit"])
            lines.append(f"    {label} 예측: {len(preds)}건 → 적중 {h}건 ({round(h/len(preds)*100,1)}%)")

    lines.append("")
    lines.append(f"  {'날짜':<12} {'예측':<5} {'예상범위':<17} {'실제등락':<8} {'실제방향':<5} {'방향':<4} {'범위':<4} {'비고'}")
    lines.append("  " + "-" * 70)
    for r in verified:
        p    = r["pred"]
        ev   = r["eval"]
        rng  = f"{p['pct_low']:+.1f}%~{p['pct_high']:+.1f}%"
        note = "🔀override" if r.get("override_reason") else ""
        lines.append(
            f"  {r['as_of']:<12} {p['direction']:<5} {rng:<17} "
            f"{ev['actual_pct']:+.2f}%  {ev['actual_dir']:<5} "
            f"{'✅' if ev['hit'] else '❌'}   {'✅' if ev['in_range'] else '❌'}   {note}"
        )

    # 틀린 예측 자기분석
    if reviews:
        wrong = [r for r in verified if not r["eval"]["hit"]]
        if wrong:
            lines.append("")
            lines.append("=" * 65)
            lines.append("  ❌ 틀린 예측 자기분석")
            lines.append("=" * 65)
            for r in wrong:
                ev   = r["eval"]
                p    = r["pred"]
                review_text = reviews.get(r["as_of"], "  (분석 없음)")
                lines.append(f"\n  [{r['as_of']}] 예측:{p['direction']} → 실제:{ev['actual_dir']} ({ev['actual_pct']:+.2f}%)")
                if r.get("override_reason"):
                    lines.append(f"  Override: {r['override_reason']}")
                for line in review_text.split("\n"):
                    lines.append(f"  {line}")

    lines.append("")
    lines.append("=" * 65)
    summary = "\n".join(lines)
    print(summary)
    return summary


# ── 메인 ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="StockOracle 백테스트")
    parser.add_argument("--ticker",    required=True)
    parser.add_argument("--name",      required=True)
    parser.add_argument("--country",   default="한국")
    parser.add_argument("--start",     required=True)
    parser.add_argument("--end",       required=True)
    parser.add_argument("--period",    default="tomorrow")
    parser.add_argument("--interval",  type=int, default=1)
    parser.add_argument("--out",       default="backtest_result.json")
    parser.add_argument("--no-ai",     action="store_true")
    parser.add_argument("--no-review", action="store_true")
    parser.add_argument("--sleep",     type=int, default=3, help="AI 호출 간 대기(초)")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt   = datetime.strptime(args.end,   "%Y-%m-%d")
    today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    test_days = business_days_between(start_dt, end_dt, args.interval)
    print(f"\n🔬 백테스트 시작: {args.ticker} ({args.name})")
    print(f"   기간: {args.start} ~ {args.end}  |  {len(test_days)}개 영업일  |  간격: {args.interval}일")
    print(f"   AI 호출 간격: {args.sleep}초\n")

    results = []

    for i, day in enumerate(test_days, 1):
        print(f"[{i}/{len(test_days)}] {day.date()} 기준 예측")

        if day >= today:
            print(f"    ⏭️  미래 날짜 스킵")
            continue

        data = collect_historical_data(args.ticker, args.name, args.country, day, args.period)

        if "error" in data.get("stock", {}):
            print(f"    ❌ 데이터 수집 실패: {data['stock']['error']}")
            results.append({"as_of": str(day.date()), "error": data["stock"]["error"]})
            continue

        base_price = float(data["stock"]["current_price"])
        print(f"    💰 기준가: {base_price:,.0f}")

        pred            = None
        ai_text         = ""
        override_reason = None

        if not args.no_ai:
            print(f"    🤖 AI 예측 중...")
            ai_text, pred = run_ai_prediction(data, sleep_sec=args.sleep)
            if pred:
                pred, override_reason = market_override(pred, data)
                tag = f" [🔀{override_reason}]" if override_reason else ""
                print(f"    📌 예측: {pred['direction']} ({pred['pct_low']:+.1f}% ~ {pred['pct_high']:+.1f}%){tag}")
            else:
                print(f"    ⚠️  예측 파싱 실패")
            time.sleep(args.sleep)  # 호출 간 기본 대기

        actual = get_actual_next_price(args.ticker, day)
        ev     = None
        if actual and pred:
            ev = evaluate(pred, base_price, actual["price"])
            print(f"    📊 실제: {actual['price']:,.0f} ({ev['actual_pct']:+.2f}%, {ev['actual_dir']}) "
                  f"→ {'✅ 방향 적중' if ev['hit'] else '❌ 방향 빗나감'} "
                  f"/ {'✅ 범위 적중' if ev['in_range'] else '❌ 범위 벗어남'}")
        elif actual:
            actual_pct = round((actual["price"] - base_price) / base_price * 100, 2)
            print(f"    📊 실제: {actual['price']:,.0f} ({actual_pct:+.2f}%)")

        results.append({
            "as_of":           str(day.date()),
            "base_price":      base_price,
            "pred":            pred,
            "actual":          actual,
            "eval":            ev,
            "override_reason": override_reason,
            "collected_data":  data,        # 자기분석용 (저장 시 제외)
            "ai_response":     ai_text[:500] if ai_text else None,
        })
        print()

    # ── 결과 저장 (누적) ──────────────────────────────────────────
    out_path = Path(args.out)
    existing = {"tests": []}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    tests   = existing.get("tests", [])
    test_id = max((t.get("test_id", 0) for t in tests), default=0) + 1

    save_results = [{k: v for k, v in r.items() if k != "collected_data"} for r in results]
    tests.append({
        "test_id": test_id,
        "run_at":  datetime.now().isoformat(),
        "ticker":  args.ticker,
        "name":    args.name,
        "period":  args.period,
        "results": save_results,
    })
    existing["tests"] = tests
    out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Test {test_id} 저장 완료 → {out_path}\n")

    # ── 틀린 예측 자기분석 ────────────────────────────────────────
    reviews = {}
    if not args.no_review and not args.no_ai:
        wrong = [r for r in results if r.get("eval") and not r["eval"]["hit"]]
        if wrong:
            print(f"🔍 틀린 예측 {len(wrong)}건 자기분석 중...\n")
            for r in wrong:
                print(f"  분석 중: {r['as_of']}")
                review = run_self_review(r)
                reviews[r["as_of"]] = review
                print(f"  → {review[:80]}...")
                time.sleep(args.sleep)
            print()

    # ── 요약 출력 및 누적 저장 ────────────────────────────────────
    print(f"\n🧪 Test ID: {test_id}\n")
    summary      = print_summary(results, reviews)
    summary_path = out_path.with_suffix(".txt")
    prev         = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(prev)
        f.write(f"\n\n{'='*20} TEST {test_id} {'='*20}\n")
        f.write(summary)
    print(f"💾 요약 저장 → {summary_path}")


if __name__ == "__main__":
    main()