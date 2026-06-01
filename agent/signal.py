"""シグナル生成層。ルールでスコア化して Signal を組み立てる。"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

import pandas as pd
from dotenv import load_dotenv

from .models import Signal

load_dotenv()

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


_LLM_SYSTEM = """\
あなたは株式テクニカル分析の専門家です。
与えられた銘柄のシグナルデータをもとに、投資判断の補足コメントを日本語で50〜80文字程度で書いてください。
テクニカルシグナルの意味と注意点を簡潔にまとめること。余計な前置き・後書き不要。コメント本文のみ出力すること。\
"""


def llm_evaluate(signals: list[Signal]) -> list[Signal]:
    """BUY候補シグナルにClaude Haikuの定性コメントを付与する。
    ANTHROPIC_API_KEY が未設定の場合はパススルー。
    """
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY 未設定。LLM評価をスキップします。")
        return signals

    try:
        import anthropic
    except ImportError:
        log.warning("anthropic パッケージが未インストールです。LLM評価をスキップします。")
        return signals

    client = anthropic.Anthropic(api_key=api_key)
    buy_signals = [s for s in signals if s.action == "buy_candidate"]

    for s in buy_signals:
        user_msg = (
            f"銘柄: {s.name}（{s.symbol}）テーマ: {s.theme}\n"
            f"コンビクション: {s.conviction:.2f}\n"
            f"シグナル理由: {' / '.join(s.reasons)}\n"
            f"直近終値: {s.metrics.get('last_close')}  "
            f"MA25: {s.metrics.get('ma_short')}  "
            f"MA75: {s.metrics.get('ma_long')}  "
            f"出来高倍率: {s.metrics.get('volume_ratio_vs_20d')}"
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=150,
                system=[
                    {
                        "type": "text",
                        "text": _LLM_SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_msg}],
            )
            s.llm_comment = resp.content[0].text.strip()
            log.debug("LLMコメント取得: %s -> %s", s.symbol, s.llm_comment)
        except Exception as e:
            log.warning("LLMコメント取得失敗: %s -> %s", s.symbol, e)

    return signals
