""" execute (stub)。未実装"""
from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
load_dotenv()
from collections import defaultdict

import requests

from .models import Signal

log = logging.getLogger(__name__)

def execute(signal: Signal) -> None:
    """発注などの実行差し替え口。プロトタイプではログ出力のみ（stub）。"""
    log.info("execute() stub: %s %s conviction=%.2f", signal.symbol, signal.action, signal.conviction)