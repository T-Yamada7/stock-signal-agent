#結果を/signalsフォルダに格納するための関数を定義
from __future__ import annotations
import json, os
from datetime import datetime, timezone, timedelta
from .models import Signal

JST = timezone(timedelta(hours=9))

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