"""X（Twitter）投稿層。BUY候補シグナルをツイートする。"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from .models import Signal

load_dotenv()

log = logging.getLogger(__name__)

_LINE_URL = "https://lin.ee/xQcK2fJ"
_HASHTAGS = "#半導体株 #量子コンピュータ #株シグナル"
_MAX_SHOW = 5  # ツイートに載せる最大銘柄数


def _conviction_emoji(conviction: float) -> str:
    return "🔥" if conviction >= 1.0 else "🟢"


def _build_tweet(signals: list[Signal]) -> str | None:
    buy_signals = [s for s in signals if s.action == "buy_candidate"]
    if not buy_signals:
        return None

    from datetime import datetime, timezone, timedelta
    jst = timezone(timedelta(hours=9))
    date_str = datetime.now(jst).strftime("%m/%d")

    lines = [f"📈 シグナル {date_str}  BUY:{len(buy_signals)}"]
    lines.append("")

    for s in buy_signals[:_MAX_SHOW]:
        emoji = _conviction_emoji(s.conviction)
        theme_short = s.theme.split("/")[-1][:4]  # "製造装置" など
        lines.append(f"{emoji} {s.symbol:<5} ({theme_short})  {s.conviction:.2f}")

    if len(buy_signals) > _MAX_SHOW:
        lines.append(f"他 {len(buy_signals) - _MAX_SHOW} 銘柄...")

    lines.append("")
    lines.append(f"詳細・LINE通知 → {_LINE_URL}")
    lines.append(_HASHTAGS)

    return "\n".join(lines)


def send_x(signals: list[Signal]) -> None:
    """BUY候補シグナルをXにブロードキャスト投稿する。"""
    api_key        = os.getenv("X_API_KEY")
    api_secret     = os.getenv("X_API_SECRET")
    access_token   = os.getenv("X_ACCESS_TOKEN")
    access_secret  = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        log.warning("X API キーが未設定です。.env を確認してください。")
        return

    try:
        import tweepy
    except ImportError:
        log.warning("tweepy が未インストールです: pip install tweepy")
        return

    tweet = _build_tweet(signals)
    if tweet is None:
        log.info("BUY候補なし。X投稿をスキップします。")
        return

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    try:
        resp = client.create_tweet(text=tweet)
        log.info("X投稿完了: tweet_id=%s", resp.data["id"])
    except Exception as e:
        log.error("X投稿失敗: %s", e)
