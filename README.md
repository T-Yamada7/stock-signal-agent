# stock-signal-agent

半導体・AI・量子・宇宙など注目テーマの日本株・米国株を対象に、買い候補シグナルを根拠付きで生成する CLI ツール。
平日朝 9 時に GitHub Actions で自動実行し、LINE にブロードキャスト通知します。

> 発注はしません。最後の判断は人間が行います。

## できること

- `config.yaml` の watchlist（約 37 銘柄、日本株・米国株）から yfinance で日足を取得
- 3 つのルールでスコア化し `conviction` 0.0〜1.0 を算出
  - 25 日線 > 75 日線（ゴールデンクロス傾向） … +0.4
  - 出来高 ≥ 20 日平均 × `volume_spike_ratio` … +0.3
  - 終値 > 25 日線（短期上昇基調） … +0.3
- `conviction ≥ 0.5` を `buy_candidate`、それ未満を `watch` として出力
- テーマ別グループ表示（半導体/製造装置・フォトニクス・量子・宇宙 など）
- Claude Haiku による定性コメントを BUY 候補に付与（`ANTHROPIC_API_KEY` 設定時）
- LINE にブロードキャスト通知（Bot を友達追加したユーザー全員に届く）
- 結果を `./signals/YYYY-MM-DD.json` に保存

## カバーしているテーマ

| テーマ | 主な銘柄 |
|--------|----------|
| 半導体/製造装置 | 東京エレクトロン、KOKUSAI ELECTRIC、AMAT、ASML |
| 半導体/設計 | NVIDIA、AMD、Arm Holdings、ソシオネクスト |
| 半導体/メモリ | キオクシア、Micron Technology |
| 半導体/素材・製造 | 信越化学工業、SUMCO、TSMC |
| フォトニクス | 浜松ホトニクス、Fujikura、Coherent Corp |
| 量子 | Rigetti Computing、D-Wave Quantum、IonQ |
| 宇宙 | Rocket Lab、AST SpaceMobile |
| ネオクラウド | さくらインターネット |
| AI/DX | FIG |
| 素材/資源・商社・自動車 | JX金属、伊藤忠商事、トヨタ自動車 |

## セットアップ

Python 3.11+ を想定。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 認証情報を .env に記入
```

`.env` に記入する項目：

```env
LINE_CHANNEL_ACCESS_TOKEN=...   # LINE Developers Console > Messaging API
ANTHROPIC_API_KEY=...           # オプション。未設定時は LLM コメントをスキップ
```

## 実行

```bash
python main.py                  # 評価 + 標準出力 + JSON 保存
python main.py --notify-line    # 上記 + LINE ブロードキャスト
python main.py --dry-run        # JSON 保存なし
python main.py -v               # DEBUG ログ
```

出力例：

```
====================================================
  シグナル 2026-05-22 09:00
  BUY候補: 5  WATCH: 8  合計: 13
====================================================

【量子】 [2BUY]
  [BUY   1.00] RGTI   Rigetti Computing
    - 25日線が75日線を上回る（ゴールデンクロス傾向）
    - 出来高が20日平均の2.04倍
    - 終値が25日線を上回る
    💬 出来高急増を伴うGC成立は上昇モメンタムが強い。短期的な過熱感にも注意。
    ⚠ 決算日程は別途確認すること。
```

## LINE 通知の設定

1. [LINE Developers Console](https://developers.line.biz/) でチャネルを作成（Messaging API）
2. `Channel Access Token` を発行 → `.env` の `LINE_CHANNEL_ACCESS_TOKEN` に設定
3. LINE Official Account の QR コードを共有するだけで友達全員に届く

GitHub Actions での自動実行時は Secrets に `LINE_CHANNEL_ACCESS_TOKEN`（と任意で `ANTHROPIC_API_KEY`）を登録してください。

## 設定のカスタマイズ

`config.yaml` の `rules` でしきい値を変更できます：

```yaml
rules:
  volume_spike_ratio: 1.5   # 出来高急増の倍率
  ma_short: 25              # 短期移動平均日数
  ma_long: 75               # 長期移動平均日数
  lookback_days: 120        # 取得期間
```

`watchlist` に銘柄を追加する場合：

```yaml
watchlist:
  - { code: "6758", name: "ソニーグループ", theme: "AI/DX" }
  - { code: "TSLA", name: "Tesla",         theme: "自動車" }
```

東証銘柄は数字コードを入れると `.T` を自動付与します（例: `6758` → `6758.T`）。

## ファイル構成

```
stock-signal-agent/
├── main.py                # CLI エントリ
├── config.yaml            # watchlist・ルール設定
├── requirements.txt
├── .env.example
├── .github/workflows/
│   └── daily_signal.yml   # 平日 09:00 JST 自動実行
├── signals/               # 出力 JSON（gitignore）
└── agent/
    ├── models.py          # Signal dataclass
    ├── data.py            # 価格データ取得（yfinance）
    ├── signal.py          # ルール評価 + llm_evaluate
    └── notify.py          # 整形 / JSON 保存 / LINE 通知
```

## 将来の拡張ポイント

- **バックテスト**: 過去シグナルと実際の株価変動を照合して精度検証
- **ヒートマップ表示**: `rich` ライブラリでテーマ×コンビクションの視覚化
- **履歴 DB 化**: SQLite にシグナル履歴を蓄積してトレンド分析
- **ニュース連携**: RSS・スクレイピングで定性情報を LLM に渡す
- **決算カレンダー連携**: `risk_notes` を実際の決算日程に基づいた動的注記へ
