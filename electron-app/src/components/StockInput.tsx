import { useState } from "react";
import { Search, TrendingUp, Globe, Zap } from "lucide-react";

interface Props {
  onAnalyze: (ticker: string, companyName: string, country: string, position?: PositionInfo, period?: string) => void;
  backendOk: boolean;
}

export interface PositionInfo {
  quantity: number;
  avgPrice: number;
  targetProfitPct?: number;  // 목표 수익률 (선택)
  targetSellPrice?: number;
}

const PRESETS: Record<string, { ticker: string; name: string; desc: string }[]> = {
  한국: [
    { ticker: "005930.KS", name: "삼성전자", desc: "반도체·스마트폰" },
    { ticker: "000660.KS", name: "SK하이닉스", desc: "메모리 반도체" },
    { ticker: "035420.KS", name: "NAVER", desc: "IT·플랫폼" },
    { ticker: "005380.KS", name: "현대차", desc: "자동차·모빌리티" },
    { ticker: "051910.KS", name: "LG화학", desc: "배터리·화학" },
    { ticker: "035720.KQ", name: "카카오", desc: "플랫폼·핀테크" },
  ],
  미국: [
    { ticker: "AAPL",  name: "Apple",     desc: "아이폰·맥" },
    { ticker: "NVDA",  name: "NVIDIA",    desc: "AI·GPU" },
    { ticker: "TSLA",  name: "Tesla",     desc: "전기차·에너지" },
    { ticker: "MSFT",  name: "Microsoft", desc: "클라우드·AI" },
    { ticker: "AMZN",  name: "Amazon",    desc: "이커머스·클라우드" },
    { ticker: "META",  name: "Meta",      desc: "소셜미디어·VR" },
  ],
  일본: [
    { ticker: "7203.T", name: "Toyota",   desc: "자동차" },
    { ticker: "9984.T", name: "SoftBank", desc: "통신·IT투자" },
    { ticker: "6758.T", name: "Sony",     desc: "엔터·반도체" },
    { ticker: "7974.T", name: "Nintendo", desc: "게임" },
  ],
};

const TICKER_PLACEHOLDER: Record<string, string> = {
  한국: "005930.KS",
  미국: "AAPL",
  일본: "7203.T",
};

const TICKER_FORMAT: Record<string, string> = {
  한국: "6자리.KS 또는 .KQ",
  미국: "영문 티커",
  일본: "4자리.T",
};

// 통합 입력 카드 내 한 행
function TickerField({
  label, hint, value, onChange, placeholder, mono = false, icon,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  mono?: boolean;
  icon: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  const filled = value.length > 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "14px 16px",
        transition: "background 0.15s",
        background: focused ? "rgba(56,189,248,0.04)" : "transparent",
        cursor: "text",
      }}
      onClick={(e) => {
        const input = (e.currentTarget as HTMLElement).querySelector("input");
        input?.focus();
      }}
    >
      {/* 아이콘 */}
      <div
        style={{
          color: focused ? "var(--accent)" : filled ? "var(--text-secondary)" : "var(--text-muted)",
          transition: "color 0.15s",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {icon}
      </div>

      {/* 레이블 + 입력 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: focused ? "var(--accent)" : "var(--text-muted)",
            transition: "color 0.15s",
            marginBottom: 3,
          }}
        >
          {label}
          <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0, marginLeft: 6, color: "var(--text-muted)", opacity: 0.7 }}>
            {hint}
          </span>
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: "100%",
            background: "transparent",
            border: "none",
            outline: "none",
            color: filled ? "var(--text-primary)" : "var(--text-muted)",
            fontSize: 15,
            fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
            fontWeight: mono ? 500 : 400,
            letterSpacing: mono ? "0.04em" : 0,
            padding: 0,
          }}
        />
      </div>

      {/* 입력 완료 체크 */}
      {filled && !focused && (
        <div
          style={{
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: "var(--green-dim)",
            border: "1px solid rgba(52,211,153,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
            <path d="M1 3.5L3.5 6L8 1" stroke="#34d399" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}

      {/* 포커스 우측 인디케이터 */}
      {focused && (
        <div
          style={{
            width: 3,
            height: 28,
            borderRadius: 2,
            background: "var(--accent)",
            flexShrink: 0,
            boxShadow: "0 0 8px var(--accent-glow)",
          }}
        />
      )}
    </div>
  );
}

export default function StockInput({ onAnalyze, backendOk }: Props) {
  const [country, setCountry] = useState("한국");
  const [ticker, setTicker] = useState("");
  const [companyName, setCompanyName] = useState("");

  // 보유 포지션
  const [hasPosition, setHasPosition] = useState(false);
  const [quantity, setQuantity] = useState("");
  const [avgPrice, setAvgPrice] = useState("");
  const [targetPct, setTargetPct] = useState("");
  const [targetSellPrice, setTargetSellPrice] = useState("");
  const [period, setPeriod] = useState("tomorrow");

  const handlePreset = (t: string, n: string) => {
    setTicker(t);
    setCompanyName(n);
  };

  const handleCountryChange = (c: string) => {
    setCountry(c);
    setTicker("");
    setCompanyName("");
  };

  const canSubmit = ticker.trim().length > 0 && companyName.trim().length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    const position = hasPosition && quantity && avgPrice ? {
      quantity: parseFloat(quantity),
      avgPrice: parseFloat(avgPrice),
      targetProfitPct: targetPct ? parseFloat(targetPct) : undefined,
      targetSellPrice: targetSellPrice ? parseFloat(targetSellPrice) : undefined,
    } : undefined;
    onAnalyze(ticker.trim().toUpperCase(), companyName.trim(), country, position, period);  };

  return (
    <div className="max-w-2xl mx-auto slide-up">
      {/* 히어로 */}
      <div className="text-center mb-10 pt-4">
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mb-5"
          style={{ background: "var(--accent-dim)", color: "var(--accent)", border: "1px solid rgba(56,189,248,0.2)" }}
        >
          <Zap size={11} />
          AI 기반 종합 시황 분석
        </div>
        <h1 className="text-3xl font-bold mb-3" style={{ color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
          {period === "tomorrow" ? "내일의 주가를 예측해드려요" :
           period === "week"     ? "이번 주 주가를 예측해드려요" :
                                   "이번 달 주가를 예측해드려요"}
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          환율 · 유가 · 선물 · 외국인/기관 수급 · 뉴스를 종합 분석합니다
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* 국가 선택 */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-medium mb-2.5" style={{ color: "var(--text-secondary)" }}>
            <Globe size={12} /> 국가 선택
          </label>
          <div className="flex gap-2">
            {(["한국", "미국", "일본"] as const).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => handleCountryChange(c)}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
                style={{
                  background: country === c ? "linear-gradient(135deg,#0ea5e9,#0284c7)" : "var(--bg-card)",
                  border: `1px solid ${country === c ? "transparent" : "var(--border)"}`,
                  color: country === c ? "white" : "var(--text-secondary)",
                  boxShadow: country === c ? "0 0 16px rgba(14,165,233,0.3)" : "none",
                }}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* 빠른 선택 */}
        <div>
          <label className="text-xs font-medium mb-2.5 block" style={{ color: "var(--text-secondary)" }}>
            빠른 선택
          </label>
          <div className="grid grid-cols-3 gap-2">
            {PRESETS[country]?.map((ex) => (
              <button
                key={ex.ticker}
                type="button"
                onClick={() => handlePreset(ex.ticker, ex.name)}
                className="px-3 py-2.5 rounded-xl text-left transition-all"
                style={{
                  background: ticker === ex.ticker ? "var(--accent-dim)" : "var(--bg-card)",
                  border: `1px solid ${ticker === ex.ticker ? "rgba(56,189,248,0.4)" : "var(--border)"}`,
                }}
              >
                <p className="font-medium text-sm" style={{ color: ticker === ex.ticker ? "var(--accent)" : "var(--text-primary)" }}>
                  {ex.name}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{ex.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* 티커 + 기업명 — 통합 입력 카드 */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 14,
            overflow: "hidden",
          }}
        >
          {/* 티커 행 */}
          <TickerField
            label="티커"
            hint={TICKER_FORMAT[country]}
            value={ticker}
            onChange={(v) => setTicker(v)}
            placeholder={TICKER_PLACEHOLDER[country]}
            mono
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="1" y="3" width="12" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M4 7h2M8 7h2M4 9.5h1.5M8.5 9.5H10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                <path d="M4.5 1.5L7 3.5L9.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
          />

          {/* 구분선 */}
          <div style={{ height: 1, background: "var(--border)", margin: "0 16px" }} />

          {/* 기업명 행 */}
          <TickerField
            label="기업명"
            hint="회사 이름"
            value={companyName}
            onChange={(v) => setCompanyName(v)}
            placeholder={
              country === "한국" ? "삼성전자" :
              country === "미국" ? "Apple" : "Toyota"
            }
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="1.5" y="4" width="11" height="8.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M4.5 4V3a2.5 2.5 0 015 0v1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                <circle cx="7" cy="8" r="1.2" fill="currentColor"/>
                <path d="M7 9.2v1.3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
            }
          />
        </div>

        {/* 분석 포인트 안내 */}
        <div
          className="rounded-xl p-4 grid grid-cols-2 gap-2"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          {[
            "환율 · 유가 · 선물 지수",
            "외국인 / 기관 순매수",
            "코스피 / 나스닥 동향",
            "최신 뉴스 & 사회 이슈",
            "과거 유사 패턴 분석",
            "AI 종합 예측 + 신뢰도",
          ].map((item) => (
            <div key={item} className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
              <TrendingUp size={11} style={{ color: "var(--accent)", flexShrink: 0 }} />
              {item}
            </div>
          ))}
        </div>
{/* 예측 기간 선택 */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-medium mb-2.5"
            style={{ color: "var(--text-secondary)" }}>
            <Zap size={12} /> 예측 기간
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { value: "tomorrow", label: "내일",   desc: "1거래일",   icon: "📅" },
              { value: "week",     label: "1주일",  desc: "5거래일",   icon: "📆" },
              { value: "month",    label: "1개월",  desc: "20거래일",  icon: "🗓️" },
            ].map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPeriod(p.value)}
                className="py-3 rounded-xl text-center transition-all"
                style={{
                  background: period === p.value ? "var(--accent-dim)" : "var(--bg-card)",
                  border: `1px solid ${period === p.value ? "rgba(56,189,248,0.4)" : "var(--border)"}`,
                  boxShadow: period === p.value ? "0 0 12px rgba(56,189,248,0.15)" : "none",
                }}
              >
                <div className="text-base mb-0.5">{p.icon}</div>
                <p className="text-sm font-semibold"
                  style={{ color: period === p.value ? "var(--accent)" : "var(--text-primary)" }}>
                  {p.label}
                </p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{p.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* 보유 포지션 입력 */}
        <div className="rounded-2xl overflow-hidden mb-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {/* 토글 헤더 */}
          <button
            type="button"
            onClick={() => setHasPosition(!hasPosition)}
            className="w-full flex items-center justify-between px-4 py-3 transition-all"
            style={{ background: hasPosition ? "rgba(56,189,248,0.06)" : "transparent" }}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-5 h-5 rounded flex items-center justify-center text-xs"
                style={{ background: hasPosition ? "var(--accent-dim)" : "var(--bg-panel)", border: `1px solid ${hasPosition ? "rgba(56,189,248,0.4)" : "var(--border)"}` }}>
                💼
              </div>
              <span className="text-sm font-medium" style={{ color: hasPosition ? "var(--accent)" : "var(--text-secondary)" }}>
                이 주식 보유 중이에요
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                (익절·추가매수 타이밍 조언)
              </span>
            </div>
            <div className="w-8 h-4 rounded-full transition-all relative flex-shrink-0"
              style={{ background: hasPosition ? "var(--accent)" : "var(--border)" }}>
              <div className="w-3 h-3 rounded-full bg-white absolute top-0.5 transition-all"
                style={{ left: hasPosition ? "17px" : "2px" }} />
            </div>
          </button>

          {/* 입력 필드 */}
          {hasPosition && (
            <div className="px-4 pb-4 pt-1">
              <div className="grid grid-cols-2 gap-2 mb-2">
                {/* 보유 수량 */}
                <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>보유 수량</p>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      placeholder="100"
                      min="1"
                      className="w-full bg-transparent text-sm font-semibold outline-none num"
                      style={{ color: "var(--text-primary)" }}
                    />
                    <span className="text-xs flex-shrink-0" style={{ color: "var(--text-muted)" }}>주</span>
                  </div>
                </div>

                {/* 평균 매수가 */}
                <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>평균 매수가</p>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={avgPrice}
                      onChange={(e) => setAvgPrice(e.target.value)}
                      placeholder="70000"
                      min="1"
                      className="w-full bg-transparent text-sm font-semibold outline-none num"
                      style={{ color: "var(--text-primary)" }}
                    />
                    <span className="text-xs flex-shrink-0" style={{ color: "var(--text-muted)" }}>원</span>
                  </div>
                </div>
              </div>

              {/* 총 투자금액 자동 계산 */}
              {quantity && avgPrice && (
                <div className="flex items-center justify-between px-3 py-2 rounded-lg mb-2"
                  style={{ background: "rgba(56,189,248,0.06)", border: "1px solid rgba(56,189,248,0.12)" }}>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>총 투자금액</span>
                  <span className="text-xs font-semibold num" style={{ color: "var(--accent)" }}>
                    {(parseFloat(quantity) * parseFloat(avgPrice)).toLocaleString()}원
                  </span>
                </div>
              )}

              {/* 목표 수익률 + 희망 매도 금액 */}
              <div className="grid grid-cols-2 gap-2">
                {/* 목표 수익률 */}
                <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
                    목표 수익률 <span style={{ fontWeight: 400 }}>(선택)</span>
                  </p>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={targetPct}
                      onChange={(e) => {
                        setTargetPct(e.target.value);
                        // 수익률 입력 시 희망 매도 금액 자동 계산
                        if (e.target.value && avgPrice) {
                          const price = parseFloat(avgPrice) * (1 + parseFloat(e.target.value) / 100);
                          setTargetSellPrice(Math.round(price).toString());
                        } else {
                          setTargetSellPrice("");
                        }
                      }}
                      placeholder="20"
                      className="w-full bg-transparent text-sm font-semibold outline-none num"
                      style={{ color: "var(--text-primary)" }}
                    />
                    <span className="text-xs flex-shrink-0" style={{ color: "var(--text-muted)" }}>%</span>
                  </div>
                </div>

                {/* 희망 매도 금액 */}
                <div className="rounded-xl px-3 py-2.5" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
                    희망 매도 금액 <span style={{ fontWeight: 400 }}>(선택)</span>
                  </p>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={targetSellPrice}
                      onChange={(e) => {
                        setTargetSellPrice(e.target.value);
                        // 금액 입력 시 목표 수익률 자동 계산
                        if (e.target.value && avgPrice) {
                          const pct = (parseFloat(e.target.value) / parseFloat(avgPrice) - 1) * 100;
                          setTargetPct(pct.toFixed(1));
                        } else {
                          setTargetPct("");
                        }
                      }}
                      placeholder="90000"
                      className="w-full bg-transparent text-sm font-semibold outline-none num"
                      style={{ color: "var(--text-primary)" }}
                    />
                    <span className="text-xs flex-shrink-0" style={{ color: "var(--text-muted)" }}>원</span>
                  </div>
                </div>
              </div>

              {/* 목표 수익 금액 자동 계산 */}
              {targetSellPrice && quantity && avgPrice && (
                <div className="flex items-center justify-between px-3 py-2 rounded-lg mt-2"
                  style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)" }}>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>목표 수익 금액</span>
                  <span className="text-xs font-semibold num" style={{ color: "var(--gold)" }}>
                    +{((parseFloat(targetSellPrice) - parseFloat(avgPrice)) * parseFloat(quantity)).toLocaleString()}원
                    <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> ({targetPct}%)</span>
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 분석 시작 버튼 */}
        <button
          type="submit"
          disabled={!canSubmit || !backendOk}
          className="w-full flex items-center justify-center gap-2.5 font-semibold text-sm rounded-xl transition-all"
          style={{
            padding: "15px",
            background: canSubmit && backendOk
              ? "linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)"
              : "var(--bg-card)",
            color: canSubmit && backendOk ? "white" : "var(--text-muted)",
            border: `1px solid ${canSubmit && backendOk ? "transparent" : "var(--border)"}`,
            cursor: canSubmit && backendOk ? "pointer" : "not-allowed",
            boxShadow: canSubmit && backendOk ? "0 4px 24px rgba(14,165,233,0.25)" : "none",
            letterSpacing: "0.02em",
          }}
          onMouseEnter={(e) => {
            if (!canSubmit || !backendOk) return;
            e.currentTarget.style.boxShadow = "0 6px 32px rgba(14,165,233,0.45)";
            e.currentTarget.style.transform = "translateY(-1px)";
            e.currentTarget.style.background = "linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = canSubmit && backendOk
              ? "0 4px 24px rgba(14,165,233,0.25)"
              : "none";
            e.currentTarget.style.transform = "none";
            e.currentTarget.style.background = canSubmit && backendOk
              ? "linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)"
              : "var(--bg-card)";
          }}
          onMouseDown={(e) => {
            if (!canSubmit || !backendOk) return;
            e.currentTarget.style.transform = "translateY(0px) scale(0.99)";
            e.currentTarget.style.boxShadow = "0 2px 12px rgba(14,165,233,0.3)";
          }}
          onMouseUp={(e) => {
            if (!canSubmit || !backendOk) return;
            e.currentTarget.style.transform = "translateY(-1px)";
          }}
        >
          <Search size={16} />
          {!backendOk ? "서버 연결 필요" : "AI 분석 시작"}
          {canSubmit && backendOk && (
            <span style={{ opacity: 0.7, fontSize: 11, marginLeft: 2 }}>→</span>
          )}
        </button>
      </form>
    </div>
  );
}