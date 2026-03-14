import { useRef, useEffect } from "react";
import type { StockData } from "../App";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown, Minus, Loader, Activity, Globe, Users, Newspaper, BarChart2, Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Props {
  stockData: StockData | null;
  analysisText: string;
  isLoading: boolean;
}

function fmt(n: number | undefined | null, digits = 0) {
  if (n == null) return "-";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function ChangeTag({ pct, abs, currency = "" }: { pct: number; abs?: number; currency?: string }) {
  const up = pct > 0;
  const dn = pct < 0;
  return (
    <span
      className="inline-flex items-center gap-1 text-sm num"
      style={{ color: up ? "var(--green)" : dn ? "var(--red)" : "var(--text-secondary)" }}
    >
      {up ? <TrendingUp size={13} /> : dn ? <TrendingDown size={13} /> : <Minus size={13} />}
      {abs != null && `${up ? "+" : ""}${fmt(abs)}${currency} `}
      ({up ? "+" : ""}{pct.toFixed(2)}%)
    </span>
  );
}

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span style={{ color: "var(--accent)" }}>{icon}</span>
      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
    </div>
  );
}

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl p-5 ${className}`}
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      {children}
    </div>
  );
}

function SkeletonPanel() {
  return (
    <div className="rounded-2xl p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="skeleton h-4 w-32 mb-4" />
      <div className="skeleton h-8 w-48 mb-2" />
      <div className="skeleton h-4 w-24" />
    </div>
  );
}

export default function AnalysisResult({ stockData, analysisText, isLoading }: Props) {
  const analysisRef = useRef<HTMLDivElement>(null);
  const stock = stockData?.stock;
  const indicators = stockData?.market_indicators;
  const investor = stockData?.investor_trading;
  const news = stockData?.news;

  // 분석 텍스트 업데이트 시 스크롤
  useEffect(() => {
    if (analysisRef.current && isLoading) {
      analysisRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [analysisText, isLoading]);

  // 52주 위치 계산
  const pricePosition = stock && stock.high_52w > stock.low_52w
    ? ((stock.current_price - stock.low_52w) / (stock.high_52w - stock.low_52w)) * 100
    : 50;

  return (
    <div className="space-y-4 slide-up">
      {/* 데이터 수집 중 스켈레톤 */}
      {!stockData && isLoading && (
        <div className="space-y-4">
          <SkeletonPanel />
          <SkeletonPanel />
          <SkeletonPanel />
        </div>
      )}

      {stockData && stock && (
        <>
          {/* ── 주가 헤더 ── */}
          <Panel>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs mb-1 num" style={{ color: "var(--text-muted)" }}>
                  {stockData.ticker} · {stockData.country}
                </p>
                <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {stock.name}
                </h2>
                <div className="mt-1">
                  <ChangeTag pct={stock.change_pct} abs={stock.change} currency={stockData.country === "미국" ? "USD" : "원"} />
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="text-3xl font-bold num" style={{ color: "var(--text-primary)" }}>
                  {fmt(stock.current_price)}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  {stockData.country === "미국" ? "USD" : "KRW"}
                </p>
              </div>
            </div>

            {/* 52주 range bar */}
            <div className="mt-4">
              <div className="flex justify-between text-xs mb-1.5" style={{ color: "var(--text-muted)" }}>
                <span>52주 최저 {fmt(stock.low_52w)}</span>
                <span>거래량 {fmt(stock.volume)}</span>
                <span>52주 최고 {fmt(stock.high_52w)}</span>
              </div>
              <div className="relative h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                <div
                  className="absolute h-full rounded-full"
                  style={{
                    left: 0,
                    width: `${pricePosition}%`,
                    background: "linear-gradient(90deg, #0ea5e9, #38bdf8)",
                  }}
                />
                <div
                  className="absolute w-3 h-3 rounded-full border-2 -translate-x-1/2 -translate-y-1/4"
                  style={{
                    left: `${pricePosition}%`,
                    background: "var(--accent)",
                    borderColor: "var(--bg-base)",
                  }}
                />
              </div>
            </div>
          </Panel>

          {/* ── 주가 차트 (볼린저밴드 + MA 포함) ── */}
          {(() => {
            const chartData = stockData.technicals?.chart_data;
            const hasData   = chartData && chartData.length > 1;
            const rawData   = hasData ? chartData : stock.history;
            if (!rawData || rawData.length < 2) return null;

            return (
              <Panel>
                <div className="flex items-center justify-between mb-3">
                  <SectionHeader icon={<Activity size={14} />} title="주가 차트" />
                  {hasData && (
                    <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 16, height: 2, background: "#38bdf8", display: "inline-block", borderRadius: 1 }} /> 종가
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 16, height: 2, background: "#f59e0b", display: "inline-block", borderRadius: 1 }} /> MA5
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 16, height: 2, background: "#a78bfa", display: "inline-block", borderRadius: 1 }} /> MA20
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 20, height: 8, background: "rgba(56,189,248,0.1)", border: "1px dashed rgba(56,189,248,0.3)", display: "inline-block", borderRadius: 2 }} /> BB
                      </span>
                    </div>
                  )}
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={rawData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(26,42,74,0.8)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#475569", fontSize: 10, fontFamily: "var(--font-mono)" }}
                      tickFormatter={(v: string) => v.slice(5)}
                      interval={Math.floor(rawData.length / 6)}
                      axisLine={false} tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#475569", fontSize: 10, fontFamily: "var(--font-mono)" }}
                      tickFormatter={(v: number) => v.toLocaleString()}
                      width={65} axisLine={false} tickLine={false}
                      domain={["auto", "auto"]}
                    />
                    <ReferenceLine y={stock.prev_price} stroke="rgba(248,113,113,0.35)" strokeDasharray="4 4" />
                    <Tooltip
                      contentStyle={{ background: "#0c1428", border: "1px solid #1a2a4a", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#94a3b8", fontFamily: "var(--font-mono)" }}
                      formatter={(value, name) => {
                        const labels: Record<string, string> = {
                          close: "종가", ma5: "MA5", ma20: "MA20",
                          bb_upper: "BB상단", bb_middle: "BB중심", bb_lower: "BB하단",
                        };
                        const display = typeof value === "number" ? value.toLocaleString() : String(value ?? "");
                        return [display, labels[String(name)] ?? String(name)] as [string, string];
                      }}
                    />
                    {/* 볼린저밴드 영역 */}
                    {hasData && (
                      <>
                        <Line type="monotone" dataKey="bb_upper"  stroke="rgba(56,189,248,0.3)"  strokeWidth={1} dot={false} strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="bb_lower"  stroke="rgba(56,189,248,0.3)"  strokeWidth={1} dot={false} strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="bb_middle" stroke="rgba(56,189,248,0.15)" strokeWidth={1} dot={false} />
                      </>
                    )}
                    {/* 이동평균 */}
                    {hasData && (
                      <>
                        <Line type="monotone" dataKey="ma5"  stroke="#f59e0b" strokeWidth={1.2} dot={false} />
                        <Line type="monotone" dataKey="ma20" stroke="#a78bfa" strokeWidth={1.2} dot={false} />
                      </>
                    )}
                    {/* 종가 */}
                    <Line type="monotone" dataKey="close" stroke="#38bdf8" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#38bdf8" }} />
                  </LineChart>
                </ResponsiveContainer>
              </Panel>
            );
          })()}

          {/* ── 기술적 지표 ── */}
          {stockData.technicals?.available && (() => {
            const t = stockData.technicals;

            // RSI 게이지 색상
            const rsiColor = t.rsi == null ? "var(--text-muted)"
              : t.rsi >= 70 ? "var(--red)"
              : t.rsi <= 30 ? "var(--green)"
              : t.rsi >= 60 ? "#f59e0b"
              : "var(--text-secondary)";

            // MACD 히스토그램 색상
            const histColor = t.histogram == null ? "var(--text-muted)"
              : t.histogram > 0 ? "var(--green)" : "var(--red)";

            // MA 배열 판단
            const prices = [t.ma5, t.ma20, t.ma60].filter(v => v != null) as number[];
            const isGolden = prices.length >= 2 && prices[0] > prices[1] && (prices.length < 3 || prices[1] > prices[2]);
            const isDead   = prices.length >= 2 && prices[0] < prices[1] && (prices.length < 3 || prices[1] < prices[2]);
            const maAlignment = isGolden ? { label: "정배열", color: "var(--green)" }
              : isDead ? { label: "역배열", color: "var(--red)" }
              : { label: "혼조", color: "var(--text-secondary)" };

            // 볼린저 %B → 게이지 위치
            const pctB = t.bb_pct_b ?? 0.5;

            return (
              <Panel>
                <SectionHeader icon={<Zap size={14} />} title="기술적 지표" />

                {/* RSI + MACD + 스토캐스틱 — 3열 */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {/* RSI */}
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>RSI (14)</p>
                    <p className="text-2xl font-bold num" style={{ color: rsiColor }}>{t.rsi ?? "N/A"}</p>
                    {/* RSI 바 */}
                    <div className="relative mt-2 mb-1" style={{ height: 4, background: "var(--border)", borderRadius: 2 }}>
                      <div style={{
                        position: "absolute", left: "30%", right: "30%", top: 0, bottom: 0,
                        background: "rgba(56,189,248,0.2)", borderRadius: 2,
                      }} />
                      {t.rsi != null && (
                        <div style={{
                          position: "absolute", left: `${Math.min(Math.max(t.rsi, 0), 100)}%`,
                          top: -2, width: 8, height: 8, borderRadius: "50%",
                          background: rsiColor, transform: "translateX(-50%)",
                          boxShadow: `0 0 6px ${rsiColor}`,
                        }} />
                      )}
                    </div>
                    <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
                      <span>0</span><span style={{ color: "var(--text-muted)", fontSize: 9 }}>과매도 30 │ 과매수 70</span><span>100</span>
                    </div>
                    <p className="text-xs mt-1.5" style={{ color: "var(--text-muted)" }}>{t.rsi_label}</p>
                    {t.rsi_trend && (
                      <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>3일 추세: {t.rsi_trend}</p>
                    )}
                  </div>

                  {/* MACD */}
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>MACD (12,26,9)</p>
                    <div className="space-y-1">
                      {[
                        { label: "MACD선",    value: t.macd_line,   color: t.macd_line != null && t.macd_line > 0 ? "var(--green)" : "var(--red)" },
                        { label: "시그널선",  value: t.signal_line, color: "var(--text-secondary)" },
                        { label: "히스토그램", value: t.histogram,   color: histColor },
                      ].map(({ label, value, color }) => (
                        <div key={label} className="flex items-center justify-between">
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
                          <span className="text-xs font-medium num" style={{ color }}>
                            {value != null ? value.toFixed(2) : "N/A"}
                          </span>
                        </div>
                      ))}
                    </div>
                    {t.macd_cross && (
                      <div className="mt-2 px-2 py-1 rounded text-xs text-center" style={{
                        background: t.macd_cross.includes("골든") ? "var(--green-dim)" : "var(--red-dim)",
                        color: t.macd_cross.includes("골든") ? "var(--green)" : "var(--red)",
                        border: `1px solid ${t.macd_cross.includes("골든") ? "rgba(52,211,153,0.2)" : "rgba(248,113,113,0.2)"}`,
                      }}>
                        {t.macd_cross}
                      </div>
                    )}
                    {!t.macd_cross && t.macd_label && (
                      <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>{t.macd_label}</p>
                    )}
                  </div>

                  {/* 스토캐스틱 */}
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>Stochastic (14,3)</p>
                    {[
                      { label: "%K", value: t.stoch_k },
                      { label: "%D", value: t.stoch_d },
                    ].map(({ label, value }) => {
                      const c = value == null ? "var(--text-muted)" : value >= 80 ? "var(--red)" : value <= 20 ? "var(--green)" : "var(--text-secondary)";
                      return (
                        <div key={label} className="flex items-center justify-between mb-1">
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
                          <span className="text-sm font-semibold num" style={{ color: c }}>
                            {value != null ? value.toFixed(1) : "N/A"}
                          </span>
                        </div>
                      );
                    })}
                    <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                      {t.stoch_k != null
                        ? t.stoch_k >= 80 ? "과매수 구간"
                        : t.stoch_k <= 20 ? "과매도 구간"
                        : "중립 구간"
                        : ""}
                    </p>
                  </div>
                </div>

                {/* 볼린저밴드 시각화 */}
                <div className="rounded-xl p-3 mb-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>볼린저밴드 (20, 2σ)</p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>밴드폭(변동성): <span className="num" style={{ color: "var(--text-secondary)" }}>{t.bb_width ?? "N/A"}%</span></p>
                  </div>
                  {/* 밴드 바 */}
                  <div className="relative" style={{ height: 28 }}>
                    <div style={{ position: "absolute", inset: "8px 0", background: "rgba(56,189,248,0.08)", border: "1px solid rgba(56,189,248,0.2)", borderRadius: 4 }} />
                    {/* 중심선 */}
                    <div style={{ position: "absolute", left: "50%", top: 4, bottom: 4, width: 1, background: "rgba(56,189,248,0.3)" }} />
                    {/* 현재가 위치 */}
                    {t.bb_upper != null && t.bb_lower != null && (
                      <div style={{
                        position: "absolute",
                        left: `${Math.min(Math.max(pctB * 100, 2), 98)}%`,
                        top: "50%", transform: "translate(-50%, -50%)",
                        width: 10, height: 10, borderRadius: "50%",
                        background: pctB >= 0.8 ? "var(--red)" : pctB <= 0.2 ? "var(--green)" : "var(--accent)",
                        boxShadow: `0 0 8px ${pctB >= 0.8 ? "var(--red)" : pctB <= 0.2 ? "var(--green)" : "var(--accent)"}`,
                        zIndex: 2,
                      }} />
                    )}
                  </div>
                  <div className="flex justify-between text-xs mt-1 num" style={{ color: "var(--text-muted)" }}>
                    <span>하단 {fmt(t.bb_lower)}</span>
                    <span>중심 {fmt(t.bb_middle)}</span>
                    <span>상단 {fmt(t.bb_upper)}</span>
                  </div>
                  <p className="text-xs mt-1.5" style={{ color: pctB >= 0.8 ? "var(--red)" : pctB <= 0.2 ? "var(--green)" : "var(--text-muted)" }}>
                    %B {pctB != null ? `${(pctB * 100).toFixed(1)}%` : "N/A"} — {t.bb_label}
                  </p>
                </div>

                {/* MA 배열 + 크로스 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>이동평균 배열</p>
                    <span className="text-sm font-semibold" style={{ color: maAlignment.color }}>{maAlignment.label}</span>
                    <div className="mt-2 space-y-1">
                      {[
                        { label: "MA5",   val: t.ma5 },
                        { label: "MA20",  val: t.ma20 },
                        { label: "MA60",  val: t.ma60 },
                        { label: "MA120", val: t.ma120 },
                      ].map(({ label, val }) => {
                        if (val == null) return null;
                        const cur2 = stock.current_price;
                        const abv  = cur2 > val;
                        return (
                          <div key={label} className="flex items-center justify-between">
                            <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
                            <span className="text-xs num" style={{ color: abv ? "var(--green)" : "var(--red)" }}>
                              {fmt(val)} {abv ? "↑" : "↓"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>크로스 신호</p>
                    {t.ma_cross ? (
                      <span className="text-sm font-semibold" style={{ color: t.ma_cross.includes("골든") ? "var(--green)" : "var(--red)" }}>
                        {t.ma_cross}
                      </span>
                    ) : (
                      <span className="text-sm" style={{ color: "var(--text-muted)" }}>없음</span>
                    )}
                    {t.macd_cross && (
                      <div className="mt-2">
                        <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>MACD 크로스</p>
                        <span className="text-xs font-semibold" style={{ color: t.macd_cross.includes("골든") ? "var(--green)" : "var(--red)" }}>
                          {t.macd_cross}
                        </span>
                      </div>
                    )}
                    <div className="mt-3">
                      <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>거래량</p>
                      <p className="text-xs num" style={{ color: (t.vol_ratio ?? 1) >= 1.3 ? "var(--accent)" : "var(--text-secondary)" }}>
                        평균 대비 {t.vol_ratio ?? "N/A"}배
                      </p>
                    </div>
                  </div>
                </div>
              </Panel>
            );
          })()}

          {/* ── 시장 지표 ── */}
          {indicators && (
            <Panel>
              <SectionHeader icon={<Globe size={14} />} title="시장 지표" />
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "코스피",      data: indicators.kospi,          prefix: "" },
                  { label: "달러/원",     data: indicators.usd_krw,        prefix: "" },
                  { label: "WTI 유가",   data: indicators.oil_wti,        prefix: "$" },
                  { label: "S&P500 선물", data: indicators.sp500_futures,  prefix: "" },
                  { label: "나스닥 선물", data: indicators.nasdaq_futures,  prefix: "" },
                  { label: "금",          data: indicators.gold,           prefix: "$" },
                ].map(({ label, data, prefix }) => {
                  if (!data) return null;
                  const up = (data.change_pct ?? 0) > 0;
                  const dn = (data.change_pct ?? 0) < 0;
                  return (
                    <div
                      key={label}
                      className="rounded-xl px-3 py-2.5"
                      style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}
                    >
                      <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                      <p className="font-semibold text-sm num" style={{ color: "var(--text-primary)" }}>
                        {prefix}{fmt(data.price, label === "달러/원" ? 0 : 2)}
                      </p>
                      <p className="text-xs num" style={{ color: up ? "var(--green)" : dn ? "var(--red)" : "var(--text-muted)" }}>
                        {up ? "+" : ""}{(data.change_pct ?? 0).toFixed(2)}%
                      </p>
                    </div>
                  );
                })}
              </div>
            </Panel>
          )}

          {/* ── 재무 지표 ── */}
          {stockData.financials?.available && (() => {
            const f = stockData.financials;
            const fv = (v: number | null | undefined, suffix = "") =>
              v != null ? `${v}${suffix}` : "N/A";

            const growthColor = (v: number | null | undefined) =>
              v == null ? "var(--text-muted)"
              : v > 5    ? "var(--green)"
              : v < -5   ? "var(--red)"
              : "var(--text-secondary)";

            const mcLabel = (() => {
              const mc = f.market_cap;
              if (!mc) return "N/A";
              if (mc >= 1e12) return `${(mc / 1e12).toFixed(1)}조원`;
              if (mc >= 1e8)  return `${(mc / 1e8).toFixed(0)}억원`;
              return `$${(mc / 1e9).toFixed(1)}B`;
            })();

            return (
              <Panel>
                <SectionHeader icon={<BarChart2 size={14} />} title="재무 지표" />

                {/* 밸류에이션 */}
                <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                  VALUATION
                </p>
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {[
                    { label: "PER", value: fv(f.per), sub: f.per_label },
                    { label: "예상 PER", value: fv(f.forward_per), sub: f.per != null && f.forward_per != null ? (f.forward_per < f.per ? "이익 증가 예상" : "이익 감소 예상") : "" },
                    { label: "PBR", value: fv(f.pbr), sub: f.pbr_label },
                    { label: "PSR", value: fv(f.psr), sub: "" },
                    { label: "EV/EBITDA", value: fv(f.ev_ebitda), sub: "" },
                    { label: "시가총액", value: mcLabel, sub: "" },
                  ].map(({ label, value, sub }) => (
                    <div key={label} className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                      <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                      <p className="font-semibold text-sm num" style={{ color: value === "N/A" ? "var(--text-muted)" : "var(--text-primary)" }}>
                        {value}
                      </p>
                      {sub && <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{sub}</p>}
                    </div>
                  ))}
                </div>

                {/* 수익성 + 성장성 */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {/* 수익성 */}
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)", letterSpacing: "0.05em" }}>PROFITABILITY</p>
                    {[
                      { label: "ROE",      value: f.roe },
                      { label: "ROA",      value: f.roa },
                      { label: "영업이익률", value: f.op_margin },
                      { label: "순이익률",  value: f.net_margin },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex items-center justify-between py-1" style={{ borderBottom: "1px solid var(--border)" }}>
                        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
                        <span className="text-xs font-medium num" style={{ color: value != null ? (value > 0 ? "var(--green)" : "var(--red)") : "var(--text-muted)" }}>
                          {fv(value, "%")}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* 성장성 */}
                  <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)", letterSpacing: "0.05em" }}>GROWTH (YoY)</p>
                    {[
                      { label: "매출 성장률",    value: f.revenue_growth },
                      { label: "순이익 성장률",  value: f.earnings_growth },
                      { label: "분기 순이익 QoQ", value: f.earnings_qoq },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex items-center justify-between py-1" style={{ borderBottom: "1px solid var(--border)" }}>
                        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
                        <span className="text-xs font-medium num" style={{ color: growthColor(value) }}>
                          {value != null ? `${value > 0 ? "+" : ""}${value}%` : "N/A"}
                        </span>
                      </div>
                    ))}
                    {/* 배당 */}
                    <p className="text-xs font-medium mt-3 mb-1.5" style={{ color: "var(--text-muted)", letterSpacing: "0.05em" }}>DIVIDEND</p>
                    <div className="flex items-center justify-between py-1" style={{ borderBottom: "1px solid var(--border)" }}>
                      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>배당수익률</span>
                      <span className="text-xs font-medium num" style={{ color: f.dividend_yield ? "var(--gold)" : "var(--text-muted)" }}>
                        {fv(f.dividend_yield, "%")}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 재무 건전성 바 */}
                <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)", letterSpacing: "0.05em" }}>FINANCIAL HEALTH</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "부채비율", value: f.debt_to_equity, unit: "%", good: (v: number) => v < 100, warn: (v: number) => v < 200 },
                    { label: "유동비율", value: f.current_ratio,  unit: "x",  good: (v: number) => v >= 2, warn: (v: number) => v >= 1 },
                    { label: "당좌비율", value: f.quick_ratio,    unit: "x",  good: (v: number) => v >= 1, warn: (v: number) => v >= 0.5 },
                  ].map(({ label, value, unit, good, warn }) => {
                    const color = value == null ? "var(--text-muted)" : good(value) ? "var(--green)" : warn(value) ? "var(--gold)" : "var(--red)";
                    return (
                      <div key={label} className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                        <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                        <p className="font-semibold text-sm num" style={{ color }}>{fv(value, unit)}</p>
                      </div>
                    );
                  })}
                </div>
              </Panel>
            );
          })()}

          {/* ── 외국인/기관 수급 ── */}
          {investor?.available && investor["5day_summary"] && (
            <Panel>
              <SectionHeader icon={<Users size={14} />} title="외국인 · 기관 수급 (최근 5일)" />
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { label: "외국인 순매수", val: investor["5day_summary"].foreign_net, str: investor["5day_summary"].foreign_net_str },
                  { label: "기관 순매수",   val: investor["5day_summary"].institution_net, str: investor["5day_summary"].institution_net_str },
                ].map(({ label, val, str }) => (
                  <div
                    key={label}
                    className="rounded-xl p-3"
                    style={{
                      background: val > 0 ? "var(--green-dim)" : val < 0 ? "var(--red-dim)" : "var(--bg-panel)",
                      border: `1px solid ${val > 0 ? "rgba(52,211,153,0.2)" : val < 0 ? "rgba(248,113,113,0.2)" : "var(--border)"}`,
                    }}
                  >
                    <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                    <p className="text-sm font-semibold num" style={{ color: val > 0 ? "var(--green)" : val < 0 ? "var(--red)" : "var(--text-secondary)" }}>
                      {str}
                    </p>
                  </div>
                ))}
              </div>

              {/* 일별 히스토리 테이블 */}
              {investor.history && investor.history.length > 0 && (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
                  <div
                    className="grid grid-cols-3 gap-0 px-3 py-2 text-xs font-medium"
                    style={{ background: "var(--bg-panel)", color: "var(--text-muted)" }}
                  >
                    <span>날짜</span>
                    <span className="text-right">외국인</span>
                    <span className="text-right">기관</span>
                  </div>
                  {investor.history.map((d, i) => (
                    <div
                      key={d.date}
                      className="grid grid-cols-3 gap-0 px-3 py-2 text-xs num"
                      style={{
                        background: i % 2 === 0 ? "var(--bg-panel)" : "transparent",
                        borderTop: "1px solid var(--border)",
                      }}
                    >
                      <span style={{ color: "var(--text-muted)" }}>{d.date}</span>
                      <span className="text-right" style={{ color: d.foreign > 0 ? "var(--green)" : d.foreign < 0 ? "var(--red)" : "var(--text-muted)" }}>
                        {d.foreign > 0 ? "+" : ""}{fmt(d.foreign)}
                      </span>
                      <span className="text-right" style={{ color: d.institution > 0 ? "var(--green)" : d.institution < 0 ? "var(--red)" : "var(--text-muted)" }}>
                        {d.institution > 0 ? "+" : ""}{fmt(d.institution)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {/* ── 뉴스 ── */}
          {news && news.articles.length > 0 && (() => {
            const s = news.sentiment_summary;
            const total = s ? (s.positive + s.negative + s.neutral) : news.total;
            const score = s?.score ?? 0;
            const scoreColor = score > 0.2 ? "var(--green)" : score < -0.2 ? "var(--red)" : "var(--text-secondary)";
            const scoreLabel = score > 0.2 ? "긍정 우세" : score < -0.2 ? "부정 우세" : "혼조/중립";

            return (
              <Panel>
                <div className="flex items-center justify-between mb-3">
                  <SectionHeader icon={<Newspaper size={14} />} title={`뉴스·이슈 분석 (${total}건)`} />
                  {s && (
                    <span className="text-xs font-semibold num" style={{ color: scoreColor }}>
                      감성 {score > 0 ? "+" : ""}{score.toFixed(2)} · {scoreLabel}
                    </span>
                  )}
                </div>

                {/* 감성 바 */}
                {s && total > 0 && (
                  <div className="mb-3">
                    <div className="flex rounded-full overflow-hidden" style={{ height: 6 }}>
                      <div style={{ width: `${(s.positive/total)*100}%`, background: "var(--green)" }} />
                      <div style={{ width: `${(s.neutral/total)*100}%`,  background: "var(--border)" }} />
                      <div style={{ width: `${(s.negative/total)*100}%`, background: "var(--red)" }} />
                    </div>
                    <div className="flex justify-between text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                      <span style={{ color: "var(--green)" }}>📈 긍정 {s.positive}</span>
                      <span>중립 {s.neutral}</span>
                      <span style={{ color: "var(--red)" }}>📉 부정 {s.negative}</span>
                    </div>
                  </div>
                )}

                {/* 카테고리 태그 */}
                {news.category_counts && Object.keys(news.category_counts).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {Object.entries(news.category_counts)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([cat, cnt]) => (
                        <span key={cat} className="text-xs px-2 py-0.5 rounded-full"
                          style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                          {cat} {cnt}
                        </span>
                      ))}
                  </div>
                )}

                {/* 키워드 */}
                {news.top_keywords && news.top_keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>핵심어:</span>
                    {news.top_keywords.slice(0, 8).map((kw) => (
                      <span key={kw} className="text-xs num" style={{ color: "var(--accent)" }}>#{kw}</span>
                    ))}
                  </div>
                )}

                {/* 기사 목록 */}
                <div className="space-y-2">
                  {news.articles.slice(0, 8).map((article, i) => {
                    const sIcon = article.sentiment === "긍정" ? "📈" : article.sentiment === "부정" ? "📉" : "📰";
                    const sColor = article.sentiment === "긍정" ? "var(--green)" : article.sentiment === "부정" ? "var(--red)" : "var(--text-muted)";
                    return (
                      <div key={i} className="rounded-xl p-3"
                        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                        <div className="flex items-start gap-2">
                          <span className="text-sm flex-shrink-0 mt-0.5">{sIcon}</span>
                          <div className="flex-1 min-w-0">
                            {article.url ? (
                              <a href={article.url} target="_blank" rel="noreferrer"
                                className="text-sm selectable hover:underline"
                                style={{ color: "var(--text-primary)", lineHeight: 1.5 }}>
                                {article.title}
                              </a>
                            ) : (
                              <p className="text-sm selectable" style={{ color: "var(--text-primary)", lineHeight: 1.5 }}>
                                {article.title}
                              </p>
                            )}
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                {article.source} · {article.published_at?.slice(0, 10)}
                              </span>
                              {article.sentiment && (
                                <span className="text-xs font-medium" style={{ color: sColor }}>{article.sentiment}</span>
                              )}
                              {article.categories?.slice(0, 2).map((c) => (
                                <span key={c} className="text-xs px-1.5 py-0.5 rounded"
                                  style={{ background: "rgba(56,189,248,0.08)", color: "var(--accent)", border: "1px solid rgba(56,189,248,0.15)" }}>
                                  {c}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Panel>
            );
          })()}
        </>
      )}

      {/* ── AI 분석 결과 ── */}
      {(analysisText || (isLoading && stockData)) && (
        <Panel>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold"
                style={{ background: "linear-gradient(135deg,#0ea5e9,#0284c7)", color: "white" }}
              >
                AI
              </div>
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                AI 종합 분석
              </span>
            </div>
            {isLoading && (
              <div className="flex items-center gap-1.5 text-xs pulse-glow" style={{ color: "var(--accent)" }}>
                <Loader size={12} className="animate-spin" />
                분석 중...
              </div>
            )}
          </div>

          <div ref={analysisRef}>
            {analysisText ? (
              <div
                className={`analysis-content selectable ${isLoading ? "cursor-blink" : ""}`}
                style={{ color: "var(--text-primary)" }}
              >
                <ReactMarkdown
                  components={{
                    // ## 섹션 헤더 → 강조 카드 헤더
                    h2: ({ children }) => {
                      const text = String(children);
                      const num  = parseInt(text.match(/^(\d+)/)?.[1] ?? "0");
                      // 섹션별 색상 매핑
                      const isPredict  = num === 8  || text.includes("예측");
                      const isTiming   = num === 9  || text.includes("타이밍");
                      const isSignal   = num === 10 || text.includes("신뢰도");
                      const isNews     = num === 2  || text.includes("뉴스");

                      const accentColor = isPredict ? "var(--accent)"
                        : isTiming   ? "#a78bfa"
                        : isSignal   ? "var(--gold)"
                        : isNews     ? "#34d399"
                        : "var(--text-secondary)";
                      const bgColor = isPredict ? "var(--accent-dim)"
                        : isTiming   ? "rgba(167,139,250,0.12)"
                        : isSignal   ? "rgba(251,191,36,0.12)"
                        : isNews     ? "rgba(52,211,153,0.12)"
                        : "var(--bg-panel)";
                      const borderColor = isPredict ? "rgba(56,189,248,0.3)"
                        : isTiming   ? "rgba(167,139,250,0.25)"
                        : isSignal   ? "rgba(251,191,36,0.2)"
                        : isNews     ? "rgba(52,211,153,0.2)"
                        : "var(--border)";

                      return (
                        <div
                          className="flex items-center gap-2 mt-6 mb-3 pb-2"
                          style={{ borderBottom: `1px solid ${borderColor}` }}
                        >
                          <div
                            className="w-5 h-5 rounded flex items-center justify-center text-xs font-bold shrink-0"
                            style={{ background: bgColor, color: accentColor, border: `1px solid ${borderColor}` }}
                          >
                            {num || "·"}
                          </div>
                          <span className="text-sm font-semibold" style={{ color: accentColor === "var(--text-secondary)" ? "var(--text-primary)" : accentColor }}>
                            {text.replace(/^\d+\.\s*/, "")}
                          </span>
                        </div>
                      );
                    },
                    // **굵은 글씨** — 예측 방향 등 강조
                    strong: ({ children }) => {
                      const text = String(children);
                      const isUp   = text.includes("상승");
                      const isDown = text.includes("하락");
                      const isHold = text.includes("보합");
                      if (isUp || isDown || isHold) {
                        return (
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-bold text-sm"
                            style={{
                              background: isUp ? "var(--green-dim)" : isDown ? "var(--red-dim)" : "rgba(148,163,184,0.1)",
                              color: isUp ? "var(--green)" : isDown ? "var(--red)" : "var(--text-secondary)",
                              border: `1px solid ${isUp ? "rgba(52,211,153,0.25)" : isDown ? "rgba(248,113,113,0.25)" : "var(--border)"}`,
                            }}
                          >
                            {isUp ? "▲" : isDown ? "▼" : "━"} {text}
                          </span>
                        );
                      }
                      return <strong style={{ color: "#f1f5f9", fontWeight: 600 }}>{children}</strong>;
                    },
                    // 리스트
                    ul: ({ children }) => (
                      <ul className="space-y-1 my-2 pl-4" style={{ color: "var(--text-primary)" }}>{children}</ul>
                    ),
                    li: ({ children }) => (
                      <li className="text-sm leading-relaxed" style={{ listStyleType: "none", paddingLeft: 0 }}>
                        <span style={{ color: "var(--accent)", marginRight: 6 }}>•</span>{children}
                      </li>
                    ),
                    ol: ({ children }) => (
                      <ol className="space-y-1.5 my-2 pl-4" style={{ counterReset: "item" }}>{children}</ol>
                    ),
                    p: ({ children }) => (
                      <p className="text-sm leading-relaxed my-1.5" style={{ color: "var(--text-secondary)" }}>{children}</p>
                    ),
                    hr: () => <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />,
                  }}
                >
                  {analysisText}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-4/5" />
                <div className="skeleton h-4 w-3/5" />
              </div>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}