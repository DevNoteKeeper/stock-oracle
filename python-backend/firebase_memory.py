"""
firebase_memory.py — StockOracle 학습 메모리
=============================================
Firebase Firestore에 예측 실패 패턴을 저장하고,
다음 분석 시 관련 패턴을 조회해서 프롬프트에 주입합니다.

Firestore 컬렉션 구조:
  failure_patterns/
    {ticker}/
      patterns/
        {pattern_id}: {
          date, ticker,
          pred_direction, actual_direction,
          pred_pct_low, pred_pct_high, actual_pct,
          signals: { rsi, macd_hist, kospi_pct, sp500_pct, usd_pct, chg5 },
          review_text,     # AI 자기분석 전체 텍스트
          rule,            # 도출된 if-then 규칙
          confirmed_count, # 이 규칙이 이후 실전에서 맞은 횟수
          created_at
        }

  prediction_history/
    {ticker}/
      records/
        {date}: {
          date, ticker, base_price,
          pred_direction, pred_pct_low, pred_pct_high,
          actual_direction, actual_pct,
          hit, in_range,
          created_at
        }

사용법:
  from firebase_memory import FirebaseMemory
  mem = FirebaseMemory()                   # 초기화 (credentials.json 자동 탐색)
  mem.save_failure(ticker, result, review) # 실패 패턴 저장
  patterns = mem.get_patterns(ticker)      # 관련 패턴 조회
  block = mem.build_memory_block(ticker, current_signals) # 프롬프트용 텍스트 생성
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Firebase 초기화 ───────────────────────────────────────────────────

def _find_credentials() -> Optional[str]:
    """프로젝트 폴더에서 Firebase credentials JSON 자동 탐색"""
    candidates = [
        "firebase_credentials.json",
        "serviceAccountKey.json",
        "firebase-adminsdk.json",
    ]
    # 현재 폴더와 부모 폴더까지 탐색
    for base in [Path("."), Path(__file__).parent]:
        for name in candidates:
            p = base / name
            if p.exists():
                return str(p)
    # 환경변수
    return os.getenv("FIREBASE_CREDENTIALS_PATH")


class FirebaseMemory:
    """Firestore 기반 예측 실패 패턴 메모리"""

    def __init__(self, credentials_path: str = None, project_id: str = None):
        self.db       = None
        self.enabled  = False
        self._init_firebase(credentials_path, project_id)

    def _init_firebase(self, credentials_path: str = None, project_id: str = None):
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            cred_path = credentials_path or _find_credentials()
            if not cred_path:
                print("⚠️  Firebase: credentials 파일을 찾을 수 없어요.")
                print("   'firebase_credentials.json'을 프로젝트 폴더에 놓거나")
                print("   FIREBASE_CREDENTIALS_PATH 환경변수를 설정하세요.")
                return

            # 이미 초기화된 앱이 있으면 재사용
            try:
                app = firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(cred_path)
                app  = firebase_admin.initialize_app(cred)

            self.db      = firestore.client()
            self.enabled = True
            print(f"✅ Firebase Firestore 연결 완료")

        except ImportError:
            print("⚠️  Firebase: firebase-admin 패키지가 없어요.")
            print("   pip install firebase-admin 으로 설치하세요.")
        except Exception as e:
            print(f"⚠️  Firebase 초기화 실패: {e}")

    # ── 실패 패턴 저장 ────────────────────────────────────────────────

    def save_failure(self, ticker: str, result: dict, review_text: str) -> bool:
        """
        틀린 예측 결과 + 자기분석을 Firestore에 저장.
        review_text에서 if-then 규칙을 자동 추출해서 함께 저장.
        """
        if not self.enabled:
            return False

        try:
            pred  = result["pred"]
            ev    = result["eval"]
            data  = result.get("collected_data", {})
            ind   = data.get("market_indicators", {})
            tech  = data.get("technicals", {})
            stock = data.get("stock", {})

            # 신호 스냅샷
            history  = stock.get("history", [])
            chg5     = None
            if len(history) >= 5:
                c = [d["close"] for d in history[-5:]]
                chg5 = round((c[-1] - c[0]) / c[0] * 100, 2)

            signals = {
                "rsi":        tech.get("rsi"),
                "macd_hist":  tech.get("histogram"),
                "kospi_pct":  ind.get("kospi",         {}).get("change_pct"),
                "sp500_pct":  ind.get("sp500_futures", {}).get("change_pct"),
                "usd_pct":    ind.get("usd_krw",       {}).get("change_pct"),
                "chg5":       chg5,
                "bb_pct_b":   tech.get("bb_pct_b"),
            }

            # if-then 규칙 추출 (review_text에서 "if ... then ..." 또는 "→" 패턴)
            rule = _extract_rule(review_text)

            pattern_id = f"{ticker}_{result['as_of'].replace('-', '')}"

            doc = {
                "pattern_id":      pattern_id,
                "ticker":          ticker,
                "date":            result["as_of"],
                "pred_direction":  pred["direction"],
                "pred_pct_low":    pred["pct_low"],
                "pred_pct_high":   pred["pct_high"],
                "actual_direction": ev["actual_dir"],
                "actual_pct":      ev["actual_pct"],
                "signals":         signals,
                "review_text":     review_text,
                "rule":            rule,
                "confirmed_count": 0,   # 이후 실전에서 이 규칙이 맞은 횟수
                "created_at":      datetime.now().isoformat(),
            }

            self.db \
                .collection("failure_patterns") \
                .document(ticker) \
                .collection("patterns") \
                .document(pattern_id) \
                .set(doc)

            print(f"  🧠 Firebase: 실패 패턴 저장 완료 ({pattern_id})")
            if rule:
                print(f"     규칙: {rule[:80]}...")
            return True

        except Exception as e:
            print(f"  ⚠️  Firebase 저장 실패: {e}")
            return False

    # ── 예측 기록 저장 ────────────────────────────────────────────────

    def save_prediction_record(self, ticker: str, result: dict) -> bool:
        """모든 예측 결과(맞든 틀리든)를 기록"""
        if not self.enabled or not result.get("eval"):
            return False

        try:
            pred = result["pred"]
            ev   = result["eval"]
            doc  = {
                "date":             result["as_of"],
                "ticker":           ticker,
                "base_price":       result["base_price"],
                "pred_direction":   pred["direction"],
                "pred_pct_low":     pred["pct_low"],
                "pred_pct_high":    pred["pct_high"],
                "actual_direction": ev["actual_dir"],
                "actual_pct":       ev["actual_pct"],
                "hit":              ev["hit"],
                "in_range":         ev["in_range"],
                "override":         result.get("override_reason"),
                "created_at":       datetime.now().isoformat(),
            }
            self.db \
                .collection("prediction_history") \
                .document(ticker) \
                .collection("records") \
                .document(result["as_of"]) \
                .set(doc)
            return True
        except Exception as e:
            print(f"  ⚠️  Firebase 기록 저장 실패: {e}")
            return False

    # ── 패턴 조회 ─────────────────────────────────────────────────────

    def get_patterns(self, ticker: str, limit: int = 20) -> list[dict]:
        """
        티커의 실패 패턴을 최신순으로 조회.
        confirmed_count가 높은 패턴을 우선 반환.
        """
        if not self.enabled:
            return []

        try:
            docs = (
                self.db
                .collection("failure_patterns")
                .document(ticker)
                .collection("patterns")
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            patterns = [d.to_dict() for d in docs]
            # confirmed_count 높은 순으로 재정렬 (가장 검증된 규칙 우선)
            patterns.sort(key=lambda x: x.get("confirmed_count", 0), reverse=True)
            return patterns
        except Exception as e:
            print(f"  ⚠️  Firebase 패턴 조회 실패: {e}")
            return []

    def get_similar_patterns(self, ticker: str, current_signals: dict, top_k: int = 5) -> list[dict]:
        """
        현재 신호와 유사한 과거 실패 패턴을 유사도 기반으로 조회.
        유사도 = 신호값들의 방향(양수/음수) 일치 개수
        """
        all_patterns = self.get_patterns(ticker, limit=50)
        if not all_patterns:
            return []

        def similarity(pattern: dict) -> int:
            sig  = pattern.get("signals", {})
            score = 0
            # RSI 구간 일치
            cur_rsi = current_signals.get("rsi")
            pat_rsi = sig.get("rsi")
            if cur_rsi and pat_rsi:
                cur_zone = "high" if cur_rsi >= 60 else "low" if cur_rsi <= 40 else "mid"
                pat_zone = "high" if pat_rsi >= 60 else "low" if pat_rsi <= 40 else "mid"
                if cur_zone == pat_zone:
                    score += 2
            # S&P500 방향 일치
            cur_sp = current_signals.get("sp500_pct", 0) or 0
            pat_sp = sig.get("sp500_pct", 0) or 0
            if (cur_sp > 0) == (pat_sp > 0):
                score += 1
            # 코스피 방향 일치
            cur_ko = current_signals.get("kospi_pct", 0) or 0
            pat_ko = sig.get("kospi_pct", 0) or 0
            if (cur_ko > 0) == (pat_ko > 0):
                score += 1
            # MACD 방향 일치
            cur_m = current_signals.get("macd_hist", 0) or 0
            pat_m = sig.get("macd_hist", 0) or 0
            if (cur_m > 0) == (pat_m > 0):
                score += 1
            # confirmed_count 보너스
            score += pattern.get("confirmed_count", 0)
            return score

        scored = [(p, similarity(p)) for p in all_patterns]
        scored.sort(key=lambda x: -x[1])
        return [p for p, s in scored[:top_k] if s >= 2]

    # ── 프롬프트용 메모리 블록 생성 ──────────────────────────────────

    def build_memory_block(self, ticker: str, current_signals: dict = None) -> str:
        """
        관련 실패 패턴을 프롬프트에 주입할 텍스트로 변환.
        current_signals가 있으면 유사 패턴 우선, 없으면 최신 패턴 사용.
        """
        if not self.enabled:
            return ""

        if current_signals:
            patterns = self.get_similar_patterns(ticker, current_signals, top_k=5)
        else:
            patterns = self.get_patterns(ticker, limit=5)

        if not patterns:
            return ""

        lines = [f"\n📚 과거 실패 패턴 학습 ({ticker} — {len(patterns)}건, 유사도순)"]
        lines.append("  ※ 아래 패턴과 유사한 상황이면 같은 실수를 반복하지 마세요.\n")

        for i, p in enumerate(patterns, 1):
            date     = p.get("date", "")
            pred_dir = p.get("pred_direction", "")
            act_dir  = p.get("actual_direction", "")
            act_pct  = p.get("actual_pct", 0)
            sig      = p.get("signals", {})
            rule     = p.get("rule", "")
            cnt      = p.get("confirmed_count", 0)
            review   = p.get("review_text", "")

            # 신호 요약
            sig_parts = []
            if sig.get("rsi"):        sig_parts.append(f"RSI {sig['rsi']}")
            if sig.get("kospi_pct"):  sig_parts.append(f"코스피 {sig['kospi_pct']:+.1f}%")
            if sig.get("sp500_pct"):  sig_parts.append(f"S&P500 {sig['sp500_pct']:+.1f}%")
            if sig.get("macd_hist"):  sig_parts.append(f"MACD {'양수' if sig['macd_hist'] > 0 else '음수'}")
            sig_summary = " / ".join(sig_parts) if sig_parts else "데이터 없음"

            confirmed_tag = f" ✅검증{cnt}회" if cnt > 0 else ""
            lines.append(f"  [{i}] {date} | {pred_dir} 예측 → 실제 {act_dir} ({act_pct:+.2f}%){confirmed_tag}")
            lines.append(f"      당시 신호: {sig_summary}")

            if rule:
                lines.append(f"      📌 도출 규칙: {rule}")
            elif review:
                # review에서 핵심 문장만 추출 (첫 2문장)
                sentences = [s.strip() for s in re.split(r'[.。\n]', review) if len(s.strip()) > 10]
                if sentences:
                    lines.append(f"      분석: {sentences[0]}")
            lines.append("")

        return "\n".join(lines)

    # ── 규칙 검증 업데이트 ────────────────────────────────────────────

    def confirm_rule(self, ticker: str, pattern_id: str) -> bool:
        """
        어떤 패턴에서 도출된 규칙이 실전에서 맞았을 때 confirmed_count 증가.
        나중에 실전 분석 후 검증 시 호출.
        """
        if not self.enabled:
            return False
        try:
            ref = (
                self.db
                .collection("failure_patterns")
                .document(ticker)
                .collection("patterns")
                .document(pattern_id)
            )
            doc = ref.get()
            if doc.exists:
                current = doc.to_dict().get("confirmed_count", 0)
                ref.update({"confirmed_count": current + 1})
                return True
        except Exception as e:
            print(f"  ⚠️  규칙 검증 업데이트 실패: {e}")
        return False

    # ── 통계 조회 ─────────────────────────────────────────────────────

    def get_stats(self, ticker: str) -> dict:
        """티커별 학습 통계"""
        if not self.enabled:
            return {}
        try:
            patterns = self.get_patterns(ticker, limit=100)
            records_docs = (
                self.db
                .collection("prediction_history")
                .document(ticker)
                .collection("records")
                .stream()
            )
            records = [d.to_dict() for d in records_docs]
            total   = len(records)
            hits    = sum(1 for r in records if r.get("hit"))
            return {
                "ticker":          ticker,
                "total_predictions": total,
                "direction_acc":   round(hits / total * 100, 1) if total > 0 else 0,
                "failure_patterns": len(patterns),
                "top_rules": [p.get("rule", "") for p in patterns[:3] if p.get("rule")],
            }
        except Exception as e:
            return {"error": str(e)}


# ── 규칙 추출 헬퍼 ────────────────────────────────────────────────────

def _extract_rule(review_text: str) -> str:
    """
    AI 자기분석 텍스트에서 if-then 규칙을 추출.
    우선순위: if-then 형식 > 규칙: 라벨 > 3번 섹션 내용
    """
    if not review_text:
        return ""

    # 1순위: if ... then ... 패턴
    m = re.search(r'if\s+.{5,100}?\s+then\s+.{5,100}', review_text, re.IGNORECASE)
    if m:
        return m.group(0).strip()[:200]

    # 2순위: **규칙:** 라벨 뒤 내용
    m = re.search(r'\*{0,2}규칙\*{0,2}\s*[:：]\s*["\']?(.{10,200}?)["\']?\s*(?:\n|$)', review_text)
    if m:
        return m.group(1).strip()[:200]

    # 3순위: "3." 섹션 이후 실질적인 문장 (헤더 제외)
    parts = re.split(r'3[.)]', review_text)
    if len(parts) > 1:
        for line in parts[-1].split("\n"):
            clean = line.strip().lstrip("-•* ").strip()
            if len(clean) > 15 and not re.match(r'^[\*#0-9]', clean) and '향후' not in clean and clean[:3] != '규칙':
                return clean[:200]

    # 4순위: 마지막 의미있는 문장
    sentences = [s.strip() for s in re.split(r'[.。\n]', review_text)
                 if len(s.strip()) > 20 and not re.match(r'^\*{0,2}[0-9]', s.strip())]
    return sentences[-1][:200] if sentences else ""


# ── 싱글턴 인스턴스 ───────────────────────────────────────────────────

_memory_instance: Optional[FirebaseMemory] = None

def get_memory() -> FirebaseMemory:
    """싱글턴 메모리 인스턴스 반환"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = FirebaseMemory()
    return _memory_instance


# ── CLI 테스트 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mem = get_memory()

    if not mem.enabled:
        print("Firebase 연결 실패. credentials 파일을 확인하세요.")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "stats":
        ticker = sys.argv[2] if len(sys.argv) > 2 else "005930.KS"
        stats  = mem.get_stats(ticker)
        print(f"\n📊 {ticker} 학습 통계:")
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == "patterns":
        ticker   = sys.argv[2] if len(sys.argv) > 2 else "005930.KS"
        patterns = mem.get_patterns(ticker)
        print(f"\n🧠 {ticker} 실패 패턴 ({len(patterns)}건):")
        for p in patterns:
            print(f"  {p['date']} | {p['pred_direction']}→{p['actual_direction']} | {p.get('rule','')[:60]}")

    elif cmd == "block":
        ticker = sys.argv[2] if len(sys.argv) > 2 else "005930.KS"
        block  = mem.build_memory_block(ticker)
        print(block or "(패턴 없음)")