# 📈 AI 주식 예측 분석기

> 환율 · 유가 · 선물 · 외국인/기관 수급 · 뉴스를 종합 분석해 내일의 주가를 예측하는 로컬 AI 데스크탑 앱

---

## ✨ 주요 기능

### 📊 데이터 수집 (완전 자동)

- **주가**: 현재가, 52주 고/저, 거래량, 30일 히스토리 (yfinance)
- **시장 지표**: 코스피, 달러/원 환율, WTI 유가, S&P500·나스닥 선물, 금
- **외국인/기관 수급**: 네이버 금융 크롤링, 최근 10일 일별 순매수/순매도
- **뉴스**: 네이버 뉴스(회사 관련 + 한국 시황) + NewsAPI 영문(해외 반응 + 글로벌 이슈)
- **기술적 지표**: RSI, MACD, 볼린저밴드, 이동평균(MA5/20/60/120), 스토캐스틱
- **재무 지표**: PER, PBR, ROE, 영업이익률, 부채비율 등 (yfinance + 네이버금융)

### 🤖 AI 분석 (Ollama 로컬 실행 — 완전 무료)

- 10개 섹션 종합 분석: 시황 · 뉴스 · 재무 · 기술적 지표 · 수급 · 예측 · 타이밍 · 신뢰도
- **내일 주가 방향 예측** (상승/하락/보합) + 예상 등락률 범위
- **보유 포지션 입력 시** 11번째 섹션 자동 추가: 익절·추가매수·손절 전략 (금액 기준)
- 글로벌 이슈 쿼리를 AI가 시장 상황 보고 동적 생성
- 예측 결과 자동 저장 → 다음날 실제 주가로 정확도 자동 검증

### 💼 보유 포지션 분석

- 평균 매수가 · 보유 수량 입력 시 실시간 평가 손익 계산
- **희망 매도 금액** 설정 → 달성까지 필요 금액/% 표시
- 목표 달성 시 예상 수익금 · 수익률 · 총 평가액 계산
- AI가 희망 매도가 도달 예상 기간 분석 및 리스크 높을 시 중간 익절 구간 제시

---

## 🛠️ 기술 스택

| 구분         | 기술                                                   |
| ------------ | ------------------------------------------------------ |
| **Frontend** | React 19 · TypeScript · Tailwind CSS · Recharts · Vite |
| **Desktop**  | Electron 41                                            |
| **Backend**  | Python 3.12 · FastAPI · Uvicorn                        |
| **AI**       | Ollama (qwen2.5:14b) — 완전 로컬, 무료                 |
| **데이터**   | yfinance · BeautifulSoup · NewsAPI                     |
| **DB**       | SQLite (JSON 파일 기반 예측 로그)                      |

---

## ⚙️ 설치 방법

### 사전 요구사항

- **RAM**: 최소 16GB (qwen2.5:14b 모델 실행용)
- **디스크**: 약 10GB 여유 공간 (모델 파일)
- **OS**: Windows (Mac/Linux 부분 지원)
- **Node.js**: 18 이상
- **Python**: 3.12 이상

---

### 1. 코드 받기

```bash
git clone https://github.com/DevNoteKeeper/stock-oracle.git
cd stock-predictor
```

---

### 2. Ollama 설치 + AI 모델 다운로드

[https://ollama.com](https://ollama.com) 에서 Ollama 설치 후:

```bash
ollama pull qwen2.5:14b
```

> ⚠️ 모델 크기 약 9GB — 다운로드에 시간이 걸립니다

---

### 3. Python 백엔드 세팅

```bash
cd python-backend

# 가상환경 생성 및 활성화
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate      # Mac/Linux

# 패키지 설치
pip install fastapi uvicorn yfinance beautifulsoup4 lxml requests python-dotenv
```

**.env 파일 생성** (`python-backend/.env`):

```env
NEWS_API_KEY=your_newsapi_key_here
```

> 💡 NewsAPI 키 없어도 동작합니다. 키가 있으면 해외 영문 뉴스까지 수집됩니다.
> 무료 키 발급: [https://newsapi.org](https://newsapi.org)

---

### 4. React + Electron 앱 세팅

```bash
cd ../electron-app
npm install
```

---

## 🚀 실행 방법

**터미널 1** — Python 백엔드 서버 시작:

```bash
cd python-backend
source venv/Scripts/activate   # Windows
python main.py
```

> 서버가 `http://localhost:8000` 에서 실행됩니다

**터미널 2** — Electron 앱 시작:

```bash
cd electron-app
npm run electron:dev
```

---

## 📁 프로젝트 구조

```
stock-predictor/
├── python-backend/
│   ├── main.py              # FastAPI 서버 (API 엔드포인트)
│   ├── data_collector.py    # 데이터 수집 (주가·시황·뉴스·수급)
│   ├── ai_analyzer.py       # Ollama AI 분석 프롬프트 및 스트리밍
│   ├── prediction_log.json  # 예측 기록 및 정확도 추적 (자동 생성)
│   └── .env                 # API 키 설정 (직접 생성 필요)
│
└── electron-app/
    ├── src/
    │   ├── App.tsx                  # 메인 앱 + 상태 관리
    │   ├── components/
    │   │   ├── StockInput.tsx       # 종목 입력 + 보유 포지션 입력
    │   │   └── AnalysisResult.tsx   # 분석 결과 UI
    │   └── electron/
    │       ├── main.cjs             # Electron 메인 프로세스
    │       └── preload.cjs          # Electron preload
    └── package.json
```

---

## 🌐 지원 국가 및 종목

| 국가    | 티커 형식                                   | 예시                   |
| ------- | ------------------------------------------- | ---------------------- |
| 🇰🇷 한국 | `000000.KS` (코스피) / `000000.KQ` (코스닥) | `005930.KS` (삼성전자) |
| 🇺🇸 미국 | 영문 티커                                   | `AAPL`, `NVDA`, `TSLA` |
| 🇯🇵 일본 | `0000.T`                                    | `7203.T` (Toyota)      |

> 한국 주식만 외국인/기관 수급 데이터가 제공됩니다 (네이버 금융 기준)

---

## 📡 API 엔드포인트

백엔드 서버가 실행 중이면 `http://localhost:8000/docs` 에서 Swagger UI로 확인 가능합니다.

| 메서드 | 경로                  | 설명                                 |
| ------ | --------------------- | ------------------------------------ |
| `POST` | `/analyze`            | 데이터 수집 + AI 분석 (SSE 스트리밍) |
| `POST` | `/collect`            | 데이터 수집만                        |
| `GET`  | `/indicators`         | 시장 지표만 조회                     |
| `GET`  | `/prediction/stats`   | 예측 정확도 통계                     |
| `GET`  | `/prediction/history` | 예측 히스토리                        |
| `POST` | `/prediction/verify`  | 미검증 예측 수동 검증                |

---

## 🔑 환경 변수

`python-backend/.env` 파일:

```env
NEWS_API_KEY=          # NewsAPI 키 (선택 — 없으면 네이버 뉴스만 수집)
```

---

## 📝 주의사항

- 이 앱은 **투자 참고용**으로만 사용하세요. AI 예측은 100% 정확하지 않습니다.
- 모든 AI 분석은 로컬에서 실행되며 외부로 데이터가 전송되지 않습니다.
- 네이버 금융 크롤링은 개인 학습 목적으로만 사용하세요.

---
