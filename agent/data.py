"""価格データ取得層。watchlist を受け取り {code: DataFrame} を返す。"""
from __future__ import annotations

import logging
import re
import time

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# 東証コード: 3〜4桁数字 + オプションのアルファベット1文字 (例: 6857, 285A)
_JP_CODE = re.compile(r'^\d{3,4}[A-Z]?$')


def _to_ticker(code: str) -> str:
    if code.endswith(".T"):
        return code
    return f"{code}.T" if _JP_CODE.match(code) else code


def fetch_prices(
    watchlist: list[dict],
    lookback_days: int,
) -> dict[str, pd.DataFrame]:
    """各銘柄の日足を取得して返す。失敗銘柄は警告ログを出してスキップ。"""
    period = f"{max(lookback_days, 30)}d"
    result: dict[str, pd.DataFrame] = {}

    for i, entry in enumerate(watchlist):
        code = entry["code"]
        ticker = _to_ticker(code)
        # Yahoo Finance のレート制限回避: 2件ごとに0.5秒待機
        if i > 0 and i % 2 == 0:
            time.sleep(0.5)
        try:
            df = yf.download(
                ticker,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if df is None or df.empty:
                log.warning("価格データが空でした: %s (%s)", code, entry.get("name", ""))
                continue
            # yfinance は MultiIndex で返すことがあるためフラット化
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            result[code] = df
        except Exception as e:  # 取得失敗は他銘柄の処理を止めない
            log.warning("価格データ取得失敗: %s (%s) -> %s", code, entry.get("name", ""), e)
            continue

    return result
