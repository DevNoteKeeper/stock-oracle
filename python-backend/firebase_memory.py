"""
firebase_memory.py — StockOracle 학습 메모리 (사용자별 격리)
=============================================================
각 기기마다 고유한 user_id를 발급해서 데이터를 완전히 격리합니다.
user_id는 ~/.stockoracle/user_id 파일에 저장되어 기기 재시작 후에도 유지됩니다.

Firestore 구조:
  users/{user_id}/
    failure_patterns/{ticker}/patterns/{pattern_id}
    prediction_history/{ticker}/records/{date}
    meta/profile

CLI:
  python firebase_memory.py whoami              # 내 user_id 확인
  python firebase_memory.py patterns 005930.KS  # 실패 패턴 목록
  python firebase_memory.py stats 005930.KS     # 학습 통계
  python firebase_memory.py block 005930.KS     # 프롬프트 블록 미리보기
  python firebase_memory.py reset               # user_id 초기화
"""

import json
import os
import platform
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── 사용자 ID 관리 ────────────────────────────────────────────────────

def _get_user_id_path() -> Path:
    return Path.home() / ".stockoracle" / "user_id"


def get_or_create_user_id() -> str:
    """
    기기 고유 user_id 반환. 없으면 UUID 생성 후 로컬 파일에 저장.
    환경변수 STOCKORACLE_USER_ID로 오버라이드 가능.
    """
    env_id = os.getenv("STOCKORACLE_USER_ID")
    if env_id:
        return env_id.strip()

    id_path = _get_user_id_path()
    if id_path.exists():
        try:
            uid = id_path.read_text(encoding="utf-8").strip()
            if uid:
                return uid
        except Exception:
            pass

    uid = f"anon_{uuid.uuid4().hex[:16]}"
    try:
        id_path.parent.mkdir(parents=True, exist_ok=True)
        id_path.write_text(uid, encoding="utf-8")
    except Exception as e:
        print(f"⚠️  user_id 저장 실패: {e}")
    return uid


# ── Firebase 초기화 ───────────────────────────────────────────────────

def _find_credentials() -> Optional[str]:
    candidates = [
        "firebase_credentials.json",
        "serviceAccountKey.json",
        "firebase-adminsdk.json",
    ]
    for base in [Path("."), Path(__file__).parent]:
        for name in candidates:
            p = base / name
            if p.exists():
                return str(p)
    return os.getenv("FIREBASE_CREDENTIALS_PATH")


class FirebaseMemory:
    """Firestore 기반 예측 실패 패턴 메모리 — 사용자별 완전 격리"""

    def __init__(self, credentials_path: str = None, user_id: str = None):
        self.db      = None
        self.enabled = False
        self.user_id = user_id or get_or_create_user_id()
        self._init_firebase(credentials_path)

    def _user_ref(self):
        """현재 사용자의 Firestore 루트 레퍼런스"""
        return self.db.collection("users").document(self.user_id)

    def _init_firebase(self, credentials_path: str = None):
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            cred_path = credentials_path or _find_credentials()
            if not cred_path:
                print("⚠️  Firebase: credentials 파일을 찾을 수 없어요.")
                print("   'firebase_credentials.json'을 프로젝트 폴더에 놓으세요.")
                return

            try:
                firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)

            self.db      = firestore.client()
            self.enabled = True
            self._ensure_profile()
            print(f"✅ Firebase Firestore 연결 완료 (user: {self.user_id})")

        except ImportError:
            print("⚠️  Firebase: pip install firebase-admin 으로 설치하세요.")
        except Exception as e:
            print(f"⚠️  Firebase 초기화 실패: {e}")

    def _ensure_profile(self):
        """최초 접속 시 사용자 메타 정보 저장"""
        try:
            ref = self._user_ref().collection("meta").document("profile")
            if not ref.get().exists:
                ref.set({
                    "user_id":    self.user_id,
                    "created_at": datetime.now().isoformat(),
                    "device":     platform.node(),
                })
        except Exception:
            pass

    # ── 실패 패턴 저장 ────────────────────────────────────────────────

    def save_failure(self, ticker: str, result: dict, review_text: str) -> bool:
        """틀린 예측 + 자기분석을 사용자 전용 경로에 저장"""
        if not self.enabled:
            return False
        try:
            pred  = result["pred"]
            ev    = result["eval"]
            data  = result.get("collected_data", {})
            ind   = data.get("market_indicators", {})
            tech  = data.get("technicals", {})
            stock = data.get("stock", {})

            history = stock.get("history", [])
            chg5    = None
            if len(history) >= 5:
                c    = [d["close"] for d in history[-5:]]
                chg5 = round((c[-1] - c[0]) / c[0] * 100, 2)

            signals = {
                "rsi":       tech.get("rsi"),
                "macd_hist": tech.get("histogram"),
                "kospi_pct": ind.get("kospi",         {}).get("change_pct"),
                "sp500_pct": ind.get("sp500_futures", {}).get("change_pct"),
                "usd_pct":   ind.get("usd_krw",       {}).get("change_pct"),
                "chg5":      chg5,
                "bb_pct_b":  tech.get("bb_pct_b"),
            }

            rule       = _extract_rule(review_text)
            pattern_id = f"{ticker}_{result['as_of'].replace('-', '')}"

            doc = {
                "pattern_id":       pattern_id,
                "user_id":          self.user_id,
                "ticker":           ticker,
                "date":             result["as_of"],
                "pred_direction":   pred["direction"],
                "pred_pct_low":     pred["pct_low"],
                "pred_pct_high":    pred["pct_high"],
                "actual_direction": ev["actual_dir"],
                "actual_pct":       ev["actual_pct"],
                "signals":          signals,
                "review_text":      review_text,
                "rule":             rule,
                "confirmed_count":  0,
                "created_at":       datetime.now().isoformat(),
            }

            (
                self._user_ref()
                .collection("failure_patterns")
                .document(ticker)
                .collection("patterns")
                .document(pattern_id)
                .set(doc)
            )

            print(f"  🧠 Firebase: 실패 패턴 저장 완료 ({pattern_id})")
            if rule:
                print(f"     규칙: {rule[:80]}")
            return True

        except Exception as e:
            print(f"  ⚠️  Firebase 저장 실패: {e}")
            return False

    # ── 예측 기록 저장 ────────────────────────────────────────────────

    def save_prediction_record(self, ticker: str, result: dict) -> bool:
        """모든 예측 결과(맞든 틀리든)를 사용자 전용 경로에 기록"""
        if not self.enabled or not result.get("eval"):
            return False
        try:
            pred = result["pred"]
            ev   = result["eval"]
            (
                self._user_ref()
                .collection("prediction_history")
                .document(ticker)
                .collection("records")
                .document(result["as_of"])
                .set({
                    "date":             result["as_of"],
                    "user_id":          self.user_id,
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
                })
            )
            return True
        except Exception as e:
            print(f"  ⚠️  Firebase 기록 저장 실패: {e}")
            return False

    # ── 패턴 조회 ─────────────────────────────────────────────────────

    def get_patterns(self, ticker: str, limit: int = 20) -> list[dict]:
        """사용자 전용 실패 패턴을 최신순 + confirmed_count 순으로 조회"""
        if not self.enabled:
            return []
        try:
            docs = (
                self._user_ref()
                .collection("failure_patterns")
                .document(ticker)
                .collection("patterns")
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            patterns = [d.to_dict() for d in docs]
            patterns.sort(key=lambda x: x.get("confirmed_count", 0), reverse=True)
            return patterns
        except Exception as e:
            print(f"  ⚠️  Firebase 패턴 조회 실패: {e}")
            return []

    def get_similar_patterns(self, ticker: str, current_signals: dict,
                              top_k: int = 5) -> list[dict]:
        """현재 신호와 유사한 과거 실패 패턴 조회"""
        all_patterns = self.get_patterns(ticker, limit=50)
        if not all_patterns:
            return []

        def similarity(p: dict) -> int:
            sig   = p.get("signals", {})
            score = 0
            cr, pr = current_signals.get("rsi"), sig.get("rsi")
            if cr and pr:
                cz = "high" if cr >= 60 else "low" if cr <= 40 else "mid"
                pz = "high" if pr >= 60 else "low" if pr <= 40 else "mid"
                if cz == pz: score += 2
            if ((current_signals.get("sp500_pct") or 0) > 0) == ((sig.get("sp500_pct") or 0) > 0):
                score += 1
            if ((current_signals.get("kospi_pct") or 0) > 0) == ((sig.get("kospi_pct") or 0) > 0):
                score += 1
            if ((current_signals.get("macd_hist") or 0) > 0) == ((sig.get("macd_hist") or 0) > 0):
                score += 1
            score += p.get("confirmed_count", 0)
            return score

        scored = sorted([(p, similarity(p)) for p in all_patterns], key=lambda x: -x[1])
        return [p for p, s in scored[:top_k] if s >= 2]

    # ── 프롬프트용 메모리 블록 생성 ──────────────────────────────────

    def build_memory_block(self, ticker: str, current_signals: dict = None) -> str:
        """관련 실패 패턴을 프롬프트에 주입할 텍스트로 변환"""
        if not self.enabled:
            return ""
        patterns = (
            self.get_similar_patterns(ticker, current_signals, top_k=5)
            if current_signals else self.get_patterns(ticker, limit=5)
        )
        if not patterns:
            return ""

        lines = [f"\n📚 과거 실패 패턴 학습 ({ticker} — {len(patterns)}건)"]
        lines.append("  ※ 아래와 유사한 상황이면 같은 실수를 반복하지 마세요.\n")

        for i, p in enumerate(patterns, 1):
            sig  = p.get("signals", {})
            cnt  = p.get("confirmed_count", 0)
            rule = p.get("rule", "")

            sig_parts = []
            if sig.get("rsi"):       sig_parts.append(f"RSI {sig['rsi']}")
            if sig.get("kospi_pct"): sig_parts.append(f"코스피 {sig['kospi_pct']:+.1f}%")
            if sig.get("sp500_pct"): sig_parts.append(f"S&P500 {sig['sp500_pct']:+.1f}%")
            if sig.get("macd_hist"): sig_parts.append(f"MACD {'양수' if sig['macd_hist'] > 0 else '음수'}")

            lines.append(
                f"  [{i}] {p.get('date','')} | "
                f"{p.get('pred_direction','')} 예측 → 실제 {p.get('actual_direction','')} "
                f"({p.get('actual_pct', 0):+.2f}%)"
                + (f" ✅검증{cnt}회" if cnt > 0 else "")
            )
            lines.append(f"      신호: {' / '.join(sig_parts) or '데이터 없음'}")
            if rule:
                lines.append(f"      📌 규칙: {rule}")
            lines.append("")

        return "\n".join(lines)

    # ── 규칙 검증 업데이트 ────────────────────────────────────────────

    def confirm_rule(self, ticker: str, pattern_id: str) -> bool:
        """패턴 규칙이 실전에서 맞았을 때 confirmed_count 증가"""
        if not self.enabled:
            return False
        try:
            ref = (
                self._user_ref()
                .collection("failure_patterns")
                .document(ticker)
                .collection("patterns")
                .document(pattern_id)
            )
            doc = ref.get()
            if doc.exists:
                ref.update({"confirmed_count": doc.to_dict().get("confirmed_count", 0) + 1})
                return True
        except Exception as e:
            print(f"  ⚠️  규칙 검증 업데이트 실패: {e}")
        return False

    # ── 통계 조회 ─────────────────────────────────────────────────────

    def get_stats(self, ticker: str) -> dict:
        if not self.enabled:
            return {}
        try:
            patterns = self.get_patterns(ticker, limit=100)
            records  = [
                d.to_dict() for d in
                self._user_ref()
                .collection("prediction_history")
                .document(ticker)
                .collection("records")
                .stream()
            ]
            total = len(records)
            hits  = sum(1 for r in records if r.get("hit"))
            return {
                "user_id":           self.user_id,
                "ticker":            ticker,
                "total_predictions": total,
                "direction_acc":     round(hits / total * 100, 1) if total > 0 else 0,
                "failure_patterns":  len(patterns),
                "top_rules":         [p.get("rule", "") for p in patterns[:3] if p.get("rule")],
            }
        except Exception as e:
            return {"error": str(e)}


# ── 규칙 추출 헬퍼 ────────────────────────────────────────────────────

def _extract_rule(review_text: str) -> str:
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
    parts = re.split(r'3[.]', review_text)
    if len(parts) > 1:
        for line in parts[-1].split("\n"):
            clean = line.strip().lstrip("-•* ").strip()
            if (len(clean) > 15
                    and not re.match(r'^[\*#0-9]', clean)
                    and '향후' not in clean
                    and clean[:3] != '규칙'):
                return clean[:200]

    # 4순위: 마지막 의미있는 문장
    sentences = [
        s.strip() for s in re.split(r'[.。\n]', review_text)
        if len(s.strip()) > 20 and not re.match(r'^\*{0,2}[0-9]', s.strip())
    ]
    return sentences[-1][:200] if sentences else ""


# ── 싱글턴 ────────────────────────────────────────────────────────────

_memory_instance: Optional[FirebaseMemory] = None

def get_memory() -> FirebaseMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = FirebaseMemory()
    return _memory_instance


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mem    = get_memory()
    cmd    = sys.argv[1] if len(sys.argv) > 1 else "whoami"
    ticker = sys.argv[2] if len(sys.argv) > 2 else "005930.KS"

    if cmd == "whoami":
        uid     = get_or_create_user_id()
        id_path = _get_user_id_path()
        print(f"\n👤 내 사용자 ID : {uid}")
        print(f"   저장 위치     : {id_path}")
        print(f"   Firebase      : {'연결됨 ✅' if mem.enabled else '연결 안됨 ❌'}")

    elif cmd == "patterns":
        if not mem.enabled: sys.exit(1)
        patterns = mem.get_patterns(ticker)
        print(f"\n🧠 {ticker} 실패 패턴 ({len(patterns)}건) [user: {mem.user_id}]:")
        for p in patterns:
            cnt = p.get("confirmed_count", 0)
            print(f"  {p['date']} | {p.get('pred_direction','')}→{p.get('actual_direction','')} "
                  + (f"✅{cnt}회" if cnt else ""))
            if p.get("rule"):
                print(f"    📌 {p['rule'][:80]}")

    elif cmd == "stats":
        if not mem.enabled: sys.exit(1)
        print(f"\n📊 {ticker} 학습 통계:")
        print(json.dumps(mem.get_stats(ticker), ensure_ascii=False, indent=2))

    elif cmd == "block":
        if not mem.enabled: sys.exit(1)
        print(mem.build_memory_block(ticker) or "(패턴 없음)")

    elif cmd == "reset":
        id_path = _get_user_id_path()
        if id_path.exists():
            id_path.unlink()
            print("✅ user_id 초기화 완료. 다음 실행 시 새 ID가 발급됩니다.")
        else:
            print("user_id 파일이 없습니다.")
            
def save_actual_price(self, ticker: str, date: str, actual_price: float) -> bool:
    """실제 주가를 Firebase에 캐싱"""
    if not self.enabled:
        return False
    try:
        (
            self.db.collection("actual_prices")
            .document(f"{ticker}_{date.replace('-', '')}")
            .set({
                "ticker":       ticker,
                "date":         date,
                "actual_price": actual_price,
                "saved_at":     datetime.now().isoformat(),
            })
        )
        return True
    except Exception as e:
        print(f"  ⚠️  실제가 캐시 저장 실패: {e}")
        return False

def get_actual_price(self, ticker: str, date: str) -> float | None:
    """Firebase에서 실제 주가 캐시 조회"""
    if not self.enabled:
        return None
    try:
        doc = (
            self.db.collection("actual_prices")
            .document(f"{ticker}_{date.replace('-', '')}")
            .get()
        )
        if doc.exists:
            return doc.to_dict().get("actual_price")
        return None
    except Exception:
        return None