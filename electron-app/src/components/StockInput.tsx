import { useState } from "react";
import { Search } from "lucide-react";

interface Props {
  onAnalyze: (ticker: string, companyName: string, country: string) => void;
}

const COUNTRY_EXAMPLES: Record<string, { ticker: string; name: string }[]> = {
  한국: [
    { ticker: "005930.KS", name: "삼성전자" },
    { ticker: "000660.KS", name: "SK하이닉스" },
    { ticker: "035420.KS", name: "NAVER" },
    { ticker: "051910.KS", name: "LG화학" },
  ],
  미국: [
    { ticker: "AAPL", name: "Apple" },
    { ticker: "NVDA", name: "NVIDIA" },
    { ticker: "TSLA", name: "Tesla" },
    { ticker: "MSFT", name: "Microsoft" },
  ],
  일본: [
    { ticker: "7203.T", name: "Toyota" },
    { ticker: "9984.T", name: "SoftBank" },
  ],
};

export default function StockInput({ onAnalyze }: Props) {
  const [country, setCountry] = useState("한국");
  const [ticker, setTicker] = useState("");
  const [companyName, setCompanyName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || !companyName.trim()) return;
    onAnalyze(ticker.trim(), companyName.trim(), country);
  };

  const handleExample = (t: string, n: string) => {
    setTicker(t);
    setCompanyName(n);
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="text-center mb-10">
        <h2 className="text-3xl font-bold mb-3">내일 주가를 예측해드려요</h2>
        <p className="text-gray-400">환율, 유가, 선물, 외국인/기관 거래량을 종합 분석합니다</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* 국가 선택 */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">국가</label>
          <div className="flex gap-2">
            {["한국", "미국", "일본"].map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCountry(c)}
                className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  country === c
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* 빠른 선택 */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">빠른 선택</label>
          <div className="flex flex-wrap gap-2">
            {COUNTRY_EXAMPLES[country]?.map((ex) => (
              <button
                key={ex.ticker}
                type="button"
                onClick={() => handleExample(ex.ticker, ex.name)}
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
              >
                {ex.name}
              </button>
            ))}
          </div>
        </div>

        {/* 티커 입력 */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">
            티커
            <span className="ml-2 text-gray-600 text-xs">
              {country === "한국" && "(예: 005930.KS)"}
              {country === "미국" && "(예: AAPL)"}
              {country === "일본" && "(예: 7203.T)"}
            </span>
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder={country === "한국" ? "005930.KS" : country === "미국" ? "AAPL" : "7203.T"}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {/* 기업명 입력 */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">기업명</label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="삼성전자"
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {/* 분석 버튼 */}
        <button
          type="submit"
          disabled={!ticker.trim() || !companyName.trim()}
          className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 rounded-xl font-semibold text-lg flex items-center justify-center gap-2 transition-colors"
        >
          <Search size={20} />
          AI 분석 시작
        </button>
      </form>
    </div>
  );
}