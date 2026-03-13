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


class AnalyzeRequest(BaseModel):
    ticker: str
    company_name: str
    country: str


class SavePredictionRequest(BaseModel):
    ticker: str
    company_name: str
    analysis_date: str       # YYYY-MM-DD
    current_price: float
    predicted_direction: str  # 상승/하락/보합
    predicted_pct_low: float
    predicted_pct_high: float
    predicted_price_low: float
    predicted_price_high: float


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
    return data


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """데이터 수집 + AI 분석 스트리밍. 분석 완료 후 예측 자동 파싱·저장."""

    data = collect_all(req.ticker, req.company_name, req.country)

    if "error" in data.get("stock", {}):
        raise HTTPException(status_code=400, detail=data["stock"]["error"])

    def stream_response():
        # ── 1. 수집 데이터 전송 ──────────────────────────────────
        yield f"data: {json.dumps({'type': 'data', 'payload': data}, ensure_ascii=False)}\n\n"

        # ── 2. AI 분석 스트리밍 ──────────────────────────────────
        full_text = []
        for token in analyze_stream(data):
            full_text.append(token)
            yield f"data: {json.dumps({'type': 'token', 'payload': token}, ensure_ascii=False)}\n\n"

        # ── 3. 예측 파싱 & 자동 저장 ────────────────────────────
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
    """분석 텍스트에서 예측 방향·등락률 파싱"""
    try:
        # 예측 방향
        dir_match = re.search(r"\*\*예측 방향\*\*[:：]\s*(상승|하락|보합)", text)
        direction = dir_match.group(1) if dir_match else None

        # 예상 등락률  예: -1.5% ~ -0.3%  또는  +1% ~ +3%
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
    """예측 수동 저장 (프론트엔드에서 직접 호출 가능)"""
    result = save_prediction(
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
    return result


@app.get("/prediction/stats")
def api_prediction_stats(ticker: str = None):
    """예측 정확도 통계 조회"""
    return get_prediction_stats(ticker)


@app.get("/prediction/history")
def api_prediction_history(ticker: str = None):
    """전체 예측 히스토리 (검증 전 포함)"""
    log = _load_log()
    if ticker:
        log = [e for e in log if e["ticker"] == ticker]
    return {"history": log[::-1]}  # 최신순


@app.post("/prediction/verify")
def api_verify(ticker: str = None):
    """미검증 예측 수동 검증 트리거"""
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


app = FastAPI(title="Stock Predictor API")

# CORS 설정 (React에서 호출 가능하게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    ticker: str          # 예: 005930.KS, AAPL
    company_name: str    # 예: 삼성전자, Apple
    country: str         # 예: 한국, 미국


@app.get("/")
def root():
    return {"status": "ok", "message": "Stock Predictor API 실행 중"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/collect")
def collect_data(req: AnalyzeRequest):
    """데이터 수집만 (AI 분석 없이)"""
    data = collect_all(req.ticker, req.company_name, req.country)
    if "error" in data.get("stock", {}):
        raise HTTPException(status_code=400, detail=data["stock"]["error"])
    return data


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """데이터 수집 + AI 분석 (스트리밍)"""

    # 1. 데이터 수집
    data = collect_all(req.ticker, req.company_name, req.country)

    if "error" in data.get("stock", {}):
        raise HTTPException(status_code=400, detail=data["stock"]["error"])

    # 2. AI 분석 스트리밍 응답
    def stream_response():
        # 먼저 수집된 데이터 전송
        yield f"data: {json.dumps({'type': 'data', 'payload': data}, ensure_ascii=False)}\n\n"

        # AI 분석 스트리밍
        for token in analyze_stream(data):
            yield f"data: {json.dumps({'type': 'token', 'payload': token}, ensure_ascii=False)}\n\n"

        # 완료 신호
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/indicators")
def get_indicators():
    """시장 지표만 조회"""
    from data_collector import get_market_indicators
    return get_market_indicators()


# 티커 검색 힌트
@app.get("/ticker-hint")
def ticker_hint(country: str, name: str):
    """국가별 티커 형식 안내"""
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