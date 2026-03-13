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


def get_news(query: str, company_name: str = "", days: int = 7):
    """뉴스 수집 (NewsAPI)"""
    if not NEWS_API_KEY:
        return {"total": 0, "articles": [], "reason": "NEWS_API_KEY 없음"}

    try:
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        search_query = f"{query} {company_name}".strip()

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": search_query,
            "from": from_date,
            "sortBy": "relevancy",
            "language": "ko",
            "pageSize": 10,
            "apiKey": NEWS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            params["language"] = "en"
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

        articles = data.get("articles", [])

        return {
            "total": len(articles),
            "articles": [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", ""),
                    "url": a.get("url", ""),
                }
                for a in articles[:10]
            ],
        }
    except Exception as e:
        return {"total": 0, "articles": [], "reason": str(e)}


def collect_all(ticker: str, company_name: str = "", country: str = "한국"):
    """모든 데이터 한번에 수집"""
    print(f"📊 데이터 수집 시작: {ticker} ({company_name})")

    stock = get_stock_data(ticker)
    print(f"  ✅ 주가 수집 완료")

    indicators = get_market_indicators()
    print(f"  ✅ 시장 지표 수집 완료")

    investor = get_investor_trading(ticker)
    if investor.get("available"):
        print(f"  ✅ 외국인/기관 거래량 수집 완료")
    else:
        print(f"  ⚠️  외국인/기관 거래량: {investor.get('reason', '수집 불가')}")

    news = get_news(ticker, company_name)
    print(f"  ✅ 뉴스 수집 완료")

    return {
        "ticker": ticker,
        "company_name": company_name,
        "country": country,
        "collected_at": datetime.now().isoformat(),
        "stock": stock,
        "market_indicators": indicators,
        "investor_trading": investor,
        "news": news,
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