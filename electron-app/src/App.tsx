import { useState } from "react";
import StockInput from "./components/StockInput";
import AnalysisResult from "./components/AnalysisResult";

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
    kospi: { price: number; change_pct: number };
    usd_krw: { price: number; change_pct: number };
    oil_wti: { price: number; change_pct: number };
    sp500_futures: { price: number; change_pct: number };
    nasdaq_futures: { price: number; change_pct: number };
    gold: { price: number; change_pct: number };
  };
  investor_trading: {
    available: boolean;
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
      foreign: number;
      institution: number;
    }[];
  };
  news: {
    total: number;
    articles: { title: string; source: string; published_at: string }[];
  };
}

type AppState = "input" | "analyzing" | "done";

function App() {
  const [appState, setAppState] = useState<AppState>("input");
  const [stockData, setStockData] = useState<StockData | null>(null);
  const [analysisText, setAnalysisText] = useState("");
  const [error, setError] = useState("");

  const handleAnalyze = async (ticker: string, companyName: string, country: string) => {
    setAppState("analyzing");
    setStockData(null);
    setAnalysisText("");
    setError("");

    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, company_name: companyName, country }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "분석 중 오류가 발생했어요.");
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          try {
            const msg = JSON.parse(jsonStr);
            if (msg.type === "data") {
              setStockData(msg.payload);
            } else if (msg.type === "token") {
              setAnalysisText((prev) => prev + msg.payload);
            } else if (msg.type === "done") {
              setAppState("done");
            }
          } catch (_e) {
            // JSON 파싱 실패 무시
          }
        }
      }

      setAppState("done");
    } catch (e) {
      setError((e as Error).message || "알 수 없는 오류가 발생했어요.");
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
    <div className="min-h-screen bg-gray-950 text-white">
      {/* 헤더 */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-sm font-bold">
              AI
            </div>
            <h1 className="text-lg font-semibold">주식 예측 분석기</h1>
          </div>
          {appState !== "input" && (
            <button
              onClick={handleReset}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              ← 새 분석
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-xl text-red-300 text-sm">
            ⚠️ {error}
          </div>
        )}

        {appState === "input" && (
          <StockInput onAnalyze={handleAnalyze} />
        )}

        {(appState === "analyzing" || appState === "done") && (
          <AnalysisResult
            stockData={stockData}
            analysisText={analysisText}
            isLoading={appState === "analyzing"}
          />
        )}
      </main>
    </div>
  );
}

export default App;