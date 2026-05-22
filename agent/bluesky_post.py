"""Bluesky投稿層。BUY候補シグナルを投稿する。"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from .models import Signal

load_dotenv()

log = logging.getLogger(__name__)

_LINE_URL = "https://lin.ee/xQcK2fJ"
_HASHTAGS = "#半導体株 #量子コンピュータ #株シグナル"
_MAX_SHOW = 5


def _conviction_emoji(conviction: float) -> str:
    return "🔥" if conviction >= 1.0 else "🟢"


def _build_post(signals: list[Signal]) -> str | None:
    buy_signals = [s for s in signals if s.action == "buy_candidate"]
    if not buy_signals:
        return None

    jst = timezone(timedelta(hours=9))
    date_str = datetime.now(jst).strftime("%m/%d")

    lines = [f"📈 シグナル {date_str}  BUY:{len(buy_signals)}"]
    lines.append("")

    for s in buy_signals[:_MAX_SHOW]:
        emoji = _conviction_emoji(s.conviction)
        theme_short = s.theme.split("/")[-1][:4]
        lines.append(f"{emoji} {s.symbol:<5} ({theme_short})  {s.conviction:.2f}")

    if len(buy_signals) > _MAX_SHOW:
        lines.append(f"他 {len(buy_signals) - _MAX_SHOW} 銘柄...")

    lines.append("")
    lines.append(f"詳細・LINE通知 → {_LINE_URL}")
    lines.append(_HASHTAGS)

    return "\n".join(lines)


def _build_facets(text: str) -> list:
    """URLとハッシュタグをリンク化するfacetsを生成する。
    BlueskyはUTF-8バイトオフセットで位置を指定する必要がある。
    """
    try:
        from atproto import models
    except ImportError:
        return []

    facets = []

    F = models.AppBskyRichtextFacet

    # URL
    for m in re.finditer(r'https?://[^\s\n]+', text):
        byte_start = len(text[:m.start()].encode('utf-8'))
        byte_end   = len(text[:m.end()].encode('utf-8'))
        facets.append(F.Main(
            features=[F.Link(uri=m.group())],
            index=F.ByteSlice(byte_start=byte_start, byte_end=byte_end),
        ))

    # ハッシュタグ（日本語含む）
    for m in re.finditer(r'#([^\s#\n]+)', text):
        byte_start = len(text[:m.start()].encode('utf-8'))
        byte_end   = len(text[:m.end()].encode('utf-8'))
        facets.append(F.Main(
            features=[F.Tag(tag=m.group(1))],
            index=F.ByteSlice(byte_start=byte_start, byte_end=byte_end),
        ))

    return facets


def send_bluesky(signals: list[Signal]) -> None:
    """BUY候補シグナルをBlueskyに投稿する。"""
    handle   = os.getenv("BSKY_HANDLE")
    password = os.getenv("BSKY_APP_PASSWORD")

    if not handle or not password:
        log.warning("BSKY_HANDLE / BSKY_APP_PASSWORD が未設定です。.env を確認してください。")
        return

    try:
        from atproto import Client
    except ImportError:
        log.warning("atproto が未インストールです: pip install atproto")
        return

    post = _build_post(signals)
    if post is None:
        log.info("BUY候補なし。Bluesky投稿をスキップします。")
        return

    facets = _build_facets(post)
    try:
        client = Client()
        client.login(handle, password)
        client.send_post(text=post, facets=facets)
        log.info("Bluesky投稿完了")
    except Exception as e:
        log.error("Bluesky投稿失敗: %s", e)
