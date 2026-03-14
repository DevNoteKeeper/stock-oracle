import requests
import json


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"


def build_prompt(data: dict) -> str:
    """분석 프롬프트 생성"""

    stock        = data.get("stock", {})
    indicators   = data.get("market_indicators", {})
    news         = data.get("news", {})
    investor     = data.get("investor_trading", {})
    company_name = data.get("company_name", data.get("ticker"))
    country      = data.get("country", "")
    ticker       = data.get("ticker", "")

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
            flow_signal = "★ 외국인·기관 동반 순매수 → 강한 매수세, 단기 상승 압력 높음"
        elif foreign_net < 0 and institution_net < 0:
            flow_signal = "★ 외국인·기관 동반 순매도 → 강한 매도세, 단기 하락 압력 높음"
        elif foreign_net > 0:
            flow_signal = "★ 외국인 순매수 / 기관 순매도 → 혼조세, 외국인 주도 방향성"
        else:
            flow_signal = "★ 외국인 순매도 / 기관 순매수 → 혼조세, 기관이 저가 매수 가능성"

        daily_rows = ""
        for d in hist_inv:
            f_val = int(d.get("foreign", 0))
            i_val = int(d.get("institution", 0))
            f_sym = "▲" if f_val > 0 else "▼" if f_val < 0 else "─"
            i_sym = "▲" if i_val > 0 else "▼" if i_val < 0 else "─"
            daily_rows += (
                f"  {d['date']}  외국인 {f_sym} {signed(f_val)}주  "
                f"기관 {i_sym} {signed(i_val)}주\n"
            )

        investor_block = (
            f"10일 누적  외국인: {signed(summary.get('foreign_net', 0) if len(hist_inv) >= 10 else foreign_net)}주 / "
            f"기관: {signed(institution_net)}주\n"
            f"5일 누적   외국인: {signed(investor.get('5day_summary', {}).get('foreign_net', 0))}주 / "
            f"기관: {signed(investor.get('5day_summary', {}).get('institution_net', 0))}주\n"
            f"{flow_signal}\n\n"
            f"일별 상세:\n"
            f"{daily_rows.rstrip()}"
        )
    else:
        investor_block = f"수급 데이터 없음 ({investor.get('reason', '')})"

    # ── 뉴스 블록 ─────────────────────────────────────────────────
    news_block = ""
    articles   = news.get("articles", [])[:12]
    sentiment  = news.get("sentiment_summary", {})
    cat_counts = news.get("category_counts", {})
    top_kw     = news.get("top_keywords", [])

    pos_c   = sentiment.get("positive", 0)
    neg_c   = sentiment.get("negative", 0)
    neu_c   = sentiment.get("neutral", 0)
    total_n = pos_c + neg_c + neu_c
    score   = sentiment.get("score", 0)
    sentiment_str = (
        f"긍정 {pos_c}건 / 부정 {neg_c}건 / 중립 {neu_c}건 (총 {total_n}건)"
        f"  → 뉴스 감성 점수 {score:+.2f}"
        f"  ({'전반적 긍정' if score > 0.2 else '전반적 부정' if score < -0.2 else '혼조/중립'})"
    )
    cat_str = "  ".join(f"{k}:{v}건" for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])[:5])
    kw_str  = ", ".join(top_kw[:8]) if top_kw else "없음"

    news_block += f"  뉴스 감성: {sentiment_str}\n"
    news_block += f"  주요 카테고리: {cat_str or '없음'}\n"
    news_block += f"  핵심 키워드: {kw_str}\n\n"

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

        cur_price = float(stock.get("current_price", 0))

        def ma_pos(ma_val):
            if ma_val is None: return ""
            return "위 ↑" if cur_price > ma_val else "아래 ↓"

        hist_val = tech.get("histogram")
        hist_dir = ""
        if hist_val is not None:
            hist_dir = "양수 (매수 압력)" if hist_val > 0 else "음수 (매도 압력)"

        pct_b     = tech.get("bb_pct_b")
        pct_b_str = f"{round(pct_b * 100, 1)}%" if pct_b is not None else "N/A"

        def stoch_label(k):
            if k is None: return ""
            if k >= 80: return "과매수"
            if k <= 20: return "과매도"
            return "중립"

        technicals_block = (
            f"▶ 기술적 지표 (당일 기준)\n\n"
            f"  [이동평균]\n"
            f"  MA5   : {fv_tech(tech.get('ma5'))}원  (현재가 {ma_pos(tech.get('ma5'))})\n"
            f"  MA20  : {fv_tech(tech.get('ma20'))}원  (현재가 {ma_pos(tech.get('ma20'))})\n"
            f"  MA60  : {fv_tech(tech.get('ma60'))}원  (현재가 {ma_pos(tech.get('ma60'))})\n"
            f"  MA120 : {fv_tech(tech.get('ma120'))}원  (현재가 {ma_pos(tech.get('ma120'))})\n"
            f"  크로스 신호 : {tech.get('ma_cross') or '없음'}\n\n"
            f"  [RSI-14]\n"
            f"  RSI     : {fv_tech(tech.get('rsi'))}  → {tech.get('rsi_label', '')}\n"
            f"  RSI 추세: 최근 3일 {tech.get('rsi_trend') or 'N/A'}\n\n"
            f"  [MACD (12, 26, 9)]\n"
            f"  MACD선    : {fv_tech(tech.get('macd_line'), digits=4)}\n"
            f"  시그널선  : {fv_tech(tech.get('signal_line'), digits=4)}\n"
            f"  히스토그램: {fv_tech(tech.get('histogram'), digits=4)}  ({hist_dir})\n"
            f"  크로스    : {tech.get('macd_cross') or '없음'}\n"
            f"  상태      : {tech.get('macd_label', '')}\n\n"
            f"  [볼린저밴드 (20, 2σ)]\n"
            f"  상단 : {fv_tech(tech.get('bb_upper'))}원\n"
            f"  중심 : {fv_tech(tech.get('bb_middle'))}원\n"
            f"  하단 : {fv_tech(tech.get('bb_lower'))}원\n"
            f"  %B   : {pct_b_str}  → {tech.get('bb_label', '')}\n"
            f"  밴드폭(변동성): {fv_tech(tech.get('bb_width'), '%')}\n\n"
            f"  [스토캐스틱 (14, 3)]\n"
            f"  %K : {fv_tech(tech.get('stoch_k'))}  %D : {fv_tech(tech.get('stoch_d'))}\n"
            f"  상태: {stoch_label(tech.get('stoch_k'))}\n\n"
            f"  [거래량]\n"
            f"  20일 평균 거래량  : {int(tech.get('vol_ma20') or 0):,}주\n"
            f"  오늘/평균 비율    : {fv_tech(tech.get('vol_ratio'))}배"
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
            if v > 20:  return " (고성장)"
            if v > 5:   return " (성장)"
            if v > 0:   return " (소폭 성장)"
            if v > -10: return " (소폭 감소)"
            return " (역성장 주의)"

        def per_vs_industry(per, ind_per):
            if per is None or ind_per is None or ind_per == 0: return ""
            ratio = per / ind_per
            if ratio < 0.8: return f" → 업종 평균({ind_per}) 대비 저평가"
            if ratio < 1.2: return f" → 업종 평균({ind_per}) 수준"
            return f" → 업종 평균({ind_per}) 대비 고평가"

        mc = fin.get("market_cap")
        if mc:
            if mc >= 1_0000_0000_0000: mc_str = f"{mc / 1_0000_0000_0000:.1f}조원"
            elif mc >= 1_0000_0000:    mc_str = f"{mc / 1_0000_0000:.0f}억원"
            else:                       mc_str = f"{mc:,}원"
        else:
            mc_str = "N/A"

        per_str  = fv_fin(fin.get("per"))
        per_str += per_vs_industry(fin.get("per"), fin.get("industry_per"))

        financials_block = (
            f"▶ 재무 지표 (최근 결산 기준)\n\n"
            f"  [밸류에이션]\n"
            f"  PER       : {per_str}  ({fin.get('per_label', '')})\n"
            f"  예상 PER  : {fv_fin(fin.get('forward_per'))}\n"
            f"  PBR       : {fv_fin(fin.get('pbr'))}  ({fin.get('pbr_label', '')})\n"
            f"  PSR       : {fv_fin(fin.get('psr'))}\n"
            f"  EV/EBITDA : {fv_fin(fin.get('ev_ebitda'))}\n"
            f"  시가총액  : {mc_str}\n\n"
            f"  [수익성]\n"
            f"  ROE          : {fv_fin(fin.get('roe'), '%')}\n"
            f"  ROA          : {fv_fin(fin.get('roa'), '%')}\n"
            f"  영업이익률   : {fv_fin(fin.get('op_margin'), '%')}\n"
            f"  순이익률     : {fv_fin(fin.get('net_margin'), '%')}\n"
            f"  매출총이익률 : {fv_fin(fin.get('gross_margin'), '%')}\n\n"
            f"  [성장성 (전년 대비)]\n"
            f"  매출 성장률    : {fv_fin(fin.get('revenue_growth'), '%')}{growth_label(fin.get('revenue_growth'))}\n"
            f"  순이익 성장률  : {fv_fin(fin.get('earnings_growth'), '%')}{growth_label(fin.get('earnings_growth'))}\n"
            f"  분기 순이익(QoQ) : {fv_fin(fin.get('earnings_qoq'), '%')}{growth_label(fin.get('earnings_qoq'))}\n\n"
            f"  [재무 건전성]\n"
            f"  부채비율    : {fv_fin(fin.get('debt_to_equity'))}%\n"
            f"  유동비율    : {fv_fin(fin.get('current_ratio'))}\n"
            f"  당좌비율    : {fv_fin(fin.get('quick_ratio'))}\n\n"
            f"  [배당]\n"
            f"  배당수익률  : {fv_fin(fin.get('dividend_yield'), '%')}\n"
            f"  배당성향    : {fv_fin(fin.get('payout_ratio'), '%')}"
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

    if kospi_pct > 0.5:    market_signals.append("코스피 강세 → 국내 전반 매수 심리")
    elif kospi_pct < -0.5: market_signals.append("코스피 약세 → 국내 전반 매도 심리")
    if sp500_pct > 0.3 or nasdaq_pct > 0.3:
        market_signals.append("미국 선물 상승 → 글로벌 위험선호 심리")
    elif sp500_pct < -0.3 or nasdaq_pct < -0.3:
        market_signals.append("미국 선물 하락 → 글로벌 위험회피 심리")
    if usd_pct > 0.3:    market_signals.append(f"달러 강세(원화 약세 {usd_pct:+.2f}%) → 외국인 매도 유인 증가")
    elif usd_pct < -0.3: market_signals.append(f"달러 약세(원화 강세 {usd_pct:+.2f}%) → 외국인 매수 유인")
    if gold_pct > 0.5:   market_signals.append("금 상승 → 안전자산 선호, 위험자산 회피 분위기")

    market_summary = "\n".join(f"  • {s}" for s in market_signals) if market_signals else "  • 특이 신호 없음"

    # ── 보유 포지션 블록 ──────────────────────────────────────────
    pos            = data.get("position")
    position_block = ""
    section_11     = ""

    if pos:
        pl       = pos.get("profit_loss", 0)
        pl_pct   = pos.get("profit_loss_pct", 0)
        pl_sign  = "+" if pl >= 0 else ""
        qty      = pos.get("quantity", 0)
        avg_p    = pos.get("avg_price", 0)
        invested = pos.get("total_invested", 0)
        cur_val  = pos.get("current_value", 0)
        tgt_p    = pos.get("target_sell_price")
        tgt_pct  = pos.get("target_profit_pct")
        tgt_amt  = pos.get("target_profit_amount")
        gap_pct  = pos.get("gap_to_target_pct")
        gap_price = pos.get("gap_to_target_price")

        if pl_pct >= 10:    pl_status = "수익 구간 (익절 검토 필요)"
        elif pl_pct >= 3:   pl_status = "소폭 수익 중"
        elif pl_pct >= -3:  pl_status = "손익분기 근처"
        elif pl_pct >= -10: pl_status = "소폭 손실 중"
        else:               pl_status = "손실 구간 (추가매수 or 손절 검토)"

        target_line = ""
        if tgt_p:
            target_line = (
                f"\n  희망 매도가  : {tgt_p:,.0f}원  "
                f"(목표 수익률 {tgt_pct:+.1f}%  /  "
                f"목표 수익금 +{tgt_amt:,.0f}원)\n"
                f"  현재→목표   : {gap_price:+,.0f}원 차이  ({gap_pct:+.2f}% 필요)"
            )

        position_block = (
            f"▶ 보유 포지션 (투자자 입력값)\n\n"
            f"  보유 수량   : {qty:,.0f}주\n"
            f"  평균 매수가 : {avg_p:,.0f}원\n"
            f"  총 투자금액 : {invested:,.0f}원\n"
            f"  현재 평가액 : {cur_val:,.0f}원\n"
            f"  평가 손익   : {pl_sign}{pl:,.0f}원  ({pl_sign}{pl_pct:.2f}%)\n"
            f"  현재 상태   : {pl_status}"
            f"{target_line}"
        )

        section_11 = (
            f"\n## 11. 보유 포지션 전략\n"
            f"투자자가 {qty:,.0f}주를 평균 {avg_p:,.0f}원에 보유하고 있습니다.\n"
            f"총 투자금액 {invested:,.0f}원, 현재 평가액 {cur_val:,.0f}원 ({pl_sign}{pl_pct:.2f}%).\n"
        )

        if tgt_p:
            section_11 += (
                f"희망 매도 목표가: {tgt_p:,.0f}원 (수익률 {tgt_pct:+.1f}%, 수익금 +{tgt_amt:,.0f}원)\n"
                f"현재가 기준 {gap_price:+,.0f}원 / {gap_pct:+.2f}% 더 올라야 달성.\n\n"
                f"아래 항목을 **반드시 구체적인 가격과 금액**을 포함해 작성하세요.\n\n"
                f"**희망 매도가 {tgt_p:,.0f}원 달성 분석**:\n"
                f"- 현재 기술적·수급 상황에서 {tgt_p:,.0f}원 도달 가능성 평가 (높음/보통/낮음)\n"
                f"- 예상 도달 기간: 단기(1~2주) / 중기(1~3개월) / 장기(3개월+) 중 판단\n"
                f"- 도달을 위해 필요한 조건 2~3가지 (구체적 지표나 이벤트)\n"
                f"- 리스크가 높아 목표가 도달이 어렵다면: 중간 익절 구간 제시 (금액 명시)\n\n"
            )
        else:
            section_11 += f"아래 항목을 **반드시 구체적인 가격과 금액**을 포함해 작성하세요.\n\n"

        section_11 += (
            f"**현재 포지션 진단**:\n"
            f"- 현재 {pl_sign}{pl_pct:.2f}% ({pl_sign}{pl:,.0f}원) 손익이 기술적·재무 관점에서 의미하는 바\n"
            f"- 지금 보유를 유지하는 게 맞는지, 왜 그런지\n\n"
            f"**익절 전략** (반드시 원 단위 금액으로 제시):\n"
            f"- 1차 익절 목표가: XX원  →  수익금 +XX원 (근거: 기술적 저항선)\n"
            f"- 2차 익절 목표가: XX원  →  수익금 +XX원 (근거: )\n"
            f"- 익절 타이밍 조건: 어떤 신호가 나오면 팔아야 하는가\n"
            f"- 분할 매도 비율: 1차에 XX%, 2차에 XX% 권장\n\n"
            f"**추가매수 전략** (반드시 원 단위 금액으로 제시):\n"
            f"- 추가매수 적정 가격: XX원 이하  →  추가매수 후 평균단가 XX원\n"
            f"- 추가매수 조건: 어떤 상황일 때 매수해야 하는가\n\n"
            f"**손절 기준** (반드시 원 단위 금액으로 제시):\n"
            f"- 손절 기준가: XX원 이탈 시  →  손실금 -XX원 (현재가 대비 -XX%)\n"
            f"- 손절이 필요한 시나리오:\n\n"
            f"**최종 권고**: 지금 당장 취해야 할 행동 1가지를 금액과 함께 명확하게 제시\n"
        )

    section_count = "11개" if pos else "10개"

    # ── 프롬프트 조합 ─────────────────────────────────────────────
    prompt = (
        f"당신은 국내 증권사 15년 경력 수석 애널리스트입니다.\n"
        f"아래에 제공된 **실제 시장 데이터**만을 근거로 분석하세요.\n"
        f"막연한 일반론(\"글로벌 불안정성\" 등)은 금지합니다. 반드시 제공된 수치를 인용하세요.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"■ 분석 대상: {company_name}  ({country} / {ticker})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"▶ 현재 주가\n"
        f"  현재가  : {cur:,.0f}원\n"
        f"  전일 대비: {stock.get('change'):+,.0f}원  ({fmt_pct(stock.get('change_pct'))})\n"
        f"  52주 범위: 최저 {low:,.0f}원 ~ 최고 {high:,.0f}원\n"
        f"  52주 내 위치: {w52_pct:.1f}% → {w52_label}\n"
        f"  오늘 거래량: {vol:,}주  ({vol_label})\n\n"
        f"▶ 최근 5거래일 가격 흐름\n"
        f"  {price_trend}\n\n"
        f"▶ 시장 지표 (현재 기준)\n"
        f"  코스피      : {kospi.get('price')}  ({fmt_pct(kospi.get('change_pct'))})  [{direction_label(kospi.get('change_pct'))}]\n"
        f"  달러/원     : {usd_krw.get('price')}원  ({fmt_pct(usd_krw.get('change_pct'))})\n"
        f"  WTI 유가    : ${oil.get('price')}  ({fmt_pct(oil.get('change_pct'))})\n"
        f"  S&P500 선물 : {sp500_futures.get('price')}  ({fmt_pct(sp500_futures.get('change_pct'))})\n"
        f"  나스닥 선물 : {nasdaq_futures.get('price')}  ({fmt_pct(nasdaq_futures.get('change_pct'))})\n"
        f"  금          : ${gold.get('price')}  ({fmt_pct(gold.get('change_pct'))})\n\n"
        f"▶ 시장 방향 자동 해석\n"
        f"{market_summary}\n\n"
        f"{financials_block}\n\n"
        f"{technicals_block}\n\n"
        f"▶ 외국인·기관 수급 (네이버금융 기준)\n"
        f"{investor_block}\n\n"
        f"▶ 관련 뉴스·이슈\n"
        f"{news_block}\n"
    )

    if position_block:
        prompt += f"\n▶ 보유 포지션\n{position_block}\n"

    prompt += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"아래 {section_count} 섹션을 **순서대로, 빠짐없이** 작성하세요.\n\n"
        f"## 1. 종합 시황 분석\n"
        f"- 코스피 {fmt_pct(kospi.get('change_pct'))}, 달러/원 {usd_krw.get('price')}원, 미국 선물 동향이\n"
        f"  {company_name}의 사업 특성(매출 구조, 환율 민감도 등)에 구체적으로 어떤 영향을 주는지 서술\n"
        f"- 유가·금 움직임의 간접 영향도 포함\n"
        f"- 오늘 거래량({vol_label})이 갖는 의미 해석\n\n"
        f"## 2. 뉴스·사회이슈 심층 분석\n"
        f"뉴스 감성 점수 {score:+.2f} (긍정 {pos_c}건 / 부정 {neg_c}건) 를 바탕으로:\n"
        f"- **핵심 이슈 3가지**: 주가에 가장 직접적 영향을 줄 뉴스를 골라 각각 \"호재/악재/중립\" 판정 및 영향 강도(강/중/약) 명시\n"
        f"- **카테고리별 해석**: 실적·규제·지정학 등 어떤 종류의 이슈가 지배적인지, 그 함의\n"
        f"- **시장 반영 여부**: 이미 주가에 선반영된 뉴스인지 vs 아직 미반영인지 판단 근거\n"
        f"- **사회·거시 이슈 연결**: 현재 금리 환경, 지정학 리스크, 산업 트렌드가 {company_name}에 미치는 구조적 영향\n\n"
        f"## 3. 재무 가치 분석\n"
        f"- PER {fin.get('per') if fin.get('available') else 'N/A'} / PBR {fin.get('pbr') if fin.get('available') else 'N/A'}: 현재 주가가 싼지 비싼지, 업종 평균 대비 위치\n"
        f"- ROE·영업이익률 수준과 경쟁사 대비 위치\n"
        f"- 매출/순이익 성장률 추세가 주가 방향에 주는 시사점\n"
        f"- 부채비율·유동비율로 본 재무 안정성 평가\n\n"
        f"## 4. 기술적 지표 분석\n"
        f"- RSI {tech.get('rsi') if tech.get('available') else 'N/A'}: 현재 구간과 3일 추세 방향\n"
        f"- MACD 히스토그램 방향과 크로스 신호의 신뢰도\n"
        f"- 볼린저밴드 %B: 밴드 위치와 변동성(밴드폭) 해석\n"
        f"- MA5/MA20/MA60 정배열/역배열 판단\n"
        f"- **지표 합의도**: RSI·MACD·BB·스토캐스틱이 같은 방향인지 충돌하는지\n\n"
        f"## 5. 상승 요인\n"
        f"수급·시황·뉴스·재무·기술적 지표에서 도출한 구체적 상승 근거를 3~5개 항목으로 작성.\n"
        f"각 항목마다 **어떤 수치·사실이 근거인지** 명시.\n\n"
        f"## 6. 하락 요인\n"
        f"수급·시황·뉴스·재무·기술적 지표에서 도출한 구체적 하락 근거를 3~5개 항목으로 작성.\n"
        f"각 항목마다 **어떤 수치·사실이 근거인지** 명시.\n\n"
        f"## 7. 외국인·기관 수급 심층 분석\n"
        f"- 10일 수급 흐름 추세(가속·둔화·전환)를 일별 데이터로 판단\n"
        f"- 외국인 보유 비중 변화 방향과 그 시사점\n"
        f"- 현재 수급 패턴과 유사한 역사적 패턴에서 주가 경과\n\n"
        f"## 8. 내일 주가 예측\n"
        f"**반드시 아래 형식을 그대로 사용하세요 (자동 파싱용):**\n\n"
        f"**예측 방향**: 상승 / 하락 / 보합 중 택1\n"
        f"**예상 등락률**: XX% ~ XX%  (예: -1.5% ~ -0.3%)\n"
        f"**예측 근거**:\n"
        f"  1. (수치 기반 근거 1)\n"
        f"  2. (수치 기반 근거 2)\n"
        f"  3. (수치 기반 근거 3)\n"
        f"**핵심 가정**: 이 예측이 맞으려면 내일 어떤 조건이 유지되어야 하는가\n\n"
        f"## 9. 상승 타이밍 분석\n"
        f"단기(1~3일), 중기(1~2주), 장기(1개월 이상) 시점별로 구분하여 작성:\n\n"
        f"**단기 매수 타이밍**:\n"
        f"- 진입 조건: (어떤 지표/가격/이벤트가 충족되어야 하는가)\n"
        f"- 진입 목표가: {cur:,.0f}원 기준 XX원 부근\n"
        f"- 단기 목표가: XX원  (근거: )\n"
        f"- 손절 기준: XX원 이탈 시\n\n"
        f"**중기 시나리오**:\n"
        f"- 상승 시나리오: (어떤 조건이 갖춰지면, 어느 시점에 XX원 도달 가능)\n"
        f"- 하락 시나리오: (어떤 리스크가 현실화되면, 어느 수준까지 조정 가능)\n"
        f"- 분할매수 전략: (타이밍 분산 방법)\n\n"
        f"**핵심 트리거 이벤트**: 주가 방향을 결정할 향후 예정 이벤트나 발표\n\n"
        f"## 10. 종합 신뢰도 및 리스크\n"
        f"**신뢰도**: 낮음 / 보통 / 높음 중 택1\n"
        f"**신뢰도 근거**: 지표 합의도와 데이터 품질 기반\n"
        f"**상방 리스크**: 예측보다 더 오를 수 있는 시나리오\n"
        f"**하방 리스크**: 예측보다 더 내릴 수 있는 시나리오\n"
        f"**내일 장 중 주목 변수**: 확인해야 할 핵심 지표 또는 이벤트\n"
    )

    # 섹션 11은 pos가 있을 때만 추가
    if section_11:
        prompt += section_11

    prompt += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"주의사항:\n"
        f"- 모든 수치는 위 데이터에서 직접 인용할 것\n"
        f"- \"일반적으로\", \"보통\", \"흔히\" 같은 막연한 표현 최소화\n"
        f"- 섹션 제목(## 1. 등)은 반드시 유지\n"
        f"- **반드시 한국어로만 작성하세요. 중국어, 영어 등 다른 언어 사용 절대 금지.**\n"
        f"- You MUST respond in Korean only. Do NOT use Chinese or any other language.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    return prompt


def analyze_stream(data: dict):
    """스트리밍 방식으로 분석"""
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