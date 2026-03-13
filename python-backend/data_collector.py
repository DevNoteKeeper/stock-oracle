import yfinance as yf
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def get_stock_data(ticker: str, period: str = "3mo"):
    """주식 데이터 수집 (한국: 005930.KS, 미국: AAPL 등)"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info

        if hist.empty:
            return {"error": f"'{ticker}' 티커를 찾을 수 없어요."}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest

        change = latest["Close"] - prev["Close"]
        change_pct = (change / prev["Close"]) * 100

        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "current_price": round(float(latest["Close"]), 2),
            "prev_price": round(float(prev["Close"]), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "volume": int(latest["Volume"]),
            "high_52w": round(float(info.get("fiftyTwoWeekHigh", 0)), 2),
            "low_52w": round(float(info.get("fiftyTwoWeekLow", 0)), 2),
            "history": [
                {
                    "date": str(idx.date()),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
                for idx, row in hist.tail(30).iterrows()
            ],
        }
    except Exception as e:
        return {"error": str(e)}

def get_technicals(ticker: str):
    """RSI, MACD, 볼린저밴드, 이동평균 계산 (외부 라이브러리 없이 순수 계산)"""
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="6mo")   # 6개월치 — 지표 안정화에 충분

        if hist.empty or len(hist) < 30:
            return {"available": False, "reason": "데이터 부족 (30일 미만)"}

        closes  = hist["Close"].tolist()
        highs   = hist["High"].tolist()
        lows    = hist["Low"].tolist()
        volumes = hist["Volume"].tolist()
        dates   = [str(d.date()) for d in hist.index]
        n       = len(closes)

        # ── 이동평균 ───────────────────────────────────────────
        def sma(data, period):
            if len(data) < period:
                return None
            return round(sum(data[-period:]) / period, 2)

        def ema(data, period):
            """지수이동평균 (전체 계산 후 마지막 값 반환)"""
            if len(data) < period:
                return None
            k   = 2 / (period + 1)
            val = sum(data[:period]) / period  # 첫 EMA = SMA
            for price in data[period:]:
                val = price * k + val * (1 - k)
            return round(val, 2)

        def ema_series(data, period):
            """전체 EMA 시리즈 반환"""
            if len(data) < period:
                return []
            k    = 2 / (period + 1)
            vals = [sum(data[:period]) / period]
            for price in data[period:]:
                vals.append(price * k + vals[-1] * (1 - k))
            return vals

        ma5   = sma(closes, 5)
        ma20  = sma(closes, 20)
        ma60  = sma(closes, 60)
        ma120 = sma(closes, 120) if n >= 120 else None

        cur = closes[-1]

        # 골든/데드크로스 감지
        def cross_signal(short_p, long_p, lookback=5):
            if n < long_p + lookback:
                return None
            short_prev = sma(closes[-(short_p + lookback):-lookback], short_p)
            long_prev  = sma(closes[-(long_p  + lookback):-lookback], long_p)
            short_cur  = sma(closes, short_p)
            long_cur   = sma(closes, long_p)
            if None in (short_prev, long_prev, short_cur, long_cur):
                return None
            if short_prev <= long_prev and short_cur > long_cur:
                return "골든크로스"
            if short_prev >= long_prev and short_cur < long_cur:
                return "데드크로스"
            return None

        ma_cross = cross_signal(5, 20) or cross_signal(20, 60)

        # ── RSI (14일) ─────────────────────────────────────────
        def calc_rsi(data, period=14):
            if len(data) < period + 1:
                return None
            deltas = [data[i] - data[i-1] for i in range(1, len(data))]
            gains  = [max(d, 0) for d in deltas]
            losses = [abs(min(d, 0)) for d in deltas]

            # 초기 평균 (단순)
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period

            # Wilder 평활
            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                return 100.0
            rs  = avg_gain / avg_loss
            return round(100 - 100 / (1 + rs), 2)

        rsi = calc_rsi(closes)

        # RSI 추세 (최근 3일 방향)
        rsi_3d_ago = calc_rsi(closes[:-3]) if n > 17 else None
        rsi_trend  = None
        if rsi and rsi_3d_ago:
            diff = rsi - rsi_3d_ago
            rsi_trend = "상승" if diff > 2 else "하락" if diff < -2 else "보합"

        def rsi_label(v):
            if v is None: return ""
            if v >= 80:   return "극단적 과매수 (강한 하락 위험)"
            if v >= 70:   return "과매수 구간 (조정 가능성)"
            if v >= 60:   return "강세 영역"
            if v >= 40:   return "중립 영역"
            if v >= 30:   return "약세 영역"
            if v >= 20:   return "과매도 구간 (반등 가능성)"
            return "극단적 과매도 (강한 반등 위험)"

        # ── MACD (12, 26, 9) ──────────────────────────────────
        ema12_s = ema_series(closes, 12)
        ema26_s = ema_series(closes, 26)

        macd_line = signal_line = histogram = None
        macd_cross = None

        if len(ema12_s) > 0 and len(ema26_s) > 0:
            # 두 시리즈를 공통 길이로 맞춤
            min_len   = min(len(ema12_s), len(ema26_s))
            macd_vals = [ema12_s[-min_len + i] - ema26_s[-min_len + i]
                         for i in range(min_len)]

            if len(macd_vals) >= 9:
                signal_s    = ema_series(macd_vals, 9)
                macd_line   = round(macd_vals[-1], 4)
                signal_line = round(signal_s[-1], 4)
                histogram   = round(macd_line - signal_line, 4)

                # 크로스 감지 (최근 3봉)
                if len(signal_s) >= 3 and len(macd_vals) >= 3:
                    offset = len(macd_vals) - len(signal_s)
                    prev_m = macd_vals[-3 + offset] if offset >= 0 else None
                    prev_s = signal_s[-3]
                    cur_m  = macd_vals[-1]
                    cur_s  = signal_s[-1]
                    if prev_m is not None:
                        if prev_m <= prev_s and cur_m > cur_s:
                            macd_cross = "골든크로스 (매수 신호)"
                        elif prev_m >= prev_s and cur_m < cur_s:
                            macd_cross = "데드크로스 (매도 신호)"

        def macd_label(line, signal):
            if line is None or signal is None: return ""
            if line > 0 and line > signal:  return "상승 모멘텀 강화"
            if line > 0 and line <= signal: return "상승세 둔화"
            if line < 0 and line < signal:  return "하락 모멘텀 강화"
            return "하락세 둔화 (반등 시도)"

        # ── 볼린저밴드 (20일, 2σ) ──────────────────────────────
        bb_upper = bb_middle = bb_lower = bb_pct_b = bb_width = None

        if n >= 20:
            bb_period = 20
            bb_std    = 2
            window    = closes[-bb_period:]
            mean      = sum(window) / bb_period
            variance  = sum((x - mean) ** 2 for x in window) / bb_period
            std       = variance ** 0.5

            bb_upper  = round(mean + bb_std * std, 2)
            bb_middle = round(mean, 2)
            bb_lower  = round(mean - bb_std * std, 2)

            # %B — 현재가가 밴드 내 어디에 위치하는지 (0~1, 1이상=상단 돌파)
            band_range = bb_upper - bb_lower
            bb_pct_b   = round((cur - bb_lower) / band_range, 4) if band_range > 0 else 0.5

            # 밴드폭 — 변동성 지표 (좁을수록 폭발 가능성)
            bb_width = round(band_range / bb_middle * 100, 2) if bb_middle > 0 else None

        def bb_label(pct_b):
            if pct_b is None: return ""
            if pct_b >= 1.0:  return "상단 돌파 (과매수, 조정 위험)"
            if pct_b >= 0.8:  return "상단 근처 (강세, 과열 주의)"
            if pct_b >= 0.5:  return "중간~상단 (강세 영역)"
            if pct_b >= 0.2:  return "중간~하단 (약세 영역)"
            if pct_b >= 0.0:  return "하단 근처 (약세, 반등 가능)"
            return "하단 이탈 (과매도, 반등 위험)"

        # ── 거래량 이동평균 ────────────────────────────────────
        vol_ma20  = round(sum(volumes[-20:]) / 20) if n >= 20 else None
        vol_ratio = round(volumes[-1] / vol_ma20, 2) if vol_ma20 and vol_ma20 > 0 else None

        # ── 스토캐스틱 (14, 3) ────────────────────────────────
        stoch_k = stoch_d = None
        if n >= 14:
            period_highs = highs[-14:]
            period_lows  = lows[-14:]
            highest_high = max(period_highs)
            lowest_low   = min(period_lows)
            if highest_high != lowest_low:
                stoch_k = round(
                    (cur - lowest_low) / (highest_high - lowest_low) * 100, 2
                )
            # %D = 최근 3일 %K 평균
            k_vals = []
            for i in range(3):
                idx   = n - 3 + i
                ph    = max(highs[idx-13:idx+1]) if idx >= 13 else None
                pl    = min(lows[idx-13:idx+1])  if idx >= 13 else None
                if ph and pl and ph != pl:
                    k_vals.append((closes[idx] - pl) / (ph - pl) * 100)
            if len(k_vals) == 3:
                stoch_d = round(sum(k_vals) / 3, 2)

        # ── 최근 차트 데이터 (UI용, 60일) ─────────────────────
        chart_data = []
        ema12_s_full = ema_series(closes, 12)
        ema26_s_full = ema_series(closes, 26)

        for i in range(max(0, n - 60), n):
            entry = {
                "date":   dates[i],
                "close":  round(closes[i], 2),
                "volume": int(volumes[i]),
            }
            # MA
            if i >= 4:   entry["ma5"]  = round(sum(closes[i-4:i+1]) / 5, 2)
            if i >= 19:  entry["ma20"] = round(sum(closes[i-19:i+1]) / 20, 2)
            # 볼린저밴드
            if i >= 19:
                w    = closes[i-19:i+1]
                m    = sum(w) / 20
                s    = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
                entry["bb_upper"]  = round(m + 2 * s, 2)
                entry["bb_middle"] = round(m, 2)
                entry["bb_lower"]  = round(m - 2 * s, 2)
            chart_data.append(entry)

        return {
            "available": True,
            # 이동평균
            "ma5": ma5, "ma20": ma20, "ma60": ma60, "ma120": ma120,
            "ma_cross": ma_cross,
            # RSI
            "rsi": rsi, "rsi_label": rsi_label(rsi), "rsi_trend": rsi_trend,
            # MACD
            "macd_line": macd_line, "signal_line": signal_line,
            "histogram": histogram, "macd_cross": macd_cross,
            "macd_label": macd_label(macd_line, signal_line),
            # 볼린저밴드
            "bb_upper": bb_upper, "bb_middle": bb_middle, "bb_lower": bb_lower,
            "bb_pct_b": bb_pct_b, "bb_width": bb_width,
            "bb_label": bb_label(bb_pct_b),
            # 거래량
            "vol_ma20": vol_ma20, "vol_ratio": vol_ratio,
            # 스토캐스틱
            "stoch_k": stoch_k, "stoch_d": stoch_d,
            # 차트 데이터 (UI)
            "chart_data": chart_data,
        }

    except Exception as e:
        return {"available": False, "reason": str(e)}


def get_financials(ticker: str, country: str = "한국"):
    """재무제표 핵심 지표 수집 (yfinance + 네이버금융 보조)"""

    def safe(val, digits=2):
        """None/NaN 안전 처리"""
        try:
            if val is None:
                return None
            f = float(val)
            import math
            if math.isnan(f) or math.isinf(f):
                return None
            return round(f, digits)
        except Exception:
            return None

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # ── 밸류에이션 ──────────────────────────────────────────
        per       = safe(info.get("trailingPE"))
        forward_per = safe(info.get("forwardPE"))
        pbr       = safe(info.get("priceToBook"))
        psr       = safe(info.get("priceToSalesTrailing12Months"))
        ev_ebitda = safe(info.get("enterpriseToEbitda"))

        # ── 수익성 ──────────────────────────────────────────────
        roe           = safe(info.get("returnOnEquity"),   4)   # 소수점 → 아래서 %로 변환
        roa           = safe(info.get("returnOnAssets"),   4)
        gross_margin  = safe(info.get("grossMargins"),     4)
        op_margin     = safe(info.get("operatingMargins"), 4)
        net_margin    = safe(info.get("profitMargins"),    4)

        # ── 성장성 ──────────────────────────────────────────────
        revenue_growth  = safe(info.get("revenueGrowth"),  4)   # 전년비
        earnings_growth = safe(info.get("earningsGrowth"), 4)
        earnings_qoq    = safe(info.get("earningsQuarterlyGrowth"), 4)  # 전분기비

        # ── 재무 건전성 ─────────────────────────────────────────
        debt_to_equity  = safe(info.get("debtToEquity"))
        current_ratio   = safe(info.get("currentRatio"))
        quick_ratio     = safe(info.get("quickRatio"))

        # ── 배당 ────────────────────────────────────────────────
        dividend_yield  = safe(info.get("dividendYield"), 4)
        payout_ratio    = safe(info.get("payoutRatio"),   4)

        # ── 규모 ────────────────────────────────────────────────
        market_cap      = info.get("marketCap")          # 시가총액 (원/달러)
        total_revenue   = info.get("totalRevenue")
        ebitda          = info.get("ebitda")

        # ── 한국 주식 보완: 네이버금융 크롤링 ───────────────────
        naver_finance = {}
        if (".KS" in ticker or ".KQ" in ticker):
            try:
                from bs4 import BeautifulSoup
                code = ticker.split(".")[0]
                url = f"https://finance.naver.com/item/main.naver?code={code}"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=8)
                soup = BeautifulSoup(resp.text, "lxml")

                # 종목 분석 테이블 (PER, PBR, EPS, BPS)
                table = soup.select_one("table.no_info")
                if table:
                    cells = table.select("td em")
                    labels = table.select("th")
                    for th, em in zip(labels, cells):
                        key_text = th.get_text(strip=True)
                        val_text = em.get_text(strip=True).replace(",", "")
                        try:
                            val = float(val_text)
                        except Exception:
                            continue
                        if "PER" in key_text:
                            naver_finance["per"] = val
                        elif "PBR" in key_text:
                            naver_finance["pbr"] = val
                        elif "EPS" in key_text:
                            naver_finance["eps"] = val
                        elif "BPS" in key_text:
                            naver_finance["bps"] = val

                # 업종 PER
                industry_per_tag = soup.select_one("em#ems")
                if industry_per_tag:
                    try:
                        naver_finance["industry_per"] = float(
                            industry_per_tag.get_text(strip=True).replace(",", "")
                        )
                    except Exception:
                        pass

            except Exception:
                pass   # 크롤링 실패해도 yfinance 데이터로 진행

        # 네이버 데이터로 보완 (yfinance가 None인 경우)
        if per is None and naver_finance.get("per"):
            per = safe(naver_finance["per"])
        if pbr is None and naver_finance.get("pbr"):
            pbr = safe(naver_finance["pbr"])

        # ── 지표 해석 라벨 ──────────────────────────────────────
        def per_label(v):
            if v is None: return ""
            if v < 0:     return "적자 (PER 음수)"
            if v < 10:    return "저평가 가능성"
            if v < 20:    return "적정 수준"
            if v < 30:    return "다소 고평가"
            return "고평가 주의"

        def pbr_label(v):
            if v is None: return ""
            if v < 1.0:   return "순자산 이하 (저평가)"
            if v < 2.0:   return "적정 수준"
            if v < 4.0:   return "다소 고평가"
            return "고평가"

        def pct(v):
            """소수점 비율 → % 문자열"""
            if v is None: return None
            return round(v * 100, 2)

        return {
            "available": True,
            # 밸류에이션
            "per":           per,
            "per_label":     per_label(per),
            "forward_per":   forward_per,
            "pbr":           pbr,
            "pbr_label":     pbr_label(pbr),
            "psr":           psr,
            "ev_ebitda":     ev_ebitda,
            "industry_per":  naver_finance.get("industry_per"),
            "eps":           naver_finance.get("eps"),
            "bps":           naver_finance.get("bps"),
            # 수익성 (%)
            "roe":           pct(roe),
            "roa":           pct(roa),
            "gross_margin":  pct(gross_margin),
            "op_margin":     pct(op_margin),
            "net_margin":    pct(net_margin),
            # 성장성 (%)
            "revenue_growth":   pct(revenue_growth),
            "earnings_growth":  pct(earnings_growth),
            "earnings_qoq":     pct(earnings_qoq),
            # 재무 건전성
            "debt_to_equity": debt_to_equity,
            "current_ratio":  current_ratio,
            "quick_ratio":    quick_ratio,
            # 배당
            "dividend_yield": pct(dividend_yield),
            "payout_ratio":   pct(payout_ratio),
            # 규모
            "market_cap":    market_cap,
            "total_revenue": total_revenue,
            "ebitda":        ebitda,
        }

    except Exception as e:
        return {"available": False, "reason": str(e)}


def get_investor_trading(ticker: str):
    """외국인/기관/개인 거래량 수집 (네이버 금융 크롤링)"""

    if ".KS" not in ticker and ".KQ" not in ticker:
        return {"available": False, "reason": "외국인/기관 데이터는 한국 주식만 지원해요."}

    try:
        from bs4 import BeautifulSoup

        code = ticker.split(".")[0]
        url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "lxml")

        table = soup.select("table.type2")[1]
        rows = table.select("tr")

        def parse_num(text):
            text = text.replace(",", "").replace("+", "").replace("%", "").strip()
            try:
                return int(text)
            except:
                try:
                    return float(text)
                except:
                    return 0

        trading_data = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 9:
                continue
            date = cols[0].get_text(strip=True)
            if not date or "." not in date:
                continue

            trading_data.append({
                "date": date,
                "close": parse_num(cols[1].get_text(strip=True)),
                "volume": parse_num(cols[4].get_text(strip=True)),
                "foreign": parse_num(cols[5].get_text(strip=True)),
                "institution": parse_num(cols[6].get_text(strip=True)),
                "foreign_holding_pct": cols[8].get_text(strip=True),
            })

            if len(trading_data) >= 5:
                break

        if not trading_data:
            return {"available": False, "reason": "데이터를 파싱할 수 없어요."}

        total_foreign = sum(d["foreign"] for d in trading_data)
        total_institution = sum(d["institution"] for d in trading_data)

        def direction(val):
            if val > 0:
                return f"+{val:,}주 (순매수)"
            elif val < 0:
                return f"{val:,}주 (순매도)"
            else:
                return "0주 (중립)"

        return {
            "available": True,
            "latest": trading_data[0],
            "5day_summary": {
                "foreign_net": total_foreign,
                "foreign_net_str": direction(total_foreign),
                "institution_net": total_institution,
                "institution_net_str": direction(total_institution),
            },
            "history": trading_data,
        }

    except Exception as e:
        return {"available": False, "reason": str(e)}

def get_market_indicators():
    """환율, 유가, 코스피, 야간선물 수집"""
    indicators = {}

    targets = {
        "kospi": "^KS11",
        "usd_krw": "USDKRW=X",
        "oil_wti": "CL=F",
        "oil_brent": "BZ=F",
        "sp500_futures": "ES=F",
        "nasdaq_futures": "NQ=F",
        "usd_jpy": "USDJPY=X",
        "gold": "GC=F",
    }

    for key, ticker in targets.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="5d")

            if hist.empty:
                indicators[key] = {"error": "데이터 없음"}
                continue

            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100

            indicators[key] = {
                "ticker": ticker,
                "price": round(float(latest["Close"]), 2),
                "change_pct": round(float(change_pct), 2),
            }
        except Exception as e:
            indicators[key] = {"error": str(e)}

    return indicators


def get_news(query: str, company_name: str = "", country: str = "한국", days: int = 7):
    """
    뉴스 수집 + 분류
    - 한국: 네이버 뉴스 크롤링 (주력) + NewsAPI 보완
    - 해외: NewsAPI
    - 키워드 기반 카테고리 분류 및 감성 사전 판단
    """

    # ── 감성/카테고리 키워드 사전 ─────────────────────────────────
    POSITIVE_KW = [
        "상승", "호실적", "최대", "흑자", "수주", "성장", "회복", "반등", "돌파", "신고가",
        "매수", "호재", "인수", "협약", "출시", "확대", "강세", "증가", "개선", "배당",
        "beat", "record", "growth", "surge", "rally", "upgrade", "profit", "gain",
    ]
    NEGATIVE_KW = [
        "하락", "적자", "손실", "리콜", "소송", "제재", "파업", "노조", "감소", "급락",
        "매도", "악재", "리스크", "위기", "부진", "하향", "취소", "연기", "불확실",
        "miss", "loss", "decline", "drop", "downgrade", "lawsuit", "strike", "recall",
    ]
    CATEGORY_KW = {
        "실적/재무": ["실적", "매출", "영업이익", "순이익", "EPS", "어닝", "분기", "연간", "흑자", "적자", "revenue", "earnings", "profit"],
        "경영/인사":  ["CEO", "대표", "회장", "사장", "임원", "교체", "선임", "사임", "합병", "인수", "분사"],
        "제품/사업":  ["출시", "개발", "계약", "수주", "파트너십", "협약", "신제품", "서비스", "공장", "투자"],
        "규제/법적":  ["소송", "제재", "규제", "공정위", "금감원", "SEC", "조사", "벌금", "과징금", "lawsuit"],
        "노사/내부":  ["파업", "노조", "임금", "구조조정", "감원", "해고", "복지", "strike", "union"],
        "거시/시장":  ["금리", "환율", "인플레", "경기", "FOMC", "Fed", "한은", "기준금리", "무역"],
        "지정학":     ["전쟁", "분쟁", "제재", "관세", "무역전쟁", "지정학", "war", "sanction", "tariff"],
    }

    def classify(title: str, desc: str = "") -> dict:
        text = (title + " " + desc).lower()
        sentiment = "중립"
        pos = sum(1 for w in POSITIVE_KW if w.lower() in text)
        neg = sum(1 for w in NEGATIVE_KW if w.lower() in text)
        if pos > neg:   sentiment = "긍정"
        elif neg > pos: sentiment = "부정"

        categories = []
        for cat, kws in CATEGORY_KW.items():
            if any(kw.lower() in text for kw in kws):
                categories.append(cat)

        return {"sentiment": sentiment, "categories": categories or ["일반"]}

    articles = []

    # ── 한국 주식: 네이버 뉴스 크롤링 ────────────────────────────
    if company_name and (country == "한국" or "KS" in query or "KQ" in query):
        try:
            from bs4 import BeautifulSoup
            import urllib.parse

            search_q = urllib.parse.quote(company_name)
            url = f"https://search.naver.com/search.naver?where=news&query={search_q}&sort=1&nso=so:dd,p:1w"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select("div.news_area")[:12]:
                title_tag = item.select_one("a.news_tit")
                desc_tag  = item.select_one("div.news_dsc")
                press_tag = item.select_one("a.info.press")
                time_tag  = item.select_one("span.info")

                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                desc  = desc_tag.get_text(strip=True) if desc_tag else ""
                source = press_tag.get_text(strip=True) if press_tag else "네이버뉴스"
                pub_time = time_tag.get_text(strip=True) if time_tag else ""
                link  = title_tag.get("href", "")

                meta = classify(title, desc)
                articles.append({
                    "title":        title,
                    "description":  desc[:200] if desc else "",
                    "source":       source,
                    "published_at": pub_time,
                    "url":          link,
                    "sentiment":    meta["sentiment"],
                    "categories":   meta["categories"],
                })

        except Exception as e:
            print(f"  ⚠️  네이버 뉴스 크롤링 실패: {e}")

    # ── NewsAPI (한국어 → 실패 시 영어) ─────────────────────────
    if NEWS_API_KEY:
        try:
            from_date    = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            search_query = f"{company_name or query}".strip()

            url    = "https://newsapi.org/v2/everything"
            params = {
                "q":        search_query,
                "from":     from_date,
                "sortBy":   "relevancy",
                "language": "ko",
                "pageSize": 10,
                "apiKey":   NEWS_API_KEY,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("status") != "ok":
                params["language"] = "en"
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()

            for a in data.get("articles", [])[:10]:
                title = a.get("title", "")
                desc  = a.get("description", "") or ""
                # 중복 제거 (네이버 결과와 제목 앞 20자 비교)
                dup = any(title[:20] == ex["title"][:20] for ex in articles if ex.get("title"))
                if dup or not title:
                    continue
                meta = classify(title, desc)
                articles.append({
                    "title":        title,
                    "description":  desc[:200],
                    "source":       a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", "")[:10],
                    "url":          a.get("url", ""),
                    "sentiment":    meta["sentiment"],
                    "categories":   meta["categories"],
                })
        except Exception:
            pass

    # ── 감성 통계 집계 ─────────────────────────────────────────
    pos_cnt  = sum(1 for a in articles if a.get("sentiment") == "긍정")
    neg_cnt  = sum(1 for a in articles if a.get("sentiment") == "부정")
    neu_cnt  = sum(1 for a in articles if a.get("sentiment") == "중립")
    total    = len(articles)

    # 카테고리별 집계
    cat_counts: dict = {}
    for a in articles:
        for c in a.get("categories", []):
            cat_counts[c] = cat_counts.get(c, 0) + 1

    # 주요 이슈 키워드 추출 (제목에서 명사 빈도 — 간단 버전)
    import re
    all_text = " ".join(a.get("title", "") for a in articles)
    words    = re.findall(r"[가-힣A-Za-z]{2,}", all_text)
    STOP     = {"있다","없다","위한","따른","통해","지난","올해","이번","해당",
                "관련","대해","대한","등의","에서","으로","부터","까지","the","and","for","with","that","this"}
    freq: dict = {}
    for w in words:
        if w not in STOP and len(w) >= 2:
            freq[w] = freq.get(w, 0) + 1
    top_keywords = sorted(freq.items(), key=lambda x: -x[1])[:10]

    return {
        "total":        total,
        "articles":     articles[:15],
        "sentiment_summary": {
            "positive": pos_cnt,
            "negative": neg_cnt,
            "neutral":  neu_cnt,
            "score":    round((pos_cnt - neg_cnt) / total, 2) if total > 0 else 0,
        },
        "category_counts": cat_counts,
        "top_keywords":    [w for w, _ in top_keywords],
    }


# ── 예측 정확도 추적 ────────────────────────────────────────────────
import json, pathlib

PREDICTION_LOG = pathlib.Path(__file__).parent / "prediction_log.json"

def save_prediction(ticker: str, company_name: str, predicted_direction: str,
                    predicted_pct_low: float, predicted_pct_high: float,
                    predicted_price_low: float, predicted_price_high: float,
                    current_price: float, analysis_date: str):
    """AI 예측 결과 저장"""
    try:
        log = _load_log()
        entry = {
            "id":                   f"{ticker}_{analysis_date.replace('-','')}",
            "ticker":               ticker,
            "company_name":         company_name,
            "analysis_date":        analysis_date,
            "current_price":        current_price,
            "predicted_direction":  predicted_direction,   # 상승/하락/보합
            "predicted_pct_low":    predicted_pct_low,
            "predicted_pct_high":   predicted_pct_high,
            "predicted_price_low":  predicted_price_low,
            "predicted_price_high": predicted_price_high,
            "actual_price":         None,     # 다음날 채워짐
            "actual_direction":     None,
            "actual_pct":           None,
            "hit":                  None,     # 방향 적중 여부
            "in_range":             None,     # 등락률 범위 내 여부
            "verified_at":          None,
        }
        # 이미 같은 ID 있으면 업데이트
        existing = next((i for i, e in enumerate(log) if e["id"] == entry["id"]), None)
        if existing is not None:
            log[existing] = entry
        else:
            log.append(entry)

        PREDICTION_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry
    except Exception as e:
        return {"error": str(e)}


def verify_predictions(ticker: str = None):
    """
    저장된 예측 중 아직 검증 안 된 것들을 실제 주가로 검증.
    매 분석 시작 시 자동 호출.
    """
    try:
        log  = _load_log()
        updated = 0

        for entry in log:
            if entry.get("verified_at"):
                continue
            if ticker and entry["ticker"] != ticker:
                continue

            analysis_date = entry.get("analysis_date", "")
            if not analysis_date:
                continue

            # 분석일 다음날 종가 수집
            try:
                from datetime import datetime as dt, timedelta as td
                target_dt = dt.strptime(analysis_date, "%Y-%m-%d") + td(days=1)
                # 주말 건너뜀
                while target_dt.weekday() >= 5:
                    target_dt += td(days=1)

                # 아직 미래면 스킵
                if target_dt.date() > dt.now().date():
                    continue

                t      = yf.Ticker(entry["ticker"])
                # 목표일 ~ +3일 범위로 조회 (공휴일 대비)
                end_dt = target_dt + td(days=4)
                hist   = t.history(start=target_dt.strftime("%Y-%m-%d"),
                                   end=end_dt.strftime("%Y-%m-%d"))

                if hist.empty:
                    continue

                actual_price = round(float(hist.iloc[0]["Close"]), 2)
                base_price   = entry["current_price"]
                actual_pct   = round((actual_price - base_price) / base_price * 100, 2)

                actual_dir = "상승" if actual_pct > 0.3 else "하락" if actual_pct < -0.3 else "보합"
                hit        = (actual_dir == entry["predicted_direction"])
                low, high  = entry.get("predicted_pct_low", -999), entry.get("predicted_pct_high", 999)
                in_range   = (low <= actual_pct <= high)

                entry["actual_price"]     = actual_price
                entry["actual_direction"] = actual_dir
                entry["actual_pct"]       = actual_pct
                entry["hit"]              = hit
                entry["in_range"]         = in_range
                entry["verified_at"]      = dt.now().strftime("%Y-%m-%d")
                updated += 1

            except Exception:
                continue

        if updated > 0:
            PREDICTION_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        return {"updated": updated, "total": len(log)}
    except Exception as e:
        return {"error": str(e)}


def get_prediction_stats(ticker: str = None):
    """예측 정확도 통계 반환"""
    try:
        log = _load_log()
        entries = [e for e in log if e.get("verified_at")]
        if ticker:
            ticker_entries = [e for e in entries if e["ticker"] == ticker]
        else:
            ticker_entries = entries

        if not ticker_entries:
            return {
                "available": False,
                "reason": "검증된 예측 데이터 없음",
                "all_history": [e for e in log if (not ticker or e["ticker"] == ticker)],
            }

        total    = len(ticker_entries)
        hits     = sum(1 for e in ticker_entries if e.get("hit"))
        in_range = sum(1 for e in ticker_entries if e.get("in_range"))
        up_pred  = [e for e in ticker_entries if e["predicted_direction"] == "상승"]
        dn_pred  = [e for e in ticker_entries if e["predicted_direction"] == "하락"]

        return {
            "available":       True,
            "total":           total,
            "direction_hits":  hits,
            "direction_acc":   round(hits / total * 100, 1),
            "range_hits":      in_range,
            "range_acc":       round(in_range / total * 100, 1),
            "up_predictions":  len(up_pred),
            "up_hits":         sum(1 for e in up_pred if e.get("hit")),
            "down_predictions": len(dn_pred),
            "down_hits":       sum(1 for e in dn_pred if e.get("hit")),
            "recent_history":  ticker_entries[-10:][::-1],   # 최근 10개 역순
            "all_history":     [e for e in log if (not ticker or e["ticker"] == ticker)],
        }
    except Exception as e:
        return {"available": False, "reason": str(e), "all_history": []}


def _load_log() -> list:
    if PREDICTION_LOG.exists():
        try:
            return json.loads(PREDICTION_LOG.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def collect_all(ticker: str, company_name: str = "", country: str = "한국"):
    """모든 데이터 한번에 수집"""
    print(f"📊 데이터 수집 시작: {ticker} ({company_name})")

    # 이전 예측 자동 검증
    verify_result = verify_predictions(ticker)
    if verify_result.get("updated", 0) > 0:
        print(f"  ✅ 이전 예측 {verify_result['updated']}건 검증 완료")

    stock = get_stock_data(ticker)
    print(f"  ✅ 주가 수집 완료")

    indicators = get_market_indicators()
    print(f"  ✅ 시장 지표 수집 완료")

    technicals = get_technicals(ticker)
    if technicals.get("available"):
        print(f"  ✅ 기술적 지표 수집 완료")
    else:
        print(f"  ⚠️  기술적 지표: {technicals.get('reason', '수집 불가')}")

    financials = get_financials(ticker, country)
    if financials.get("available"):
        print(f"  ✅ 재무 지표 수집 완료")
    else:
        print(f"  ⚠️  재무 지표: {financials.get('reason', '수집 불가')}")

    investor = get_investor_trading(ticker)
    if investor.get("available"):
        print(f"  ✅ 외국인/기관 거래량 수집 완료")
    else:
        print(f"  ⚠️  외국인/기관 거래량: {investor.get('reason', '수집 불가')}")

    news = get_news(ticker, company_name, country)
    print(f"  ✅ 뉴스 수집 완료 ({news.get('total', 0)}건)")

    pred_stats = get_prediction_stats(ticker)

    return {
        "ticker":            ticker,
        "company_name":      company_name,
        "country":           country,
        "collected_at":      datetime.now().isoformat(),
        "stock":             stock,
        "market_indicators": indicators,
        "technicals":        technicals,
        "financials":        financials,
        "investor_trading":  investor,
        "news":              news,
        "prediction_stats":  pred_stats,
    }


# 테스트
if __name__ == "__main__":
    result = collect_all("005930.KS", "삼성전자", "한국")
    print("\n📈 삼성전자 현재가:", result["stock"].get("current_price"))
    print("💵 달러/원 환율:", result["market_indicators"]["usd_krw"].get("price"))

    investor = result["investor_trading"]
    if investor.get("available"):
        summary = investor.get("5day_summary", {})
        print(f"\n👥 최근 5일 순매수")
        print(f"  외국인: {summary.get('foreign_net'):,}원")
        print(f"  기관:   {summary.get('institution_net'):,}원")
        print(f"  개인:   {summary.get('individual_net'):,}원")
    else:
        print(f"\n⚠️  투자자 데이터: {investor.get('reason')}")