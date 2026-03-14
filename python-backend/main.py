from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, re
from datetime import datetime

from data_collector import (
    collect_all, save_prediction, get_prediction_stats,
    verify_predictions, _load_log,
)
from ai_analyzer import analyze_stream

app = FastAPI(title="Stock Predictor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PositionInfo(BaseModel):
    quantity: float
    avgPrice: float
    targetProfitPct: float | None = None
    targetSellPrice: float | None = None


class AnalyzeRequest(BaseModel):
    ticker: str
    company_name: str
    country: str
    position: PositionInfo | None = None


class SavePredictionRequest(BaseModel):
    ticker: str
    company_name: str
    analysis_date: str
    current_price: float
    predicted_direction: str
    predicted_pct_low: float
    predicted_pct_high: float
    predicted_price_low: float
    predicted_price_high: float


def _calc_position(req: AnalyzeRequest, current_price: float) -> dict | None:
    if not req.position:
        return None
    qty      = req.position.quantity
    avg      = req.position.avgPrice
    cur      = current_price
    invested = round(qty * avg, 0)
    cur_val  = round(qty * cur, 0)
    pl       = round(cur_val - invested, 0)
    pl_pct   = round((cur - avg) / avg * 100, 2) if avg > 0 else 0

    # 목표가 결정 — 희망 매도 금액 우선, 없으면 수익률로 계산
    target_sell_price = req.position.targetSellPrice
    target_pct        = req.position.targetProfitPct

    if target_sell_price:
        # 금액 입력 → 수익률 역산
        target_pct = round((target_sell_price / avg - 1) * 100, 2) if avg > 0 else None
    elif target_pct:
        # 수익률 입력 → 금액 계산
        target_sell_price = round(avg * (1 + target_pct / 100), 0)

    # 목표 도달 시 수익 금액
    target_profit_amount = round((target_sell_price - avg) * qty, 0) if target_sell_price else None

    # 현재가 → 목표가까지 남은 금액/퍼센트
    gap_to_target_pct   = round((target_sell_price - cur) / cur * 100, 2) if target_sell_price and cur else None
    gap_to_target_price = round(target_sell_price - cur, 0) if target_sell_price else None

    return {
        "quantity":             qty,
        "avg_price":            avg,
        "total_invested":       invested,
        "current_value":        cur_val,
        "profit_loss":          pl,
        "profit_loss_pct":      pl_pct,
        "profit_loss_amount":   pl,  # 원 단위 손익 (명시적)
        "target_profit_pct":    target_pct,
        "target_sell_price":    target_sell_price,
        "target_profit_amount": target_profit_amount,
        "gap_to_target_pct":    gap_to_target_pct,
        "gap_to_target_price":  gap_to_target_price,
    }

@app.get("/")
def root():
    return {"status": "ok", "message": "StockOracle API 실행 중"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/collect")
def collect_data(req: AnalyzeRequest):
    """데이터 수집만 (AI 분석 없이)"""
    data = collect_all(req.ticker, req.company_name, req.country)
    if "error" in data.get("stock", {}):
        raise HTTPException(status_code=400, detail=data["stock"]["error"])
    pos = _calc_position(req, float(data["stock"].get("current_price", 0)))
    if pos:
        data["position"] = pos
    return data


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """데이터 수집 + AI 분석 스트리밍"""

    data = collect_all(req.ticker, req.company_name, req.country)

    if "error" in data.get("stock", {}):
        raise HTTPException(status_code=400, detail=data["stock"]["error"])

    # 포지션 계산 후 data에 추가
    pos = _calc_position(req, float(data["stock"].get("current_price", 0)))
    if pos:
        data["position"] = pos

    def stream_response():
        # 1. 수집 데이터 전송
        yield f"data: {json.dumps({'type': 'data', 'payload': data}, ensure_ascii=False)}\n\n"

        # 2. AI 분석 스트리밍
        full_text = []
        for token in analyze_stream(data):
            full_text.append(token)
            yield f"data: {json.dumps({'type': 'token', 'payload': token}, ensure_ascii=False)}\n\n"

        # 3. 예측 파싱 & 자동 저장
        try:
            analysis = "".join(full_text)
            pred = _parse_prediction(analysis, data)
            if pred:
                today = datetime.now().strftime("%Y-%m-%d")
                cur   = float(data["stock"].get("current_price", 0))
                save_prediction(
                    ticker               = req.ticker,
                    company_name         = req.company_name,
                    predicted_direction  = pred["direction"],
                    predicted_pct_low    = pred["pct_low"],
                    predicted_pct_high   = pred["pct_high"],
                    predicted_price_low  = round(cur * (1 + pred["pct_low"]  / 100), 2),
                    predicted_price_high = round(cur * (1 + pred["pct_high"] / 100), 2),
                    current_price        = cur,
                    analysis_date        = today,
                )
                yield f"data: {json.dumps({'type': 'prediction_saved', 'payload': pred}, ensure_ascii=False)}\n\n"
        except Exception:
            pass

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _parse_prediction(text: str, data: dict) -> dict | None:
    try:
        dir_match = re.search(r"\*\*예측 방향\*\*[:：]\s*(상승|하락|보합)", text)
        direction = dir_match.group(1) if dir_match else None
        rng_match = re.search(
            r"\*\*예상 등락률\*\*[:：]\s*([+-]?\d+\.?\d*)\s*%\s*[~～]\s*([+-]?\d+\.?\d*)\s*%",
            text,
        )
        if not direction or not rng_match:
            return None
        low  = float(rng_match.group(1))
        high = float(rng_match.group(2))
        if low > high:
            low, high = high, low
        return {"direction": direction, "pct_low": low, "pct_high": high}
    except Exception:
        return None


@app.post("/prediction/save")
def api_save_prediction(req: SavePredictionRequest):
    return save_prediction(
        ticker               = req.ticker,
        company_name         = req.company_name,
        predicted_direction  = req.predicted_direction,
        predicted_pct_low    = req.predicted_pct_low,
        predicted_pct_high   = req.predicted_pct_high,
        predicted_price_low  = req.predicted_price_low,
        predicted_price_high = req.predicted_price_high,
        current_price        = req.current_price,
        analysis_date        = req.analysis_date,
    )


@app.get("/prediction/stats")
def api_prediction_stats(ticker: str = None):
    return get_prediction_stats(ticker)


@app.get("/prediction/history")
def api_prediction_history(ticker: str = None):
    log = _load_log()
    if ticker:
        log = [e for e in log if e["ticker"] == ticker]
    return {"history": log[::-1]}


@app.post("/prediction/verify")
def api_verify(ticker: str = None):
    return verify_predictions(ticker)


@app.get("/indicators")
def get_indicators():
    from data_collector import get_market_indicators
    return get_market_indicators()


@app.get("/ticker-hint")
def ticker_hint(country: str, name: str):
    hints = {
        "한국": {
            "format": "숫자6자리.KS (코스피) 또는 숫자6자리.KQ (코스닥)",
            "examples": ["005930.KS (삼성전자)", "000660.KS (SK하이닉스)", "035720.KQ (카카오)"],
        },
        "미국": {
            "format": "영문 티커",
            "examples": ["AAPL (Apple)", "TSLA (Tesla)", "NVDA (NVIDIA)"],
        },
        "일본": {
            "format": "숫자4자리.T",
            "examples": ["7203.T (Toyota)", "9984.T (SoftBank)"],
        },
    }
    return hints.get(country, {"format": "Yahoo Finance 티커 형식 사용", "examples": []})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)