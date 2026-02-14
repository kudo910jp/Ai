# 価格ウォッチ - 不動産自動査定システム (Price Watch)

日本の不動産市場における価格査定の課題を解決するための自動査定エンジン。

## 概要

日本にはアメリカのMLS（Multiple Listing Service）のような包括的な取引データベースが存在しないため、
複数のデータソースを組み合わせた独自の査定ロジックにより、信頼性の高い不動産価格査定を実現します。

## 2段階査定方式

### Stage 1: 自動計算査定
- 住所・土地面積・建物面積・築年数・構造種別から自動算出
- ポータルサイトデータ、路線価、公示地価等を活用
- 短時間で概算価格を提示

### Stage 2: 現地査定
- 不動産査定員による現地調査
- 外観・現況・市場動向を反映した詳細査定
- Stage 1の結果を基礎に精度を向上

## Tech Stack
- Python 3.10+
- データモデル: dataclasses / Pydantic
- 設定: YAML

## プロジェクト構成
```
price_watch/
├── __init__.py
├── config.py              # システム設定
├── models/                # データモデル
│   ├── __init__.py
│   ├── property.py        # 物件モデル
│   ├── market.py          # 市場データモデル
│   └── assessment.py      # 査定結果モデル
├── engines/               # 査定エンジン
│   ├── __init__.py
│   ├── land_valuation.py  # 土地評価エンジン
│   ├── building_depreciation.py  # 建物減価償却エンジン
│   ├── market_analyzer.py # 市場動向分析
│   ├── stage1_auto.py     # Stage 1 自動査定
│   └── stage2_onsite.py   # Stage 2 現地査定
├── data_sources/          # データソース連携
│   ├── __init__.py
│   ├── portal_tracker.py  # ポータルサイト追跡
│   ├── government_data.py # 行政データ(路線価・公示地価)
│   └── house_market_db.py # ハウスマーケットDB
└── main.py                # メインエントリーポイント
```
