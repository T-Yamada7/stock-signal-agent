""" execute (stub)。未実装"""
from __future__ import annotations

import logging
import os
from .models import Signal

log = logging.getLogger(__name__)

"""---------------------"""
import requests
from dotenv import load_dotenv
load_dotenv()
"""現時点で未使用だが，このファイルが発注機能である以上は，これらのモジュールが使用されることになるだろうことは自明
"""


def execute(signal: Signal) -> None:
    """発注などの実行差し替え口。プロトタイプではログ出力のみ（stub）。"""
    log.info("execute() stub: %s %s conviction=%.2f", signal.symbol, signal.action, signal.conviction)