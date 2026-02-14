"""
価格ウォッチ システム設定

査定ロジックに使用するパラメータ、減価償却率、信頼度係数等を一元管理する。
これらの値は不動産鑑定の実務知見と市場データに基づいて設定されており、
定期的な市場分析により更新される。
"""

from dataclasses import dataclass, field
from enum import Enum


class StructureType(Enum):
    """建物構造種別"""
    WOOD = "木造"
    LIGHT_STEEL = "軽量鉄骨造"
    STEEL = "鉄骨造"
    RC = "鉄筋コンクリート造"
    SRC = "鉄骨鉄筋コンクリート造"


class PropertyType(Enum):
    """物件種別"""
    DETACHED_HOUSE = "戸建て"
    APARTMENT = "マンション"
    LAND = "土地"
    COMMERCIAL = "事業用"


class DataSourceType(Enum):
    """データソース種別"""
    HOUSE_MARKET_DB = "ハウスマーケットDB"
    PORTAL_SITE = "ポータルサイト"
    ROSENKA = "路線価"
    KOJI_CHIKA = "公示地価"
    CHIKA_KOJI = "基準地価"
    GOVERNMENT_TRANSACTION = "国土交通省取引事例"
    ONSITE_APPRAISAL = "現地査定"


# ──────────────────────────────────────────────
# 建物減価償却設定
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class DepreciationConfig:
    """
    建物コンポーネント別の減価償却設定

    【設計思想 - チームからのフィードバック】
    従来の日本の査定では建物を一体として耐用年数で減価償却するが、
    これは実態と乖離する。実際の建物価値は以下の3層で異なる速度で減耗する:

    1. 基礎・躯体（Foundation/Structure）: 建物の骨格。適切なメンテナンスで
       法定耐用年数を超えて機能する。長期償却。
    2. 設備・水回り（Equipment/Plumbing）: キッチン・浴室・給排水等。
       15-25年で大規模更新が必要。中期償却。
    3. 内装・仕上げ（Interior/Finish）: 壁紙・フローリング・建具等。
       10-15年で劣化が顕著。短期償却。

    この3層モデルにより、リフォーム済み物件の価値を適切に評価できる。
    例：築30年でも水回りと内装を全面リフォーム済みなら、
    基礎躯体の償却のみが反映され、実態に即した評価となる。
    """
    # 各コンポーネントの価値構成比率（合計=1.0）
    foundation_ratio: float = 0.45   # 基礎・躯体の価値割合
    equipment_ratio: float = 0.30    # 設備・水回りの価値割合
    interior_ratio: float = 0.25     # 内装・仕上げの価値割合

    # 残存価値率（完全償却後も残る価値の割合）
    foundation_residual: float = 0.10
    equipment_residual: float = 0.05
    interior_residual: float = 0.03


# 構造種別ごとの法定耐用年数と各コンポーネント耐用年数
STRUCTURE_USEFUL_LIFE: dict[StructureType, dict] = {
    StructureType.WOOD: {
        "legal": 22,         # 法定耐用年数
        "foundation": 35,    # 基礎・躯体
        "equipment": 20,     # 設備・水回り
        "interior": 12,      # 内装・仕上げ
    },
    StructureType.LIGHT_STEEL: {
        "legal": 27,
        "foundation": 40,
        "equipment": 22,
        "interior": 13,
    },
    StructureType.STEEL: {
        "legal": 34,
        "foundation": 50,
        "equipment": 25,
        "interior": 15,
    },
    StructureType.RC: {
        "legal": 47,
        "foundation": 65,
        "equipment": 25,
        "interior": 15,
    },
    StructureType.SRC: {
        "legal": 47,
        "foundation": 70,
        "equipment": 28,
        "interior": 15,
    },
}


# ──────────────────────────────────────────────
# 土地評価設定
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class LandValuationConfig:
    """
    土地評価設定

    【設計思想】
    日本の土地評価には「一物四価」と呼ばれる複数の公的価格が存在する:
    - 公示地価（国土交通省）: 市場価格の基準。年1回発表。
    - 基準地価（都道府県）: 公示地価の補完。年1回発表。
    - 路線価（国税庁）: 相続税・贈与税の算定基準。公示地価の約80%。
    - 固定資産税評価額: 固定資産税の算定基準。公示地価の約70%。

    これらに加え、ポータルサイトの実売データ、ハウスマーケットDBの
    取引追跡データを組み合わせることで、市場実勢に近い土地価格を算出する。
    """
    # 路線価から市場価格への変換係数（路線価 ÷ 0.8 ≒ 公示地価 ≒ 市場価格）
    rosenka_to_market_ratio: float = 0.80

    # 公示地価から市場価格への乖離調整（エリアにより±10-20%の乖離がある）
    koji_chika_market_adjustment: float = 1.05

    # データソース別の信頼度重み付け
    weight_house_market_db: float = 0.40    # ハウスマーケットDB（最も信頼性高）
    weight_portal_data: float = 0.30        # ポータルサイト売出価格
    weight_rosenka: float = 0.15            # 路線価
    weight_koji_chika: float = 0.10         # 公示地価
    weight_gov_transaction: float = 0.05    # 国土交通省取引事例


# ──────────────────────────────────────────────
# 市場動向分析設定
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class MarketAnalysisConfig:
    """
    市場動向分析設定

    【設計思想 - チームディスカッションから】
    MLSがない日本では、ポータルサイトの物件掲載状況が市場の温度計になる。
    物件の「出現」と「消滅」を追跡し、消滅理由（売却済 / 一時停止 / 価格変更）
    を不動産会社へのヒアリングで補完することで、疑似的な取引データを構築する。

    売出期間（Days on Market）は価格の適正性の重要指標:
    - 短期間で消滅 → 売出価格が市場価格以下だった可能性が高い
    - 長期掲載 → 売出価格が市場価格を上回っている可能性が高い
    - 価格変更を伴う長期掲載 → 当初価格と変更後価格の差が市場乖離幅を示唆
    """
    # 売出価格から成約価格への平均乖離率（売出価格に対する値引率）
    avg_negotiation_discount: float = 0.05  # 平均5%の値引き

    # 掲載期間による価格調整係数
    # 掲載日数 → 売出価格に対する推定成約率
    dom_adjustment: dict = field(default_factory=lambda: {
        30: 0.98,    # 30日以内: ほぼ売出価格で成約
        60: 0.96,    # 60日以内: 約4%引き
        90: 0.93,    # 90日以内: 約7%引き
        120: 0.90,   # 120日以内: 約10%引き
        180: 0.87,   # 180日以内: 約13%引き
        365: 0.83,   # 1年超: 大幅な乖離
    })

    # 市場トレンド分析の最小データポイント数
    min_data_points_for_trend: int = 10

    # 類似物件の検索半径（km）
    comparable_search_radius_km: float = 2.0


# ──────────────────────────────────────────────
# 信頼度スコア設定
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class ConfidenceConfig:
    """
    査定結果の信頼度スコア設定

    【設計思想】
    査定金額が「正当な金額かどうかは誰にもわからない」という現実を踏まえ、
    金額そのものよりも「判断材料としての品質」を明示することが重要。
    信頼度スコアにより、ユーザーは査定結果をどの程度信頼して良いかを判断できる。

    信頼度は以下の要素から算出:
    1. データソースの数と品質
    2. 類似物件データの豊富さ
    3. 市場の流動性（物件の動きが活発かどうか）
    4. データの鮮度（最新のデータほど信頼性が高い）
    """
    # 各要素の信頼度への寄与度（合計=1.0）
    weight_data_source_count: float = 0.25
    weight_comparable_count: float = 0.30
    weight_market_liquidity: float = 0.25
    weight_data_freshness: float = 0.20

    # 信頼度ランク閾値
    rank_a_threshold: float = 0.80  # 高信頼: 複数データソース、豊富な類似事例
    rank_b_threshold: float = 0.60  # 中信頼: 一定のデータあり
    rank_c_threshold: float = 0.40  # 低信頼: データ不足だが参考値あり
    # D: 0.40未満 → 参考程度
