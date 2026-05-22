"""CLIエントリ。config.yaml を読み、data → signal → notify と流す。"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from agent.data import fetch_prices
from agent.signal import generate_signals, llm_evaluate
from agent.notify import render, save_json, send_line


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="株式シグナル生成エージェント（プロトタイプ）")
    p.add_argument("--config", default="config.yaml", help="設定ファイルのパス")
    p.add_argument("--dry-run", action="store_true", help="JSON保存せず標準出力だけ")
    p.add_argument("--json-only", action="store_true", help="標準出力を抑え、JSONだけ保存")
    p.add_argument("--notify-line", action="store_true", help="BUY候補をLINEに通知する")
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUGログを出す")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"設定ファイルが見つかりません: {cfg_path}", file=sys.stderr)
        return 1

    cfg = load_config(str(cfg_path))
    watchlist = cfg.get("watchlist", [])
    rules = cfg.get("rules", {})
    json_dir = cfg.get("output", {}).get("json_dir", "./signals")
    lookback = int(rules.get("lookback_days", 120))

    if not watchlist:
        print("watchlist が空です。config.yaml を確認してください。", file=sys.stderr)
        return 1

    price_data = fetch_prices(watchlist, lookback_days=lookback)
    if not price_data:
        print("すべての銘柄で価格データ取得に失敗しました。", file=sys.stderr)
        return 2

    signals = generate_signals(price_data, watchlist, rules)
    signals = llm_evaluate(signals)  # 現状はパススルー

    if not args.json_only:
        print(render(signals))

    if args.notify_line:
        send_line(signals)

    if not args.dry_run:
        path = save_json(signals, json_dir)
        if not args.json_only:
            print(f"\n保存先: {path}")
        else:
            print(path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
