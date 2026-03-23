import { useState, useEffect } from "react";
import StockInput from "./components/StockInput";
import type { PositionInfo } from "./components/StockInput";
import AnalysisResult from "./components/AnalysisResult";
import PredictionHistory from "./components/PredictionHistory";
import AiChat from "./components/AiChat";

export interface StockData {
  ticker: string;
  company_name: string;
  country: string;
  collected_at: string;
  stock: {
    name: string;
    current_price: number;
    prev_price: number;
    change: number;
    change_pct: number;
    volume: number;
    high_52w: number;
    low_52w: number;
    history: { date: string; close: number; volume: number }[];
  };
  market_indicators: {
    kospi?: { price: number; change_pct: number };
    usd_krw?: { price: number; change_pct: number };
    oil_wti?: { price: number; change_pct: number };
    sp500_futures?: { price: number; change_pct: number };
    nasdaq_futures?: { price: number; change_pct: number };
    gold?: { price: number; change_pct: number };
  };
  investor_trading: {
    available: boolean;
    reason?: string;
    latest?: {
      date: string;
      foreign: number;
      institution: number;
      foreign_holding_pct: string;
    };
    "5day_summary"?: {
      foreign_net: number;
      foreign_net_str: string;
      institution_net: number;
      institution_net_str: string;
    };
    history?: {
      date: string;
      close?: number;
      volume?: number;
      foreign: number;
      institution: number;
      foreign_holding_pct?: string;
    }[];
  };
  technicals: {
    available: boolean;
    reason?: string;
    ma5?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    ma120?: number | null;
    ma_cross?: string | null;
    rsi?: number | null;
    rsi_label?: string;
    rsi_trend?: string | null;
    macd_line?: number | null;
    signal_line?: number | null;
    histogram?: number | null;
    macd_cross?: string | null;
    macd_label?: string;
    bb_upper?: number | null;
    bb_middle?: number | null;
    bb_lower?: number | null;
    bb_pct_b?: number | null;
    bb_width?: number | null;
    bb_label?: string;
    stoch_k?: number | null;
    stoch_d?: number | null;
    vol_ma20?: number | null;
    vol_ratio?: number | null;
    chart_data?: {
      date: string;
      close: number;
      volume: number;
      ma5?: number;
      ma20?: number;
      bb_upper?: number;
      bb_middle?: number;
      bb_lower?: number;
    }[];
  };
  financials: {
    available: boolean;
    reason?: string;
    // 밸류에이션
    per?: number | null;
    per_label?: string;
    forward_per?: number | null;
    pbr?: number | null;
    pbr_label?: string;
    psr?: number | null;
    ev_ebitda?: number | null;
    industry_per?: number | null;
    eps?: number | null;
    bps?: number | null;
    // 수익성
    roe?: number | null;
    roa?: number | null;
    gross_margin?: number | null;
    op_margin?: number | null;
    net_margin?: number | null;
    // 성장성
    revenue_growth?: number | null;
    earnings_growth?: number | null;
    earnings_qoq?: number | null;
    // 재무 건전성
    debt_to_equity?: number | null;
    current_ratio?: number | null;
    quick_ratio?: number | null;
    // 배당
    dividend_yield?: number | null;
    payout_ratio?: number | null;
    // 규모
    market_cap?: number | null;
    total_revenue?: number | null;
    ebitda?: number | null;
  };
  news: {
    total: number;
    articles: {
      title: string;
      description?: string;
      source: string;
      published_at: string;
      url?: string;
      sentiment?: "긍정" | "부정" | "중립";
      categories?: string[];
    }[];
    sentiment_summary?: {
      positive: number;
      negative: number;
      neutral: number;
      score: number;
    };
    category_counts?: Record<string, number>;
    top_keywords?: string[];
  };
  prediction_stats?: {
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
  };
  position?: {
    quantity: number;
    avg_price: number;
    total_invested: number;
    current_value: number;
    profit_loss: number;
    profit_loss_pct: number;
    target_profit_pct?: number;
    target_price?: number;
    target_sell_price?: number; 
    target_profit_amount?: number;
    gap_to_target_pct?: number;
    gap_to_target_price?: number;
  };
}

export interface PredictionEntry {
  id: string;
  ticker: string;
  company_name: string;
  analysis_date: string;
  current_price: number;
  predicted_direction: "상승" | "하락" | "보합";
  predicted_pct_low: number;
  predicted_pct_high: number;
  predicted_price_low: number;
  predicted_price_high: number;
  actual_price?: number | null;
  actual_direction?: string | null;
  actual_pct?: number | null;
  hit?: boolean | null;
  in_range?: boolean | null;
  verified_at?: string | null;
}

type AppState = "input" | "analyzing" | "done";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

declare global {
  interface Window {
    electronAPI?: {
      platform: string;
      checkBackend?: () => Promise<{ ok: boolean }>;
      getVersion?: () => Promise<string>;
      windowClose?: () => void;
      windowMinimize?: () => void;
      windowMaximize?: () => void;
    };
  }
}

const isMac = window.electronAPI?.platform === "darwin";

// Windows 스타일 창 컨트롤 버튼
function WinButton({
  children, onClick, hoverBg, hoverColor = "var(--text-primary)", title, isClose = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  hoverBg: string;
  hoverColor?: string;
  title: string;
  isClose?: boolean;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        width: isClose ? 46 : 46,
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "transparent",
        border: "none",
        color: "var(--text-muted)",
        cursor: "pointer",
        transition: "background 0.12s, color 0.12s",
        outline: "none",
        WebkitAppRegion: "no-drag",
      } as React.CSSProperties}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = hoverBg;
        e.currentTarget.style.color = hoverColor;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--text-muted)";
      }}
    >
      {children}
    </button>
  );
}

export default function App() {
  const [appState, setAppState] = useState<AppState>("input");
  const [stockData, setStockData] = useState<StockData | null>(null);
  const [analysisText, setAnalysisText] = useState("");
  const [error, setError] = useState("");
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  // 앱 시작 시 백엔드 상태 확인
  useEffect(() => {
    const check = async () => {
      try {
        // Electron IPC로 확인 or 직접 fetch
        if (window.electronAPI?.checkBackend) {
          const result = await window.electronAPI.checkBackend();
          setBackendOk(result.ok);
        } else {
          const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
          setBackendOk(res.ok);
        }
      } catch {
        setBackendOk(false);
      }
    };
    check();
  }, []);

const handleAnalyze = async (ticker: string, companyName: string, country: string, position?: PositionInfo, period?: string) => {
  setAppState("analyzing");
  setStockData(null);
  setAnalysisText("");
  setError("");

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ ticker, company_name: companyName, country, position, period: period || "tomorrow" }),
    });

    if (!response.ok) {
      let detail = "분석 중 오류가 발생했어요.";
      try {
        const err = await response.json();
        detail = err.detail || detail;
      } catch {}
      throw new Error(detail);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let receivedData = false;
    let isDone = false;

    while (!isDone) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          const msg = JSON.parse(jsonStr);
          if (msg.type === "data") {
            setStockData(msg.payload);
            receivedData = true;
          } else if (msg.type === "token") {
            setAnalysisText((prev) => prev + msg.payload);
          } else if (msg.type === "prediction_saved") {
            console.log("예측 저장됨:", msg.payload);
          } else if (msg.type === "error") {
            console.error("서버 에러:", msg.payload);
          } else if (msg.type === "done") {
            isDone = true;
            setAppState("done");
          }
        } catch {
          // 파싱 실패 무시
        }
      }
    }

    if (!receivedData) throw new Error("서버에서 데이터를 받지 못했어요.");
    if (!isDone) setAppState("done");

  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "알 수 없는 오류가 발생했어요.";
    setError(msg);
    setAppState("input");
  }
};

  const handleReset = () => {
    setAppState("input");
    setStockData(null);
    setAnalysisText("");
    setError("");
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "var(--bg-base)" }}>
      {/* 타이틀바 */}
      <header
        className="titlebar-drag flex items-center justify-between shrink-0"
        style={{
          paddingTop: isMac ? "10px" : "0",
          height: isMac ? "52px" : "44px",
          paddingLeft: isMac ? "80px" : "12px",
          paddingRight: "0",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-panel)",
        }}
      >
        {/* 로고 + 상태 */}
        <div className="flex items-center gap-4" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold shrink-0"
              style={{ background: "linear-gradient(135deg,#0ea5e9,#0284c7)", color: "white" }}
            >
              AI
            </div>
            <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
              StockOracle
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: "var(--accent-dim)", color: "var(--accent)", fontSize: 10 }}
            >
              BETA
            </span>
          </div>

          {/* 백엔드 상태 */}
          <div className="flex items-center gap-1.5">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: backendOk === null ? "#fbbf24" : backendOk ? "#34d399" : "#f87171",
                boxShadow: backendOk === true ? "0 0 6px #34d399" : undefined,
              }}
            />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {backendOk === null ? "확인 중..." : backendOk ? "서버 연결됨" : "서버 오프라인"}
            </span>
          </div>
        </div>

        {/* 오른쪽: 새 분석 버튼 + 창 컨트롤 */}
        <div className="flex items-center h-full" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
          {/* 예측 히스토리 버튼 — 항상 표시 */}
          <button
            onClick={() => setShowHistory(true)}
            className="text-xs px-3 py-1.5 rounded-lg transition-all mr-2"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#a78bfa";
              e.currentTarget.style.borderColor = "rgba(167,139,250,0.4)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-muted)";
              e.currentTarget.style.borderColor = "var(--border)";
            }}
            title="예측 정확도 추적"
          >
            📊 예측 기록
          </button>

          {appState !== "input" && (
            <button
              onClick={handleReset}
              className="text-xs px-3 py-1.5 rounded-lg transition-all mr-3"
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = "var(--text-primary)";
                e.currentTarget.style.borderColor = "var(--border-bright)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = "var(--text-secondary)";
                e.currentTarget.style.borderColor = "var(--border)";
              }}
            >
              ← 새 분석
            </button>
          )}
        </div>
      </header>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 overflow-y-auto bg-grid">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* 백엔드 오프라인 경고 */}
          {backendOk === false && (
            <div
              className="mb-5 px-4 py-3 rounded-xl text-sm flex items-start gap-2 slide-up"
              style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.25)", color: "#fca5a5" }}
            >
              <span>⚠️</span>
              <div>
                <p className="font-medium">백엔드 서버에 연결할 수 없어요</p>
                <p className="mt-0.5" style={{ color: "rgba(252,165,165,0.7)", fontSize: 12 }}>
                  터미널에서 <code style={{ fontFamily: "var(--font-mono)" }}>uvicorn main:app --reload</code> 를 실행해주세요.
                </p>
              </div>
            </div>
          )}

          {/* 에러 */}
          {error && (
            <div
              className="mb-5 px-4 py-3 rounded-xl text-sm slide-up"
              style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.25)", color: "#fca5a5" }}
            >
              ⚠️ {error}
            </div>
          )}

          {appState === "input" && (
            <StockInput onAnalyze={handleAnalyze} backendOk={backendOk ?? false} />
          )}

          {(appState === "analyzing" || appState === "done") && (
          <AnalysisResult
            stockData={stockData}
            analysisText={analysisText}
            isLoading={appState === "analyzing"}
          />
        )}

        {/* AI 채팅 — 분석 완료 후 플로팅 버튼 */}
        <AiChat
          stockData={stockData}
          analysisText={analysisText}
          isAnalysisDone={appState === "done"}
        />
        </div>
      </main>

      {/* 예측 히스토리 모달 */}
      {showHistory && (
        <PredictionHistory
          ticker={stockData?.ticker}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  );
}