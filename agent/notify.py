"""通知層。標準出力整形 / JSON保存 / LINE通知 / execute (stub)。"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

from .models import Signal

load_dotenv()

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


def _reason_codes(reasons: list[str]) -> str:
    codes = []
    for r in reasons:
        if "ゴールデンクロス" in r:
            codes.append("GC")
        elif "出来高" in r:
            codes.append("VL")
        elif "上回る" in r:
            codes.append("MA")
    return "+".join(codes) if codes else "-"


def _conviction_emoji(conviction: float, action: str) -> str:
    if conviction >= 1.0:
        return "🔥"
    if action == "buy_candidate":
        return "🟢"
    return "⚪"


def send_line(signals: list[Signal]) -> None:
    """シグナルをLINE Messaging APIでプッシュ通知する。"""
    token   = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    if not token or not user_id:
        log.warning("LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定です。.env を確認してください。")
        return

    buy_signals = [s for s in signals if s.action == "buy_candidate"]
    if not buy_signals:
        log.info("BUY候補なし。LINE通知をスキップします。")
        return

    lines = [f"📈 シグナル {datetime.now(JST).strftime('%m/%d %H:%M')}  BUY:{len(buy_signals)}"]

    current_theme = None
    for s in buy_signals:
        if s.theme != current_theme:
            current_theme = s.theme
            lines.append(f"\n【{s.theme}】")
        emoji = _conviction_emoji(s.conviction, s.action)
        codes = _reason_codes(s.reasons)
        symbol = s.symbol.ljust(5)
        name   = s.name[:10]
        lines.append(f"{emoji} {symbol} {name}  {s.conviction:.2f}  {codes}")

    lines.append("\n─────────────────")
    lines.append("GC:ゴールデンクロス VL:出来高急増 MA:MA上抜け")

    message = "\n".join(lines)

    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=10,
    )
    if resp.status_code == 200:
        log.info("LINE通知を送信しました。")
    else:
        log.error("LINE通知に失敗しました: %s %s", resp.status_code, resp.text)


def execute(signal: Signal) -> None:
    """発注などの実行差し替え口。プロトタイプではログ出力のみ（stub）。"""
    log.info("execute() stub: %s %s conviction=%.2f", signal.symbol, signal.action, signal.conviction)
