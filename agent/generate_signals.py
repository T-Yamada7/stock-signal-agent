"""
シグナル生成層。ルールでスコア化して Signal を組み立てる。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

from .models import Signal
from .evaluate_one import _evaluate_one

log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

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

