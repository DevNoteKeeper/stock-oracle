import { useState, useEffect } from "react";
import type { PredictionEntry } from "../App";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Stats {
  available: boolean;
  reason?: string;
  total?: number;
  direction_hits?: number;
  direction_acc?: number;
  range_hits?: number;
  range_acc?: number;
  up_predictions?: number;
  up_hits?: number;
  down_predictions?: number;
  down_hits?: number;
  recent_history?: PredictionEntry[];
  all_history?: PredictionEntry[];
}

interface Props {
  ticker?: string;
  onClose: () => void;
}

export default function PredictionHistory({ ticker, onClose }: Props) {
  const [stats, setStats]       = useState<Stats | null>(null);
  const [loading, setLoading]   = useState(true);
  const [tab, setTab]           = useState<"overview" | "history">("overview");

  useEffect(() => {
    fetchStats();
  }, [ticker]);

  async function fetchStats() {
    try {
      setLoading(true);
      const url = ticker
        ? `${API_BASE}/prediction/stats?ticker=${encodeURIComponent(ticker)}`
        : `${API_BASE}/prediction/stats`;
      const res  = await fetch(url);
      const data = await res.json();
      setStats(data);
    } catch {
      setStats({ available: false, reason: "서버 연결 실패" });
    } finally {
      setLoading(false);
    }
  }

  const dirColor = (dir?: string | null) =>
    dir === "상승" ? "var(--green)" : dir === "하락" ? "var(--red)" : "var(--text-secondary)";

  const dirIcon = (dir?: string | null) =>
    dir === "상승" ? "▲" : dir === "하락" ? "▼" : "━";

  const hitBadge = (hit?: boolean | null, verified?: string | null) => {
    if (!verified) return <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(148,163,184,0.08)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>대기중</span>;
    if (hit == null) return null;
    return hit
      ? <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: "rgba(52,211,153,0.12)", color: "var(--green)", border: "1px solid rgba(52,211,153,0.25)" }}>✓ 적중</span>
      : <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: "rgba(248,113,113,0.12)", color: "var(--red)", border: "1px solid rgba(248,113,113,0.25)" }}>✗ 빗나감</span>;
  };

  // 최근 20건 정확도 미니 그래프용
  const recentHits = stats?.recent_history?.slice(0, 10).reverse() ?? [];

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(3,7,18,0.85)", backdropFilter: "blur(6px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-2xl mx-4 rounded-2xl overflow-hidden flex flex-col"
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
          maxHeight: "85vh",
        }}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center text-base"
              style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
              📊
            </div>
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>예측 정확도 추적</p>
              {ticker && <p className="text-xs num" style={{ color: "var(--text-muted)" }}>{ticker}</p>}
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-lg"
            style={{ color: "var(--text-muted)", background: "var(--bg-panel)", border: "1px solid var(--border)" }}
          >×</button>
        </div>

        {/* 탭 */}
        <div className="flex px-5 pt-4 gap-2">
          {(["overview", "history"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: tab === t ? "var(--accent-dim)" : "var(--bg-panel)",
                color: tab === t ? "var(--accent)" : "var(--text-muted)",
                border: `1px solid ${tab === t ? "rgba(56,189,248,0.3)" : "var(--border)"}`,
              }}
            >
              {t === "overview" ? "📈 통계 개요" : "📋 전체 기록"}
            </button>
          ))}
        </div>

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="text-sm" style={{ color: "var(--text-muted)" }}>불러오는 중...</div>
            </div>
          ) : !stats?.available && tab === "overview" ? (
            <div className="text-center py-12">
              <p className="text-4xl mb-3">🔮</p>
              <p className="text-sm font-medium mb-1" style={{ color: "var(--text-primary)" }}>아직 검증된 예측이 없어요</p>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {stats?.reason || "분석을 실행하면 다음날 자동으로 실제 주가와 비교해 정확도를 측정합니다"}
              </p>
              {/* 미검증 기록이라도 있으면 보여주기 */}
              {(stats?.all_history?.length ?? 0) > 0 && (
                <button onClick={() => setTab("history")} className="mt-4 text-xs px-3 py-1.5 rounded-lg"
                  style={{ background: "var(--accent-dim)", color: "var(--accent)", border: "1px solid rgba(56,189,248,0.3)" }}>
                  대기중인 예측 {stats!.all_history!.length}건 보기 →
                </button>
              )}
            </div>
          ) : tab === "overview" && stats?.available ? (
            <div className="space-y-4">
              {/* 핵심 지표 카드 */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  {
                    label: "방향 적중률",
                    value: `${stats.direction_acc ?? 0}%`,
                    sub: `${stats.direction_hits}/${stats.total}건`,
                    color: (stats.direction_acc ?? 0) >= 60 ? "var(--green)" : (stats.direction_acc ?? 0) >= 45 ? "var(--gold)" : "var(--red)",
                    emoji: (stats.direction_acc ?? 0) >= 60 ? "🎯" : (stats.direction_acc ?? 0) >= 45 ? "🤔" : "😬",
                  },
                  {
                    label: "범위 적중률",
                    value: `${stats.range_acc ?? 0}%`,
                    sub: `${stats.range_hits}/${stats.total}건`,
                    color: (stats.range_acc ?? 0) >= 50 ? "var(--green)" : "var(--text-secondary)",
                    emoji: "📐",
                  },
                  {
                    label: "총 예측 수",
                    value: `${stats.total ?? 0}건`,
                    sub: "누적 분석",
                    color: "var(--accent)",
                    emoji: "🔢",
                  },
                ].map(({ label, value, sub, color, emoji }) => (
                  <div key={label} className="rounded-xl p-3 text-center"
                    style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <p className="text-xl mb-1">{emoji}</p>
                    <p className="text-xl font-bold num" style={{ color }}>{value}</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{label}</p>
                    <p className="text-xs num" style={{ color: "var(--text-muted)" }}>{sub}</p>
                  </div>
                ))}
              </div>

              {/* 상승/하락 예측 정확도 */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "상승 예측", total: stats.up_predictions ?? 0, hits: stats.up_hits ?? 0, color: "var(--green)", bg: "rgba(52,211,153,0.08)" },
                  { label: "하락 예측", total: stats.down_predictions ?? 0, hits: stats.down_hits ?? 0, color: "var(--red)", bg: "rgba(248,113,113,0.08)" },
                ].map(({ label, total, hits, color, bg }) => {
                  const acc = total > 0 ? Math.round((hits / total) * 100) : 0;
                  return (
                    <div key={label} className="rounded-xl p-3" style={{ background: bg, border: `1px solid ${color}22` }}>
                      <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>{label}</p>
                      <p className="text-2xl font-bold num" style={{ color }}>{acc}%</p>
                      <div className="mt-2" style={{ height: 4, background: "var(--border)", borderRadius: 2 }}>
                        <div style={{ width: `${acc}%`, height: "100%", background: color, borderRadius: 2 }} />
                      </div>
                      <p className="text-xs num mt-1" style={{ color: "var(--text-muted)" }}>{hits}/{total}건 적중</p>
                    </div>
                  );
                })}
              </div>

              {/* 최근 예측 히트맵 */}
              {recentHits.length > 0 && (
                <div className="rounded-xl p-3" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>최근 예측 결과</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    {recentHits.map((e, i) => (
                      <div key={i} className="flex flex-col items-center gap-1">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
                          style={{
                            background: !e.verified_at ? "var(--border)"
                              : e.hit ? "rgba(52,211,153,0.2)" : "rgba(248,113,113,0.2)",
                            border: `1px solid ${!e.verified_at ? "var(--border)" : e.hit ? "rgba(52,211,153,0.4)" : "rgba(248,113,113,0.4)"}`,
                            color: dirColor(e.predicted_direction),
                          }}>
                          {dirIcon(e.predicted_direction)}
                        </div>
                        <span className="text-xs num" style={{ color: "var(--text-muted)", fontSize: 9 }}>
                          {e.analysis_date.slice(5)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    <span>▲ 상승예측</span><span>▼ 하락예측</span>
                    <span style={{ color: "var(--green)" }}>■ 적중</span>
                    <span style={{ color: "var(--red)" }}>■ 빗나감</span>
                    <span>■ 대기중</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* 전체 기록 탭 */
            <div className="space-y-2">
              {(stats?.all_history ?? []).length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-sm" style={{ color: "var(--text-muted)" }}>예측 기록이 없어요. 분석을 먼저 실행해보세요.</p>
                </div>
              ) : (
                [...(stats?.all_history ?? [])].reverse().map((e) => (
                  <div key={e.id} className="rounded-xl p-3"
                    style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs num font-medium" style={{ color: "var(--text-muted)" }}>{e.analysis_date}</span>
                        <span className="text-xs font-bold" style={{ color: "var(--accent)" }}>{e.ticker}</span>
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{e.company_name}</span>
                      </div>
                      {hitBadge(e.hit, e.verified_at)}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {/* 예측 */}
                      <div className="rounded-lg p-2" style={{ background: "var(--bg-base)" }}>
                        <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>예측</p>
                        <p className="text-sm font-bold" style={{ color: dirColor(e.predicted_direction) }}>
                          {dirIcon(e.predicted_direction)} {e.predicted_direction}
                        </p>
                        <p className="text-xs num" style={{ color: "var(--text-muted)" }}>
                          {e.predicted_pct_low > 0 ? "+" : ""}{e.predicted_pct_low}% ~ {e.predicted_pct_high > 0 ? "+" : ""}{e.predicted_pct_high}%
                        </p>
                        <p className="text-xs num" style={{ color: "var(--text-muted)" }}>
                          기준가 {e.current_price.toLocaleString()}
                        </p>
                      </div>
                      {/* 실제 */}
                      <div className="rounded-lg p-2" style={{ background: "var(--bg-base)" }}>
                        <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>실제 결과</p>
                        {e.verified_at ? (
                          <>
                            <p className="text-sm font-bold" style={{ color: dirColor(e.actual_direction) }}>
                              {dirIcon(e.actual_direction)} {e.actual_direction}
                            </p>
                            <p className="text-xs num" style={{ color: (e.actual_pct ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                              {(e.actual_pct ?? 0) >= 0 ? "+" : ""}{e.actual_pct}%
                            </p>
                            <p className="text-xs num" style={{ color: "var(--text-muted)" }}>
                              실제가 {e.actual_price?.toLocaleString()}
                            </p>
                            {e.in_range && (
                              <span className="text-xs" style={{ color: "var(--green)" }}>범위 내 ✓</span>
                            )}
                          </>
                        ) : (
                          <div>
                            <p className="text-xs" style={{ color: "var(--text-muted)" }}>검증 대기중</p>
                            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                              예측가 {e.predicted_price_low.toLocaleString()} ~ {e.predicted_price_high.toLocaleString()}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}