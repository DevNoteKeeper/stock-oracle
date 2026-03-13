from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from data_collector import collect_all
from ai_analyzer import analyze_stream

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