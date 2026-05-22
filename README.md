# stock-signal-agent

日本株について、買い候補のシグナルを根拠付きで生成するローカル CLI ツール（プロトタイプ）。
発注はしません。最後の判断は人間が行います。

## できること

- `config.yaml` の watchlist 各銘柄について yfinance から日足を取得
- 3つのルールでスコア化し、`conviction` 0.0〜1.0 を算出
  - 25日線 > 75日線（ゴールデンクロス傾向） … +0.4
  - 出来高 ≥ 20日平均 × `volume_spike_ratio` … +0.3
  - 終値 > 25日線（短期上昇基調） … +0.3
- `conviction ≥ 0.5` を `buy_candidate`、それ未満を `watch` として出力
- 結果を標準出力に整形表示し、`./signals/YYYY-MM-DD.json` に保存

## セットアップ

Python 3.11+ を想定。venv を切るのを推奨します。

```bash
cd ~/Desktop/dev/stock-signal-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 実行

```bash
python main.py             # 評価して標準出力 + JSON保存
python main.py --dry-run   # JSON保存せず標準出力だけ
python main.py --json-only # 標準出力を抑え、JSONだけ保存
python main.py -v          # DEBUGログを出す
```

出力例：

```
=== 2026-05-20 09:00 シグナル ===
[BUY   0.70] 5016 JX金属
  - 25日線が75日線を上回る（ゴールデンクロス傾向）
  - 終値が25日線を上回る
  リスク: 決算日程は別途確認すること。価格・出来高は yfinance の遅延データの可能性あり。
[WATCH 0.30] 6701 NEC
  - 終値が25日線を上回る

保存先: ./signals/2026-05-20.json
```

## しきい値の変え方

`config.yaml` の `rules` を編集：

```yaml
rules:
  volume_spike_ratio: 1.5   # 出来高急増の倍率
  ma_short: 25              # 短期移動平均日数
  ma_long: 75               # 長期移動平均日数
  lookback_days: 120        # 取得期間
```

スコアの重み（GC=0.4, 出来高=0.3, 短期上昇=0.3）と判定閾値（0.5）は `agent/signal.py` の定数で調整できます。

## 監視銘柄の変更

`config.yaml` の `watchlist` に `{ code: "xxxx", name: "..." }` を追加するだけです。
東証銘柄は数字4桁の `code` を入れれば `.T` を自動付与します。

> 注: Kioxia (285A) のような英字混じりの新型コードは yfinance での取扱いが不安定なため、初期 watchlist からは除外しています。試したい場合は追加して挙動を確認してください（失敗時は警告ログでスキップされます）。

## ファイル構成

```
stock-signal-agent/
├── README.md
├── requirements.txt
├── config.yaml
├── main.py                # CLIエントリ
├── signals/               # 出力先
└── agent/
    ├── __init__.py
    ├── models.py          # Signal dataclass
    ├── data.py            # 価格データ取得 (yfinance)
    ├── signal.py          # ルール評価 + llm_evaluate フック
    └── notify.py          # 整形 / JSON保存 / execute フック
```

## 将来の拡張ポイント

- **LLM 評価の差し込み**: `agent/signal.py` の `llm_evaluate(signals)` が現在パススルー。
  ここでニュースや決算等の定性情報を踏まえて `conviction` を上書き／`reasons` を追記する。
- **発注実行**: `agent/notify.py` の `execute(signal)` が現在 stub（ログ出力のみ）。
  証券会社 API クライアントをここに差し込めば、`buy_candidate` を発注に流せる構造。
- **決算カレンダー連携**: `risk_notes` を固定文言から、実際の決算日程に基づいた動的注記へ。
- **シグナル種別の追加**: 出来高急減・乖離率・RSI 等を追加し重み付けを再調整。

## 設計メモ

- 3層（`data` / `signal` / `notify`）を `Signal` dataclass だけで疎結合化。
- 全条件 AND ではなくスコア合算式。LLM 評価を後段で重ねやすい。
- データ取得は失敗しても他銘柄の処理を止めない（警告ログでスキップ）。
- タイムゾーンは Asia/Tokyo 固定。
