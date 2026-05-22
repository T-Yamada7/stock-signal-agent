"""通知層。標準出力整形 / JSON保存 / execute (stub)。"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from .models import Signal

log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# テーマの表示順（未定義テーマは末尾）
_THEME_ORDER = [
    "半導体/製造装置", "半導体/テスト", "半導体/設計", "半導体/メモリ",
    "半導体/素材", "半導体/製造",
    "フォトニクス", "量子", "宇宙", "ネオクラウド", "AI/DX",
    "素材/資源", "商社", "自動車",
]


def _theme_key(theme: str) -> int:
    try:
        return _THEME_ORDER.index(theme)
    except ValueError:
        return len(_THEME_ORDER)


def render(signals: list[Signal]) -> str:
    """人間向けの整形済みテキストを返す。テーマ別にグループ化して表示。"""
    now_str = datetime.now(JST).strftime('%Y-%m-%d %H:%M')
    buy_count  = sum(1 for s in signals if s.action == "buy_candidate")
    watch_count = len(signals) - buy_count
    header = (
        f"{'='*52}\n"
        f"  シグナル {now_str}\n"
        f"  BUY候補: {buy_count}  WATCH: {watch_count}  合計: {len(signals)}\n"
        f"{'='*52}"
    )
    if not signals:
        return header + "\n（対象なし）"

    by_theme: dict[str, list[Signal]] = defaultdict(list)
    for s in signals:
        by_theme[s.theme or "その他"].append(s)

    lines = [header]
    for theme in sorted(by_theme, key=_theme_key):
        sigs = by_theme[theme]
        buy_n = sum(1 for s in sigs if s.action == "buy_candidate")
        suffix = f" [{buy_n}BUY]" if buy_n else ""
        lines.append(f"\n【{theme}】{suffix}")
        for s in sigs:
            tag = "BUY  " if s.action == "buy_candidate" else "WATCH"
            lines.append(f"  [{tag} {s.conviction:.2f}] {s.symbol:<6} {s.name}")
            for r in s.reasons:
                lines.append(f"    - {r}")
            if s.action == "buy_candidate":
                lines.append(f"    ⚠ {s.risk_notes}")
    return "\n".join(lines)


def save_json(signals: list[Signal], json_dir: str) -> str:
    """シグナル全件を1ファイルに保存。保存先パスを返す。"""
    os.makedirs(json_dir, exist_ok=True)
    fname = datetime.now(JST).strftime("%Y-%m-%d") + ".json"
    path = os.path.join(json_dir, fname)
    payload = {
        "generated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "signals": [s.to_dict() for s in signals],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def execute(signal: Signal) -> None:
    """発注などの実行差し替え口。プロトタイプではログ出力のみ（stub）。"""
    log.info("execute() stub: %s %s conviction=%.2f", signal.symbol, signal.action, signal.conviction)
