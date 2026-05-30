from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from .models import Signal
from .evaluate_one import _evaluate_one

log = logging.getLogger(__name__)

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
