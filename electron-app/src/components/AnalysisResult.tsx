import type { StockData } from "../App";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { TrendingUp, TrendingDown, Loader } from "lucide-react";
import ReactMarkdown from "react-markdown";
interface Props {
  stockData: StockData | null;
  analysisText: string;
  isLoading: boolean;
}

function formatNum(n: number) {
  return n?.toLocaleString("ko-KR") ?? "-";
}

function PriceChange({ value, change }: { value: number; change: number }) {
  const color = value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-gray-400";
  const sign = value > 0 ? "+" : "";
  return (
    <p className={`${color} text-sm mt-1 flex items-center gap-1`}>
      {value > 0 ? <TrendingUp size={14} /> : value < 0 ? <TrendingDown size={14} /> : null}
      {sign}{formatNum(change)}원 ({sign}{value.toFixed(2)}%)
    </p>
  );
}

function IndicatorChange({ value }: { value: number }) {
  const color = value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-gray-400";
  const sign = value > 0 ? "+" : "";
  return <p className={`text-xs ${color} mt-0.5`}>{sign}{value.toFixed(2)}%</p>;
}

export default function AnalysisResult({ stockData, analysisText, isLoading }: Props) {
  const stock = stockData?.stock;
  const indicators = stockData?.market_indicators;
  const investor = stockData?.investor_trading;

  return (
    <div className="space-y-6">

      {/* 데이터 수집 중 */}
      {!stockData && isLoading && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader size={32} className="animate-spin text-blue-400" />
          <p className="text-gray-400">데이터 수집 중...</p>
        </div>
      )}

      {stockData && stock && (
        <>
          {/* 주가 헤더 */}
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-gray-400 text-sm mb-1">{stockData.ticker}</p>
                <h2 className="text-2xl font-bold">{stock.name}</h2>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">
                  {formatNum(stock.current_price)}
                  <span className="text-lg text-gray-400 ml-1">
                    {stockData.country === "미국" ? "USD" : "원"}
                  </span>
                </p>
                <PriceChange value={stock.change_pct} change={stock.change} />
              </div>
            </div>

            {/* 52주 정보 */}
            <div className="mt-4 flex gap-6 text-sm text-gray-400">
              <span>52주 최고 <span className="text-white">{formatNum(stock.high_52w)}</span></span>
              <span>52주 최저 <span className="text-white">{formatNum(stock.low_52w)}</span></span>
              <span>거래량 <span className="text-white">{formatNum(stock.volume)}</span></span>
            </div>
          </div>

          {/* 주가 차트 */}
          {stock.history && stock.history.length > 0 && (
            <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
              <h3 className="text-sm font-medium text-gray-400 mb-4">최근 30일 주가</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={stock.history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    interval={4}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickFormatter={(v: number) => v.toLocaleString()}
                    width={70}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#111827",
                      border: "1px solid #374151",
                      borderRadius: 8,
                    }}
                    labelStyle={{ color: "#9ca3af" }}
                    formatter={(v: number) => [v.toLocaleString() + "원", "종가"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="close"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 시장 지표 */}
          {indicators && (
            <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
              <h3 className="text-sm font-medium text-gray-400 mb-4">시장 지표</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {[
                  { label: "코스피", data: indicators.kospi, prefix: "" },
                  { label: "달러/원", data: indicators.usd_krw, prefix: "" },
                  { label: "WTI 유가", data: indicators.oil_wti, prefix: "$" },
                  { label: "S&P500 선물", data: indicators.sp500_futures, prefix: "" },
                  { label: "나스닥 선물", data: indicators.nasdaq_futures, prefix: "" },
                  { label: "금", data: indicators.gold, prefix: "$" },
                ].map((item) => (
                  <div key={item.label} className="bg-gray-800 rounded-xl p-3">
                    <p className="text-xs text-gray-500 mb-1">{item.label}</p>
                    <p className="font-semibold">
                      {item.prefix}{formatNum(item.data?.price ?? 0)}
                    </p>
                    <IndicatorChange value={item.data?.change_pct ?? 0} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 외국인/기관 거래 */}
          {investor?.available && investor["5day_summary"] && (
            <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
              <h3 className="text-sm font-medium text-gray-400 mb-4">
                외국인/기관 거래 동향 (최근 5일)
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1">외국인 순매수</p>
                  <p className={`font-semibold text-sm ${investor["5day_summary"].foreign_net > 0 ? "text-green-400" : "text-red-400"}`}>
                    {investor["5day_summary"].foreign_net_str}
                  </p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1">기관 순매수</p>
                  <p className={`font-semibold text-sm ${investor["5day_summary"].institution_net > 0 ? "text-green-400" : "text-red-400"}`}>
                    {investor["5day_summary"].institution_net_str}
                  </p>
                </div>
              </div>

              {/* 일별 히스토리 */}
              {investor.history && (
                <div className="space-y-2">
                  {investor.history.map((d) => (
                    <div
                      key={d.date}
                      className="flex items-center justify-between text-sm py-2 border-b border-gray-800"
                    >
                      <span className="text-gray-500 w-24">{d.date}</span>
                      <span className={d.foreign > 0 ? "text-green-400" : "text-red-400"}>
                        외국인 {d.foreign > 0 ? "+" : ""}{formatNum(d.foreign)}
                      </span>
                      <span className={d.institution > 0 ? "text-green-400" : "text-red-400"}>
                        기관 {d.institution > 0 ? "+" : ""}{formatNum(d.institution)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* AI 분석 결과 */}
      {(analysisText || (isLoading && stockData)) && (
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-6 h-6 bg-blue-600 rounded-md flex items-center justify-center text-xs font-bold">
              AI
            </div>
            <h3 className="text-sm font-medium text-gray-400">AI 분석 결과</h3>
            {isLoading && (
              <Loader size={14} className="animate-spin text-blue-400 ml-auto" />
            )}
          </div>

          {analysisText ? (
  <div className="text-left text-gray-200 text-sm leading-relaxed prose prose-invert prose-sm max-w-none
    [&_h3]:text-white [&_h3]:font-bold [&_h3]:text-base [&_h3]:mt-5 [&_h3]:mb-2
    [&_h4]:text-blue-300 [&_h4]:font-semibold [&_h4]:mt-4 [&_h4]:mb-1
    [&_strong]:text-white
    [&_li]:mb-1 [&_ul]:pl-4 [&_ol]:pl-4
    [&_p]:mb-2">
    <ReactMarkdown>{analysisText}</ReactMarkdown>
  </div>
) : (
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <Loader size={14} className="animate-spin" />
              AI가 분석 중이에요...
            </div>
          )}
        </div>
      )}
    </div>
  );
}