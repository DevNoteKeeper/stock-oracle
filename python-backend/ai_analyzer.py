import requests
import json
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
MODEL      = "llama-3.1-8b-instant"

# ── 키 로테이션 ───────────────────────────────────────────────────
GROQ_KEYS = [k for k in [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
] if k]

_key_index = 0

def _get_key() -> str | None:
    """순서대로 키 반환"""
    if not GROQ_KEYS:
        return None
    return GROQ_KEYS[_key_index % len(GROQ_KEYS)]

def _rotate_key():
    """다음 키로 전환"""
    global _key_index
    _key_index += 1

def _is_rate_limit(status_code: int, text: str = "") -> bool:
    return status_code == 429 or "rate_limit" in text.lower() or "too many" in text.lower()


def build_prompt(data: dict) -> str:
    """분석 프롬프트 생성"""

    stock        = data.get("stock", {})
    indicators   = data.get("market_indicators", {})
    news         = data.get("news", {})
    investor     = data.get("investor_trading", {})
    company_name = data.get("company_name", data.get("ticker"))
    country      = data.get("country", "")
    ticker       = data.get("ticker", "")
    period       = data.get("period", "tomorrow")

    # ── 시장 지표 ─────────────────────────────────────────────────
    kospi          = indicators.get("kospi", {})
    usd_krw        = indicators.get("usd_krw", {})
    oil            = indicators.get("oil_wti", {})
    sp500_futures  = indicators.get("sp500_futures", {})
    nasdaq_futures = indicators.get("nasdaq_futures", {})
    gold           = indicators.get("gold", {})

    def fmt_pct(val):
        if val is None: return "N/A"
        sign = "+" if float(val) > 0 else ""
        return f"{sign}{float(val):.2f}%"

    def direction_label(val):
        v = float(val) if val else 0
        if v >= 1.0:  return "강한 상승"
        if v >= 0.3:  return "약한 상승"
        if v <= -1.0: return "강한 하락"
        if v <= -0.3: return "약한 하락"
        return "보합"

    # ── 52주 위치 계산 ────────────────────────────────────────────
    cur     = float(stock.get("current_price", 0))
    high    = float(stock.get("high_52w", 1))
    low     = float(stock.get("low_52w", 0))
    w52_pct = ((cur - low) / (high - low) * 100) if high != low else 50
    w52_label = (
        "52주 신고가 근처 (과열 가능성)"  if w52_pct >= 90 else
        "52주 고점대 (상단 저항 존재)"    if w52_pct >= 70 else
        "52주 중간대 (방향성 탐색 중)"    if w52_pct >= 40 else
        "52주 저점대 (반등 가능성)"        if w52_pct >= 15 else
        "52주 신저가 근처 (추가 하락 위험)"
    )

    # ── 거래량 해석 ───────────────────────────────────────────────
    vol     = int(stock.get("volume", 0))
    history = stock.get("history", [])
    if len(history) >= 10:
        avg_vol   = sum(d["volume"] for d in history[-10:]) / 10
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0
        vol_label = (
            f"10일 평균 대비 {vol_ratio:.1f}배 — 거래 폭발적 증가" if vol_ratio >= 2.0 else
            f"10일 평균 대비 {vol_ratio:.1f}배 — 거래 증가"         if vol_ratio >= 1.3 else
            f"10일 평균 대비 {vol_ratio:.1f}배 — 거래 감소"         if vol_ratio <= 0.7 else
            f"10일 평균 대비 {vol_ratio:.1f}배 — 평균 수준"
        )
    else:
        vol_label = f"{vol:,}주"

    # ── 최근 5일 주가 추세 ────────────────────────────────────────
    price_trend = ""
    if len(history) >= 5:
        closes    = [d["close"] for d in history[-5:]]
        diffs     = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        ups       = sum(1 for d in diffs if d > 0)
        downs     = sum(1 for d in diffs if d < 0)
        total_chg = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
        price_trend = (
            f"최근 5거래일: {ups}일 상승 / {downs}일 하락, 누적 {total_chg:+.2f}%\n"
            f"  5일 종가: {' → '.join(str(int(c)) for c in closes)}"
        )

    # ── 외국인/기관 수급 ──────────────────────────────────────────
    def signed(val):
        v = int(val) if val else 0
        return f"+{v:,}" if v > 0 else f"{v:,}"

    investor_block = ""
    if investor.get("available"):
        summary         = investor.get("5day_summary", {})
        hist_inv        = investor.get("history", [])
        foreign_net     = summary.get("foreign_net", 0)
        institution_net = summary.get("institution_net", 0)

        if foreign_net > 0 and institution_net > 0:
            flow_signal = "★ 외국인·기관 동반 순매수 → 강한 매수세"
        elif foreign_net < 0 and institution_net < 0:
            flow_signal = "★ 외국인·기관 동반 순매도 → 강한 매도세"
        elif foreign_net > 0:
            flow_signal = "★ 외국인 순매수 / 기관 순매도 → 혼조세"
        else:
            flow_signal = "★ 외국인 순매도 / 기관 순매수 → 혼조세"

        daily_rows = ""
        for d in hist_inv:
            f_val = int(d.get("foreign", 0))
            i_val = int(d.get("institution", 0))
            f_sym = "▲" if f_val > 0 else "▼" if f_val < 0 else "─"
            i_sym = "▲" if i_val > 0 else "▼" if i_val < 0 else "─"
            daily_rows += f"  {d['date']}  외국인 {f_sym} {signed(f_val)}주  기관 {i_sym} {signed(i_val)}주\n"

        investor_block = (
            f"10일 누적  외국인: {signed(summary.get('foreign_net', 0) if len(hist_inv) >= 10 else foreign_net)}주 / "
            f"기관: {signed(institution_net)}주\n"
            f"5일 누적   외국인: {signed(foreign_net)}주 / 기관: {signed(institution_net)}주\n"
            f"{flow_signal}\n\n일별 상세:\n{daily_rows.rstrip()}"
        )
    else:
        investor_block = f"수급 데이터 없음 ({investor.get('reason', '')})"

    # ── 뉴스 블록 ─────────────────────────────────────────────────
    news_block = ""
    articles   = news.get("articles", [])[:8]
    sentiment  = news.get("sentiment_summary", {})
    cat_counts = news.get("category_counts", {})
    top_kw     = news.get("top_keywords", [])

    pos_c   = sentiment.get("positive", 0)
    neg_c   = sentiment.get("negative", 0)
    neu_c   = sentiment.get("neutral", 0)
    total_n = pos_c + neg_c + neu_c
    score   = sentiment.get("score", 0)

    news_block += f"  감성: 긍정 {pos_c}건 / 부정 {neg_c}건 / 중립 {neu_c}건  점수 {score:+.2f}\n"
    news_block += f"  카테고리: {'  '.join(f'{k}:{v}건' for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])[:5]) or '없음'}\n"
    news_block += f"  키워드: {', '.join(top_kw[:8]) or '없음'}\n\n"

    for i, a in enumerate(articles, 1):
        title     = a.get("title", "").strip()
        desc      = (a.get("description") or "").strip()
        src       = a.get("source", "")
        pub       = a.get("published_at", "")[:10]
        senti_tag = {"긍정": "📈", "부정": "📉", "중립": "📰"}.get(a.get("sentiment", ""), "📰")
        cats      = "/".join(a.get("categories", []))
        if not title: continue
        news_block += f"  [{i}] {senti_tag} {title}"
        if src:  news_block += f"  ({src})"
        if pub:  news_block += f"  [{pub}]"
        if cats: news_block += f"  [{cats}]"
        if desc and len(desc) < 150:
            news_block += f"\n      → {desc}"
        news_block += "\n"

    if not articles:
        news_block = "  관련 뉴스 없음\n"

    # ── 기술적 지표 블록 ──────────────────────────────────────────
    tech             = data.get("technicals", {})
    technicals_block = ""
    if tech.get("available"):
        def fv_tech(v, suffix="", digits=2):
            if v is None: return "N/A"
            return f"{round(float(v), digits)}{suffix}"

        def ma_pos(ma_val):
            if ma_val is None: return ""
            return "위 ↑" if cur > ma_val else "아래 ↓"

        hist_val = tech.get("histogram")
        hist_dir = "양수 (매수 압력)" if hist_val and hist_val > 0 else "음수 (매도 압력)" if hist_val else ""
        pct_b    = tech.get("bb_pct_b")
        pct_b_str = f"{round(pct_b * 100, 1)}%" if pct_b is not None else "N/A"

        def stoch_label(k):
            if k is None: return ""
            if k >= 80: return "과매수"
            if k <= 20: return "과매도"
            return "중립"

        technicals_block = (
            f"▶ 기술적 지표\n"
            f"  MA5:{fv_tech(tech.get('ma5'))}({ma_pos(tech.get('ma5'))}) "
            f"MA20:{fv_tech(tech.get('ma20'))}({ma_pos(tech.get('ma20'))}) "
            f"MA60:{fv_tech(tech.get('ma60'))}({ma_pos(tech.get('ma60'))}) "
            f"크로스:{tech.get('ma_cross') or '없음'}\n"
            f"  RSI:{fv_tech(tech.get('rsi'))} {tech.get('rsi_label','')} / 3일추세:{tech.get('rsi_trend') or 'N/A'}\n"
            f"  MACD:{fv_tech(tech.get('macd_line'),digits=4)} 시그널:{fv_tech(tech.get('signal_line'),digits=4)} "
            f"히스토:{fv_tech(tech.get('histogram'),digits=4)}({hist_dir}) {tech.get('macd_cross') or ''}\n"
            f"  BB상단:{fv_tech(tech.get('bb_upper'))} 중심:{fv_tech(tech.get('bb_middle'))} "
            f"하단:{fv_tech(tech.get('bb_lower'))} %B:{pct_b_str} {tech.get('bb_label','')}\n"
            f"  스토캐스틱 %K:{fv_tech(tech.get('stoch_k'))} %D:{fv_tech(tech.get('stoch_d'))} "
            f"{stoch_label(tech.get('stoch_k'))}\n"
            f"  거래량 20일평균:{int(tech.get('vol_ma20') or 0):,}주 오늘비율:{fv_tech(tech.get('vol_ratio'))}배"
        )
    else:
        technicals_block = f"  기술적 지표 계산 불가 ({tech.get('reason', '')})"

    # ── 재무 지표 블록 ────────────────────────────────────────────
    fin              = data.get("financials", {})
    financials_block = ""
    if fin.get("available"):
        def fv_fin(v, suffix=""):
            if v is None: return "N/A"
            return f"{v}{suffix}"

        def growth_label(v):
            if v is None: return ""
            if v > 20:  return "(고성장)"
            if v > 5:   return "(성장)"
            if v > 0:   return "(소폭성장)"
            if v > -10: return "(소폭감소)"
            return "(역성장)"

        mc = fin.get("market_cap")
        if mc:
            if mc >= 1_0000_0000_0000: mc_str = f"{mc/1_0000_0000_0000:.1f}조원"
            elif mc >= 1_0000_0000:    mc_str = f"{mc/1_0000_0000:.0f}억원"
            else:                       mc_str = f"{mc:,}원"
        else:
            mc_str = "N/A"

        financials_block = (
            f"▶ 재무 지표\n"
            f"  PER:{fv_fin(fin.get('per'))}({fin.get('per_label','')}) "
            f"PBR:{fv_fin(fin.get('pbr'))}({fin.get('pbr_label','')}) "
            f"시가총액:{mc_str}\n"
            f"  ROE:{fv_fin(fin.get('roe'),'%')} 영업이익률:{fv_fin(fin.get('op_margin'),'%')} "
            f"순이익률:{fv_fin(fin.get('net_margin'),'%')}\n"
            f"  매출성장:{fv_fin(fin.get('revenue_growth'),'%')}{growth_label(fin.get('revenue_growth'))} "
            f"순이익성장:{fv_fin(fin.get('earnings_growth'),'%')}{growth_label(fin.get('earnings_growth'))}\n"
            f"  부채비율:{fv_fin(fin.get('debt_to_equity'),'%')} 유동비율:{fv_fin(fin.get('current_ratio'))}"
        )
    else:
        financials_block = f"  재무 데이터 수집 불가 ({fin.get('reason', '')})"

    # ── 시장 방향 해석 ────────────────────────────────────────────
    market_signals = []
    kospi_pct  = float(kospi.get("change_pct", 0) or 0)
    sp500_pct  = float(sp500_futures.get("change_pct", 0) or 0)
    nasdaq_pct = float(nasdaq_futures.get("change_pct", 0) or 0)
    usd_pct    = float(usd_krw.get("change_pct", 0) or 0)
    gold_pct   = float(gold.get("change_pct", 0) or 0)

    if kospi_pct > 0.5:    market_signals.append("코스피 강세 → 국내 매수 심리")
    elif kospi_pct < -0.5: market_signals.append("코스피 약세 → 국내 매도 심리")
    if sp500_pct > 0.3 or nasdaq_pct > 0.3:
        market_signals.append("미국 선물 상승 → 글로벌 위험선호")
    elif sp500_pct < -0.3 or nasdaq_pct < -0.3:
        market_signals.append("미국 선물 하락 → 글로벌 위험회피")
    if usd_pct > 0.3:    market_signals.append(f"달러 강세({usd_pct:+.2f}%) → 외국인 매도 유인")
    elif usd_pct < -0.3: market_signals.append(f"달러 약세({usd_pct:+.2f}%) → 외국인 매수 유인")
    if gold_pct > 0.5:   market_signals.append("금 상승 → 안전자산 선호")
    market_summary = "\n".join(f"  • {s}" for s in market_signals) if market_signals else "  • 특이 신호 없음"

    # ── 보유 포지션 블록 ──────────────────────────────────────────
    pos            = data.get("position")
    position_block = ""
    section_11     = ""

    if pos:
        pl      = pos.get("profit_loss", 0)
        pl_pct  = pos.get("profit_loss_pct", 0)
        pl_sign = "+" if pl >= 0 else ""
        qty     = pos.get("quantity", 0)
        avg_p   = pos.get("avg_price", 0)
        tgt_p   = pos.get("target_sell_price")
        tgt_pct = pos.get("target_profit_pct")
        tgt_amt = pos.get("target_profit_amount")
        gap_pct = pos.get("gap_to_target_pct")
        gap_price = pos.get("gap_to_target_price")

        if pl_pct >= 10:    pl_status = "수익 구간 (익절 검토)"
        elif pl_pct >= 3:   pl_status = "소폭 수익 중"
        elif pl_pct >= -3:  pl_status = "손익분기 근처"
        elif pl_pct >= -10: pl_status = "소폭 손실 중"
        else:               pl_status = "손실 구간 (추가매수 or 손절 검토)"

        position_block = (
            f"  보유: {qty:,.0f}주 / 평균매수가: {avg_p:,.0f}원\n"
            f"  평가손익: {pl_sign}{pl:,.0f}원 ({pl_sign}{pl_pct:.2f}%) — {pl_status}\n"
        )
        if tgt_p:
            position_block += (
                f"  희망매도가: {tgt_p:,.0f}원 (수익률 {tgt_pct:+.1f}%, 수익금 +{tgt_amt:,.0f}원)\n"
                f"  현재→목표: {gap_price:+,.0f}원 ({gap_pct:+.2f}% 필요)\n"
            )

        section_11 = (
            f"\n## 11. 보유 포지션 전략\n"
            f"보유: {qty:,.0f}주 @ 평균 {avg_p:,.0f}원 / 현재 {pl_sign}{pl_pct:.2f}% ({pl_sign}{pl:,.0f}원)\n"
        )
        if tgt_p:
            section_11 += (
                f"희망매도가: {tgt_p:,.0f}원 (목표수익률 {tgt_pct:+.1f}%, 목표수익금 +{tgt_amt:,.0f}원)\n"
                f"달성까지 {gap_price:+,.0f}원 / {gap_pct:+.2f}% 필요\n\n"
                f"**희망 매도가 {tgt_p:,.0f}원 달성 분석**:\n"
                f"- 달성 가능성: 높음/보통/낮음 중 판단\n"
                f"- 예상 도달 기간: 단기(1~2주)/중기(1~3개월)/장기(3개월+)\n"
                f"- 달성 조건 2~3가지 (구체적 지표)\n"
                f"- 리스크 높을 경우 중간 익절 구간 제시 (금액 명시)\n\n"
            )
        section_11 += (
            f"**현재 포지션 진단**: 보유 유지 여부와 이유\n\n"
            f"**익절 전략** (원 단위 금액 필수):\n"
            f"- 1차 목표가: XX원 → 수익금 +XX원\n"
            f"- 2차 목표가: XX원 → 수익금 +XX원\n\n"
            f"**추가매수 전략** (원 단위 금액 필수):\n"
            f"- 적정가: XX원 이하 → 추가 후 평균단가 XX원\n\n"
            f"**손절 기준** (원 단위 금액 필수):\n"
            f"- 손절가: XX원 → 손실금 -XX원\n\n"
            f"**최종 권고**: 지금 취해야 할 행동 1가지 (금액 포함)\n"
        )

    # ── 요일 감지 ─────────────────────────────────────────────────
    from datetime import datetime as _dt
    weekday = _dt.now().weekday()
    weekend_warning = ""
    if weekday in (5, 6):
        weekend_warning = (
            "\n⚠️ 【주말 분석 주의】 현재 데이터는 직전 금요일 종가 기준입니다.\n"
            "월요일 갭상승 패턴 / 주말 뉴스 변수 반드시 고려.\n"
            "신뢰도는 '낮음'으로 설정하고 등락률 범위를 2배 넓게 잡을 것.\n"
        )
    elif weekday == 4:
        weekend_warning = (
            "\n⚠️ 【금요일 주의】 주말 전 포지션 정리 매물 및 월요일 갭상승 변수 고려.\n"
        )
    elif weekday == 0:
        weekend_warning = (
            "\n💡 【월요일】 주말 변수가 시가에 반영됐을 수 있음. 갭 이후 방향성 주목.\n"
        )

    # ── ATR 기반 현실적 등락률 범위 사전 계산 ───────────────────────
    atr_block = ""
    atr_pct   = None
    if len(history) >= 10:
        daily_changes = [
            abs((history[i]["close"] - history[i-1]["close"]) / history[i-1]["close"] * 100)
            for i in range(1, len(history))
        ]
        atr_pct = round(sum(daily_changes[-10:]) / min(10, len(daily_changes)), 2)

        closes5    = [d["close"] for d in history[-5:]]
        chg5       = round((closes5[-1] - closes5[0]) / closes5[0] * 100, 2)
        up_days    = sum(1 for i in range(1, len(closes5)) if closes5[i] > closes5[i-1])
        dn_days    = len(closes5) - 1 - up_days
        trend_desc = f"상승 {up_days}일 / 하락 {dn_days}일, 누적 {chg5:+.2f}%"

        atr_block = (
            f"\n📐 통계 기반 참고 범위\n"
            f"  - 최근 10일 평균 일간 변동폭(ATR): ±{atr_pct:.2f}%\n"
            f"  - 최근 5일 추세: {trend_desc}\n"
            f"  ※ ATR의 2배 이상 범위는 특별한 이벤트 없이는 쓰지 마세요.\n"
        )

    # ── 신호 카운터: 기술지표 + 시장지표를 코드로 점수화 ────────────
    up_signals   = []
    down_signals = []

    # 1. RSI
    rsi_val = tech.get("rsi") if tech.get("available") else None
    if rsi_val is not None:
        if rsi_val >= 60:
            up_signals.append(f"RSI {rsi_val} (강세)")
        elif rsi_val <= 40:
            down_signals.append(f"RSI {rsi_val} (약세/과매도)")

    # 2. MACD 히스토그램 방향
    hist_val = tech.get("histogram") if tech.get("available") else None
    if hist_val is not None:
        if hist_val > 0:
            up_signals.append(f"MACD 히스토그램 양수({round(hist_val,1)}) → 매수압력")
        else:
            down_signals.append(f"MACD 히스토그램 음수({round(hist_val,1)}) → 매도압력")

    # 3. MA 배열 (현재가 vs MA5/MA20/MA60)
    ma5_val  = tech.get("ma5")  if tech.get("available") else None
    ma20_val = tech.get("ma20") if tech.get("available") else None
    ma60_val = tech.get("ma60") if tech.get("available") else None
    if ma5_val and cur > ma5_val:
        up_signals.append(f"현재가 > MA5({ma5_val:,.0f})")
    elif ma5_val and cur < ma5_val:
        down_signals.append(f"현재가 < MA5({ma5_val:,.0f})")
    if ma20_val and cur > ma20_val:
        up_signals.append(f"현재가 > MA20({ma20_val:,.0f})")
    elif ma20_val and cur < ma20_val:
        down_signals.append(f"현재가 < MA20({ma20_val:,.0f})")
    if ma60_val and cur > ma60_val:
        up_signals.append(f"현재가 > MA60({ma60_val:,.0f})")
    elif ma60_val and cur < ma60_val:
        down_signals.append(f"현재가 < MA60({ma60_val:,.0f})")

    # 4. 볼린저밴드 %B
    bb_val = tech.get("bb_pct_b") if tech.get("available") else None
    if bb_val is not None:
        if bb_val >= 0.7:
            up_signals.append(f"볼린저 %B {round(bb_val*100,1)}% (상단 근접)")
        elif bb_val <= 0.3:
            down_signals.append(f"볼린저 %B {round(bb_val*100,1)}% (하단 근접)")

    # 5. 코스피 등락
    if kospi_pct >= 1.0:
        up_signals.append(f"코스피 {kospi_pct:+.2f}% (강세)")
    elif kospi_pct <= -1.0:
        down_signals.append(f"코스피 {kospi_pct:+.2f}% (약세)")

    # 6. S&P500 선물
    if sp500_pct >= 1.0:
        up_signals.append(f"S&P500선물 {sp500_pct:+.2f}% (강세)")
    elif sp500_pct <= -1.0:
        down_signals.append(f"S&P500선물 {sp500_pct:+.2f}% (약세)")

    # 7. 달러/원 (강달러 → 외국인 매도)
    if usd_pct >= 0.5:
        down_signals.append(f"달러/원 {usd_pct:+.2f}% (강달러→외국인매도)")
    elif usd_pct <= -0.5:
        up_signals.append(f"달러/원 {usd_pct:+.2f}% (약달러→외국인매수)")

    # 8. 최근 5일 추세
    if len(history) >= 5:
        closes5 = [d["close"] for d in history[-5:]]
        chg5    = (closes5[-1] - closes5[0]) / closes5[0] * 100
        if chg5 >= 2.0:
            up_signals.append(f"5일 누적 {chg5:+.2f}% (상승추세)")
        elif chg5 <= -2.0:
            down_signals.append(f"5일 누적 {chg5:+.2f}% (하락추세)")

    # 9. 외국인/기관 수급
    inv = data.get("investor_trading", {})
    if inv.get("available"):
        s = inv.get("5day_summary", {})
        fn = s.get("foreign_net", 0)
        inst = s.get("institution_net", 0)
        if fn > 0:
            up_signals.append(f"외국인 5일 순매수 +{fn:,}주")
        elif fn < 0:
            down_signals.append(f"외국인 5일 순매도 {fn:,}주")
        if inst > 0:
            up_signals.append(f"기관 5일 순매수 +{inst:,}주")
        elif inst < 0:
            down_signals.append(f"기관 5일 순매도 {inst:,}주")

    # ── 종합 판정 ─────────────────────────────────────────────────
    n_up   = len(up_signals)
    n_down = len(down_signals)
    score  = n_up - n_down  # 양수=상승우세, 음수=하락우세

    if score >= 3:
        verdict = f"🟢 상승 우세 (상승신호 {n_up}개 vs 하락신호 {n_down}개) → '상승' 예측 강력 권고"
    elif score <= -3:
        verdict = f"🔴 하락 우세 (하락신호 {n_down}개 vs 상승신호 {n_up}개) → '하락' 예측 강력 권고"
    elif score >= 1:
        verdict = f"🟡 상승 약우세 (상승신호 {n_up}개 vs 하락신호 {n_down}개) → '보합' 또는 '상승' 검토"
    elif score <= -1:
        verdict = f"🟡 하락 약우세 (하락신호 {n_down}개 vs 상승신호 {n_up}개) → '보합' 또는 '하락' 검토"
    else:
        verdict = f"⚪ 신호 균형 (상승 {n_up}개 = 하락 {n_down}개) → '보합' 예측 권고"

    signal_lines = []
    if up_signals:
        signal_lines.append(f"  📈 상승 신호 ({n_up}개): " + " / ".join(up_signals))
    if down_signals:
        signal_lines.append(f"  📉 하락 신호 ({n_down}개): " + " / ".join(down_signals))
    signal_lines.append(f"  ▶ 종합: {verdict}")

    signal_counter_block = (
        f"\n🔢 사전 신호 집계 (코드 자동 산출 — 반드시 참고하세요)\n"
        + "\n".join(signal_lines) + "\n"
    )

    # ── 방향별 비대칭 범위 힌트 ───────────────────────────────────
    # 상승 예측 시 범위를 양수 쪽으로, 하락 예측 시 음수 쪽으로 shift
    range_hint = ""
    if atr_pct:
        if score >= 3:
            # 상승 강력: 하단을 ATR*0.3으로 좁히고 상단을 ATR*2로 열기
            r_low  = round(atr_pct * 0.3, 1)
            r_high = round(atr_pct * 2.0, 1)
            range_hint = (
                f"\n📏 방향별 권장 등락률 범위\n"
                f"  상승 예측 시: +{r_low}% ~ +{r_high}% (하락 가능성 낮으므로 상단 확장)\n"
                f"  ※ 상승 예측인데 범위를 대칭(-X%~+X%)으로 쓰지 마세요.\n"
            )
        elif score <= -3:
            r_low  = round(atr_pct * 2.0, 1)
            r_high = round(atr_pct * 0.3, 1)
            range_hint = (
                f"\n📏 방향별 권장 등락률 범위\n"
                f"  하락 예측 시: -{r_low}% ~ -{r_high}% (상승 가능성 낮으므로 하단 확장)\n"
                f"  ※ 하락 예측인데 범위를 대칭(-X%~+X%)으로 쓰지 마세요.\n"
            )
        else:
            r = round(atr_pct * 1.2, 1)
            range_hint = (
                f"\n📏 방향별 권장 등락률 범위\n"
                f"  보합 예측 시: -{r}% ~ +{r}% (대칭 범위 사용)\n"
            )

    signal_counter_block += range_hint

    # ── Firebase 학습 메모리 주입 ─────────────────────────────────
    memory_block = ""
    try:
        from firebase_memory import get_memory
        mem = get_memory()
        if mem.enabled:
            current_signals = {
                "rsi":       tech.get("rsi") if tech.get("available") else None,
                "macd_hist": tech.get("histogram") if tech.get("available") else None,
                "kospi_pct": kospi_pct,
                "sp500_pct": sp500_pct,
                "usd_pct":   usd_pct,
            }
            memory_block = mem.build_memory_block(ticker, current_signals)
    except Exception:
        pass  # Firebase 없어도 정상 동작

    # ── 예측 기간 레이블 ──────────────────────────────────────────
    period_label = {"tomorrow": "내일 (1거래일)", "week": "1주일 (5거래일)", "month": "1개월 (20거래일)"}.get(period, "내일")
    section_count = "11개" if pos else "10개"

    # ── 프롬프트 조합 ─────────────────────────────────────────────
    prompt = (
        f"당신은 국내 증권사 15년 경력 수석 애널리스트입니다.\n"
        f"제공된 실제 시장 데이터만을 근거로 분석하세요. 반드시 수치를 인용하세요.\n"
        f"【중요】아래 '사전 신호 집계'의 종합 판정을 반드시 따르세요. "
        f"신호가 혼조적이거나 약하면 반드시 '보합'으로 예측하세요.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"■ 분석 대상: {company_name} ({country} / {ticker})\n"
        f"■ 예측 기간: {period_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{atr_block}"
        f"{signal_counter_block}"
        f"{memory_block}"
        f"▶ 현재 주가\n"
        f"  현재가:{cur:,.0f}원 / 전일대비:{stock.get('change'):+,.0f}원({fmt_pct(stock.get('change_pct'))})\n"
        f"  52주:{low:,.0f}~{high:,.0f}원 (현재위치 {w52_pct:.1f}% → {w52_label})\n"
        f"  거래량:{vol:,}주 ({vol_label})\n\n"
        f"▶ 최근 5거래일\n  {price_trend}\n\n"
        f"▶ 시장 지표\n"
        f"  코스피:{kospi.get('price')}({fmt_pct(kospi.get('change_pct'))}) "
        f"달러/원:{usd_krw.get('price')}({fmt_pct(usd_krw.get('change_pct'))})\n"
        f"  WTI:${oil.get('price')}({fmt_pct(oil.get('change_pct'))}) "
        f"S&P500:{sp500_futures.get('price')}({fmt_pct(sp500_futures.get('change_pct'))}) "
        f"금:${gold.get('price')}({fmt_pct(gold.get('change_pct'))})\n\n"
        f"▶ 시장 신호\n{market_summary}\n\n"
        f"{financials_block}\n\n"
        f"{technicals_block}\n\n"
        f"▶ 외국인·기관 수급\n{investor_block}\n\n"
        f"▶ 뉴스·이슈\n{news_block}\n"
    )

    if weekend_warning:
        prompt += weekend_warning + "\n"

    if position_block:
        prompt += f"\n▶ 보유 포지션\n{position_block}\n"

    prompt += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n아래 {section_count} 섹션을 순서대로 작성하세요.\n\n"

    prompt += (
        f"## 1. 종합 시황 분석\n"
        f"코스피 {fmt_pct(kospi.get('change_pct'))}, 달러/원 {usd_krw.get('price')}원, 미국 선물이 {company_name}에 미치는 영향\n\n"
        f"## 2. 뉴스·이슈 심층 분석\n"
        f"감성점수 {score:+.2f} 기반 핵심이슈 3가지 (호재/악재/중립 판정, 영향강도 명시)\n\n"
        f"## 3. 재무 가치 분석\n"
        f"PER/PBR 평가, ROE·영업이익률, 성장률 시사점, 재무 안정성\n\n"
        f"## 4. 기술적 지표 분석\n"
        f"RSI·MACD·볼린저밴드·MA 배열 판단, 지표 합의도\n\n"
        f"## 5. 상승 요인\n"
        f"구체적 수치 기반 상승 근거 3~5개\n\n"
        f"## 6. 하락 요인\n"
        f"구체적 수치 기반 하락 근거 3~5개\n\n"
        f"## 7. 외국인·기관 수급 심층 분석\n"
        f"10일 흐름 추세, 보유비중 변화, 역사적 패턴 비교\n\n"
    )

    # ── 기간별 예측 섹션 ──────────────────────────────────────────
    if period == "tomorrow":
        prompt += (
            f"## 8. 내일 주가 예측\n"
            f"**예측 방향**: 상승 / 하락 / 보합 중 택1\n"
            f"  ※ 위 '사전 신호 집계' 종합 판정을 최우선 근거로 사용하세요.\n"
            f"  ※ 판정이 '강력 권고'면 해당 방향, '검토'면 추가 지표 확인 후 결정.\n"
            f"**예상 등락률**: 위 ATR 권장 범위 내에서 XX% ~ XX%\n"
            f"**예측 근거**: 1. 2. 3. (신호 카운터 항목 직접 인용)\n"
            f"**핵심 가정**: 내일 유지되어야 할 조건\n\n"
            f"## 9. 매수 타이밍 분석\n"
            f"단기진입조건/목표가/손절가, 중기 상승·하락 시나리오, 핵심 트리거 이벤트\n\n"
            f"## 10. 종합 신뢰도 및 리스크\n"
            f"**신뢰도**: 낮음/보통/높음\n"
            f"**신뢰도 근거**: \n"
            f"**상방 리스크**: \n"
            f"**하방 리스크**: \n"
            f"**내일 주목 변수**: \n"
        )
    elif period == "week":
        prompt += (
            f"## 8. 1주일 주가 예측 (5거래일)\n"
            f"**예측 방향**: 상승 / 하락 / 보합 중 택1\n"
            f"**예상 등락률**: XX% ~ XX%\n"
            f"**예상 가격 범위**: {cur:,.0f}원 기준 XX원 ~ XX원\n"
            f"**주간 시나리오**: 상승/기준/하락 시나리오별 조건과 목표가\n"
            f"**핵심 변수**: 이번 주 방향 결정 이벤트 3가지\n\n"
            f"## 9. 주간 매매 전략\n"
            f"매수구간/1차목표가/2차목표가/손절기준, 분할매수 전략, 주중 일정\n\n"
            f"## 10. 종합 신뢰도 및 리스크\n"
            f"**신뢰도**: 낮음/보통/높음\n"
            f"**상방 리스크**: \n"
            f"**하방 리스크**: \n"
            f"**주간 모니터링 포인트**: \n"
        )
    elif period == "month":
        prompt += (
            f"## 8. 1개월 주가 예측 (20거래일)\n"
            f"**예측 방향**: 상승 / 하락 / 보합 중 택1\n"
            f"**예상 등락률**: XX% ~ XX%\n"
            f"**예상 가격 범위**: {cur:,.0f}원 기준 XX원 ~ XX원\n"
            f"**월간 시나리오**: 강세(확률XX%)/기준(XX%)/약세(XX%) 시나리오\n"
            f"**방향 전환 조건**: 어떤 신호면 방향이 바뀌는가\n\n"
            f"## 9. 중기 투자 전략\n"
            f"분할매수계획(1~3차), 중기목표가, 손절기준(월봉), 보유전략, 월간 핵심 이벤트\n\n"
            f"## 10. 종합 신뢰도 및 리스크\n"
            f"**신뢰도**: 낮음/보통/높음\n"
            f"**상방 리스크**: \n"
            f"**하방 리스크**: \n"
            f"**월간 모니터링 포인트**: \n"
        )

    if section_11:
        prompt += section_11

    prompt += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[필수 준수 사항]\n"
        f"1. 반드시 위 {section_count}개 섹션(## 1 ~ ## {section_count})을 모두 빠짐없이 작성하세요.\n"
        f"2. 각 섹션 제목(## N. 제목)을 그대로 유지하세요.\n"
        f"3. 모든 수치는 위 데이터에서 직접 인용하세요. 임의로 수치를 만들지 마세요.\n"
        f"4. **예측 방향** 규칙:\n"
        f"   - '상승': RSI 상승+MACD 골든크로스+거래량 증가 등 명확한 상승 신호 3개 이상일 때만\n"
        f"   - '하락': 명확한 하락 신호 3개 이상일 때만\n"
        f"   - 그 외 모든 경우(신호 혼조, 약한 신호, 불확실): 반드시 '보합'\n"
        f"5. **예상 등락률**: 위에 제시된 ATR 권장 범위를 반드시 준수하세요.\n"
        f"   - ATR 2배 이상의 범위는 절대 쓰지 마세요.\n"
        f"6. 분석 근거는 데이터 수치를 직접 언급하며 구체적으로 작성하세요.\n"
        f"7. 반드시 한국어로만 작성하세요. You MUST respond in Korean only. Do NOT write in English.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    return prompt


def _call_groq_stream(prompt: str):
    """키 로테이션 + 재시도 포함 스트리밍. 모든 키 소진 시 최대 2회 대기 재시도."""
    if not GROQ_KEYS:
        yield "❌ GROQ_API_KEY가 설정되지 않았어요. .env 파일을 확인해주세요."
        return

    WAIT_SECONDS = [15, 30]

    for retry in range(len(WAIT_SECONDS) + 1):
        tried = set()
        while len(tried) < len(GROQ_KEYS):
            key = _get_key()
            if key in tried:
                _rotate_key()
                key = _get_key()
            if key is None or key in tried:
                break
            tried.add(key)

            try:
                response = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": True,
                        "temperature": 0.3,
                        "max_tokens": 4000,
                    },
                    stream=True,
                    timeout=120,
                )

                # HTTP 레벨 rate limit (429)
                if response.status_code == 429:
                    print(f"  ⚠️  키 {GROQ_KEYS.index(key)+1} HTTP 429 → 다음 키로 전환")
                    _rotate_key()
                    time.sleep(2)
                    continue

                if not response.ok:
                    err_text = ""
                    try:
                        err_text = response.text
                    except Exception:
                        pass
                    if _is_rate_limit(response.status_code, err_text):
                        print(f"  ⚠️  키 {GROQ_KEYS.index(key)+1} rate limited → 다음 키로 전환")
                        _rotate_key()
                        time.sleep(2)
                        continue
                    yield f"❌ Groq API 오류: {response.status_code}"
                    return

                # 스트림 레벨 rate limit 감지
                rate_limited = False
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8") if isinstance(line, bytes) else line
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        return

                    try:
                        d = json.loads(chunk)

                        # 스트림 안에 error 객체가 담겨온 경우
                        if "error" in d:
                            err_type = d["error"].get("type", "")
                            err_msg  = d["error"].get("message", "")
                            if "rate_limit" in err_type or "rate_limit" in err_msg.lower() or "429" in err_msg:
                                print(f"  ⚠️  키 {GROQ_KEYS.index(key)+1} 스트림 rate limit → 다음 키로 전환")
                                _rotate_key()
                                time.sleep(2)
                                rate_limited = True
                                break
                            else:
                                yield f"❌ Groq 오류: {err_msg}"
                                return

                        token = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if token:
                            yield token

                    except json.JSONDecodeError:
                        continue

                if rate_limited:
                    continue  # 다음 키로 재시도

                return  # 정상 완료

            except requests.exceptions.ConnectionError:
                yield "❌ Groq API에 연결할 수 없어요."
                return
            except requests.exceptions.Timeout:
                yield "❌ 분석 시간이 초과됐어요."
                return
            except Exception as e:
                err = str(e)
                if "rate_limit" in err.lower() or "429" in err:
                    _rotate_key()
                    time.sleep(2)
                    continue
                yield f"❌ 오류: {err}"
                return

        # 모든 키 소진 — 재시도 남아있으면 대기
        if retry < len(WAIT_SECONDS):
            wait = WAIT_SECONDS[retry]
            print(f"  ⏳ 모든 키 rate limit — {wait}초 대기 후 재시도 ({retry+1}/{len(WAIT_SECONDS)})...")
            yield f"⏳ API 요청 한도 초과. {wait}초 후 자동 재시도합니다...\n"
            time.sleep(wait)
            global _key_index
            _key_index = 0
        else:
            yield "❌ 요청이 너무 많아요. 잠시 후 다시 시도해주세요."


def analyze_stream(data: dict):
    """스트리밍 방식으로 분석"""
    prompt = build_prompt(data)
    yield from _call_groq_stream(prompt)


def analyze(data: dict) -> str:
    """단일 응답 방식 (테스트용)"""
    prompt = build_prompt(data)
    if not GROQ_KEYS:
        return "❌ GROQ_API_KEY가 설정되지 않았어요."

    tried = set()
    while len(tried) < len(GROQ_KEYS):
        key = _get_key()
        if key in tried:
            _rotate_key()
            key = _get_key()
        if key is None or key in tried:
            break
        tried.add(key)

        try:
            response = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                timeout=120,
            )
            if _is_rate_limit(response.status_code, response.text):
                _rotate_key()
                time.sleep(0.5)
                continue
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return f"Groq 오류: {response.status_code}"
        except Exception as e:
            return f"❌ 오류: {str(e)}"

    return f"❌ 모든 API 키({len(GROQ_KEYS)}개)가 rate limit에 걸렸어요."