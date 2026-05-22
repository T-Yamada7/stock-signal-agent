"""シグナル生成層。ルールでスコア化して Signal を組み立てる。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

from .models import Signal

log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ルールごとの重み（合計1.0）
W_GOLDEN_CROSS = 0.4
W_VOLUME_SPIKE = 0.3
W_ABOVE_MA_SHORT = 0.3

BUY_THRESHOLD = 0.5
RISK_NOTES_DEFAULT = "決算日程は別途確認すること。価格・出来高は yfinance の遅延データの可能性あり。"


def _evaluate_one(
    code: str,
    name: str,
    theme: str,
    df: pd.DataFrame,
    rules: dict,
    now_iso: str,
) -> Signal | None:
    ma_short_n = int(rules.get("ma_short", 25))
    ma_long_n = int(rules.get("ma_long", 75))
    vol_ratio_th = float(rules.get("volume_spike_ratio", 1.5))

    if "Close" not in df.columns or "Volume" not in df.columns:
        log.warning("必要な列がありません: %s", code)
        return None
    if len(df) < ma_long_n + 1:
        log.warning("データが不足しています (%d行 < %d): %s", len(df), ma_long_n + 1, code)
        return None

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    ma_short = close.rolling(ma_short_n).mean().iloc[-1]
    ma_long = close.rolling(ma_long_n).mean().iloc[-1]
    vol_ma20 = volume.rolling(20).mean().iloc[-1]
    last_close = close.iloc[-1]
    last_volume = volume.iloc[-1]
    volume_ratio = float(last_volume / vol_ma20) if vol_ma20 and vol_ma20 > 0 else 0.0

    score = 0.0
    reasons: list[str] = []

    if pd.notna(ma_short) and pd.notna(ma_long) and ma_short > ma_long:
        score += W_GOLDEN_CROSS
        reasons.append(f"{ma_short_n}日線が{ma_long_n}日線を上回る（ゴールデンクロス傾向）")

    if volume_ratio >= vol_ratio_th:
        score += W_VOLUME_SPIKE
        reasons.append(f"出来高が20日平均の{volume_ratio:.2f}倍")

    if pd.notna(ma_short) and last_close > ma_short:
        score += W_ABOVE_MA_SHORT
        reasons.append(f"終値が{ma_short_n}日線を上回る")

    conviction = round(min(score, 1.0), 3)
    action = "buy_candidate" if conviction >= BUY_THRESHOLD else "watch"

    return Signal(
        symbol=code,
        name=name,
        theme=theme,
        action=action,
        conviction=conviction,
        reasons=reasons,
        risk_notes=RISK_NOTES_DEFAULT,
        metrics={
            "last_close": round(float(last_close), 2),
            "ma_short": round(float(ma_short), 2) if pd.notna(ma_short) else None,
            "ma_long": round(float(ma_long), 2) if pd.notna(ma_long) else None,
            "volume_ratio_vs_20d": round(volume_ratio, 3),
            "last_volume": int(last_volume) if pd.notna(last_volume) else None,
        },
        generated_at=now_iso,
    )


def generate_signals(
    price_data: dict[str, pd.DataFrame],
    watchlist: list[dict],
    rules: dict,
) -> list[Signal]:
    """価格データ＋watchlistからSignalのリストを返す。"""
    now_iso = datetime.now(JST).isoformat(timespec="seconds")
    name_by_code  = {entry["code"]: entry.get("name", entry["code"]) for entry in watchlist}
    theme_by_code = {entry["code"]: entry.get("theme", "") for entry in watchlist}

    signals: list[Signal] = []
    for code, df in price_data.items():
        try:
            sig = _evaluate_one(
                code,
                name_by_code.get(code, code),
                theme_by_code.get(code, ""),
                df, rules, now_iso,
            )
            if sig is not None:
                signals.append(sig)
        except Exception as e:
            log.warning("シグナル生成失敗: %s -> %s", code, e)
            continue

    # conviction降順、buy_candidateを上に
    signals.sort(key=lambda s: (s.action != "buy_candidate", -s.conviction))
    return signals


def llm_evaluate(signals: list[Signal]) -> list[Signal]:
    """将来の差し替え口。デフォルトはパススルー。

    ここで LLM による定性評価を conviction に加味したり、reasons に追記したりする。
    """
    return signals
