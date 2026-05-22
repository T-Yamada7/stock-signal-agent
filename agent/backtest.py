"""バックテスト層。過去シグナルと実価格を照合して精度を検証する。"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import NamedTuple

import pandas as pd

from .signal import generate_signals

log = logging.getLogger(__name__)

_FWD_DAYS = [5, 10, 20]


class BacktestRecord(NamedTuple):
    as_of: str
    symbol: str
    name: str
    theme: str
    conviction: float
    entry_price: float
    returns: dict[int, float | None]  # {5: 0.032, 10: None, ...}


def run_backtest(
    price_data: dict[str, pd.DataFrame],
    watchlist: list[dict],
    rules: dict,
    lookback_window: int = 45,
    step_days: int = 5,
) -> list[BacktestRecord]:
    """ローリングウィンドウでシグナルを再生成し、実際の騰落率と照合する。

    lookback_window: 何日前まで遡るか（営業日）
    step_days: サイクル間隔（営業日）
    """
    ma_long_n = int(rules.get("ma_long", 75))
    min_rows = ma_long_n + 2
    max_fwd = max(_FWD_DAYS)

    # 全銘柄の日付を統合してソート
    all_dates = sorted({d for df in price_data.values() for d in df.index})
    n = len(all_dates)

    if n < min_rows + max_fwd:
        log.warning(
            "バックテスト: データが不足しています（%d日）。config.yaml の lookback_days を増やしてください。", n
        )
        return []

    # 評価日の範囲: 末尾から max_fwd 手前 〜 lookback_window 手前
    last_eval_idx = n - max_fwd - 1
    first_eval_idx = max(min_rows - 1, last_eval_idx - lookback_window)
    eval_indices = list(range(last_eval_idx, first_eval_idx - 1, -step_days))

    log.info(
        "バックテスト: %d サイクル (%s 〜 %s)",
        len(eval_indices),
        str(all_dates[eval_indices[-1]])[:10],
        str(all_dates[eval_indices[0]])[:10],
    )

    records: list[BacktestRecord] = []

    for idx in eval_indices:
        eval_date = all_dates[idx]

        # その日時点のデータにスライス（十分な行数があるものだけ）
        sliced = {
            code: df[df.index <= eval_date]
            for code, df in price_data.items()
            if len(df[df.index <= eval_date]) >= min_rows
        }
        if not sliced:
            continue

        signals = generate_signals(sliced, watchlist, rules)

        for sig in (s for s in signals if s.action == "buy_candidate"):
            code = sig.symbol
            if code not in price_data:
                continue

            full_df = price_data[code].sort_index()
            entry_price = float(full_df[full_df.index <= eval_date]["Close"].iloc[-1])
            future = full_df[full_df.index > eval_date]

            returns: dict[int, float | None] = {}
            for fwd in _FWD_DAYS:
                if len(future) >= fwd:
                    fp = float(future["Close"].iloc[fwd - 1])
                    returns[fwd] = round((fp - entry_price) / entry_price, 4)
                else:
                    returns[fwd] = None  # まだデータなし

            as_of = str(eval_date.date()) if hasattr(eval_date, "date") else str(eval_date)[:10]
            records.append(BacktestRecord(
                as_of=as_of,
                symbol=code,
                name=sig.name,
                theme=sig.theme,
                conviction=sig.conviction,
                entry_price=entry_price,
                returns=returns,
            ))

    return records


def _stats(records: list[BacktestRecord], fwd: int) -> tuple[float | None, float | None]:
    """勝率と平均リターンを返す（データなしは None）。"""
    valid = [r.returns[fwd] for r in records if r.returns.get(fwd) is not None]
    if not valid:
        return None, None
    wr = sum(1 for v in valid if v > 0) / len(valid)
    avg = sum(valid) / len(valid)
    return wr, avg


def render_backtest(records: list[BacktestRecord]) -> str:
    if not records:
        return "バックテスト結果なし（データが不足している可能性があります）"

    dates = sorted({r.as_of for r in records})
    lines: list[str] = [
        "=" * 56,
        f"  バックテスト  {dates[0]} 〜 {dates[-1]}",
        f"  {len(dates)} サイクル  BUYシグナル延べ {len(records)} 件",
        "=" * 56,
    ]

    # ヘッダー行
    lines.append(f"  {'':14}{'  +5d':>10}{'  +10d':>10}{'  +20d':>10}")
    lines.append("  " + "─" * 46)

    def _row(label: str, recs: list[BacktestRecord]) -> str:
        cells = []
        for fwd in _FWD_DAYS:
            wr, avg = _stats(recs, fwd)
            if wr is None:
                cells.append(f"{'N/A':>10}")
            else:
                n_valid = sum(1 for r in recs if r.returns.get(fwd) is not None)
                cells.append(f"  {wr*100:3.0f}% {avg*100:+.1f}%")
        return f"  {label:<14}" + "".join(cells)

    lines.append(_row("全体", records))

    # テーマ別（2件以上）
    by_theme: dict[str, list[BacktestRecord]] = defaultdict(list)
    for r in records:
        by_theme[r.theme or "その他"].append(r)

    for theme, recs in sorted(by_theme.items(), key=lambda kv: -len(kv[1])):
        if len(recs) >= 2:
            lines.append(_row(theme[:14], recs))

    # 詳細テーブル
    lines.append("")
    lines.append(f"  {'日付':10}  {'銘柄':<6}  {'確信':4}  {'入値':>8}  {'  +5d':>6}  {'+10d':>6}  {'+20d':>6}")
    lines.append("  " + "─" * 54)

    def _ret(v: float | None) -> str:
        return f"{v*100:+.1f}%" if v is not None else "  N/A"

    for r in sorted(records, key=lambda x: (x.as_of, x.symbol), reverse=True):
        lines.append(
            f"  {r.as_of}  {r.symbol:<6}  {r.conviction:.2f}  "
            f"{r.entry_price:>8.2f}  "
            f"{_ret(r.returns.get(5)):>6}  "
            f"{_ret(r.returns.get(10)):>6}  "
            f"{_ret(r.returns.get(20)):>6}"
        )

    return "\n".join(lines)
