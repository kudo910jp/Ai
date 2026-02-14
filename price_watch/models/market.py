"""
市場データモデル

ポータルサイトの掲載情報、ハウスマーケットDBの追跡データ、
類似物件（コンパラブル）データを構造化して管理する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from price_watch.config import StructureType, PropertyType, DataSourceType


class ListingStatus(Enum):
    """物件掲載ステータス"""
    ACTIVE = "掲載中"
    REMOVED_SOLD = "消滅・売却済"
    REMOVED_SUSPENDED = "消滅・一時停止"
    REMOVED_UNKNOWN = "消滅・理由不明"
    PRICE_CHANGED = "価格変更"
    RELISTED = "再掲載"


@dataclass
class PortalListing:
    """
    ポータルサイト掲載物件データ

    ハウスマーケットが追跡する物件の掲載情報。
    物件の出現・消滅・価格変更を時系列で追跡し、
    疑似的な取引データとして活用する。
    """
    listing_id: str                          # 掲載物件ID
    source: str                              # ソースサイト名
    property_type: PropertyType
    address: str
    prefecture: str
    city: str
    land_area_sqm: float | None = None
    building_area_sqm: float | None = None
    structure_type: StructureType | None = None
    built_date: date | None = None
    rooms: str = ""
    asking_price_yen: int = 0                # 売出価格
    price_per_sqm_land: float | None = None  # 土地坪単価
    first_seen_date: date | None = None      # 初回出現日
    last_seen_date: date | None = None       # 最終確認日
    removed_date: date | None = None         # 消滅日
    status: ListingStatus = ListingStatus.ACTIVE
    price_history: list[dict] = field(default_factory=list)
    # 例: [{"date": "2025-01-15", "price": 45000000}, {"date": "2025-03-01", "price": 42000000}]

    # ヒアリング結果
    sold_price_yen: int | None = None        # 成約価格（判明している場合）
    agent_feedback: str = ""                  # 不動産会社からのフィードバック

    @property
    def days_on_market(self) -> int | None:
        """掲載日数（Days on Market）"""
        if self.first_seen_date is None:
            return None
        end = self.removed_date or date.today()
        return (end - self.first_seen_date).days

    @property
    def price_reduction_rate(self) -> float | None:
        """価格変更率（初回価格からの変動率）"""
        if not self.price_history or len(self.price_history) < 2:
            return None
        initial = self.price_history[0].get("price", 0)
        current = self.price_history[-1].get("price", 0)
        if initial == 0:
            return None
        return (current - initial) / initial

    @property
    def estimated_transaction_price(self) -> int | None:
        """推定成約価格（成約価格が不明の場合は売出価格から推定）"""
        if self.sold_price_yen:
            return self.sold_price_yen
        if self.status == ListingStatus.REMOVED_SOLD and self.asking_price_yen > 0:
            # 売却済みだが成約価格不明：売出価格から平均値引率で推定
            return int(self.asking_price_yen * 0.95)
        return None


@dataclass
class MarketComparable:
    """
    類似物件（コンパラブル）データ

    対象物件と類似する物件のデータ。
    査定における比較対象として使用される。
    """
    listing: PortalListing
    similarity_score: float = 0.0            # 類似度スコア（0-1）
    distance_km: float = 0.0                 # 対象物件からの距離（km）
    data_source: DataSourceType = DataSourceType.PORTAL_SITE
    adjustments: dict = field(default_factory=dict)
    # 補正項目: {"面積差補正": -0.05, "築年数補正": +0.03, ...}

    @property
    def adjusted_price_per_sqm(self) -> float | None:
        """補正後の㎡単価"""
        base = self.listing.price_per_sqm_land
        if base is None:
            return None
        total_adjustment = sum(self.adjustments.values())
        return base * (1 + total_adjustment)


@dataclass
class AreaMarketData:
    """
    エリア市場データ

    特定エリアの市場動向を集約したデータ。
    トレンド分析、平均価格、流動性指標等を含む。
    """
    prefecture: str
    city: str
    district: str = ""
    analysis_date: date = field(default_factory=date.today)

    # 価格指標
    avg_price_per_sqm: float | None = None       # 平均㎡単価
    median_price_per_sqm: float | None = None    # 中央値㎡単価
    price_trend_pct: float | None = None         # 価格トレンド（前年比%）

    # 流動性指標
    active_listing_count: int = 0                 # 現在掲載中件数
    avg_days_on_market: float | None = None       # 平均掲載日数
    monthly_sold_count: int = 0                   # 月間成約件数（推定）
    absorption_rate: float | None = None          # 在庫消化率（月）

    # トレンドデータ
    quarterly_price_index: list[dict] = field(default_factory=list)
    # 例: [{"quarter": "2025Q1", "index": 100}, {"quarter": "2025Q2", "index": 102}]

    @property
    def market_temperature(self) -> str:
        """
        市場の温度感

        在庫消化率（Absorption Rate）から市場の需給バランスを判定:
        - 6ヶ月未満: 売り手市場（需要 > 供給）
        - 6-9ヶ月: 均衡市場
        - 9ヶ月超: 買い手市場（供給 > 需要）
        """
        if self.absorption_rate is None:
            return "判定不能"
        if self.absorption_rate < 6:
            return "売り手市場"
        elif self.absorption_rate <= 9:
            return "均衡市場"
        else:
            return "買い手市場"

    @property
    def data_quality_score(self) -> float:
        """データ品質スコア（0-1）: データの充実度を数値化"""
        score = 0.0
        if self.avg_price_per_sqm is not None:
            score += 0.2
        if self.median_price_per_sqm is not None:
            score += 0.2
        if self.active_listing_count > 0:
            score += 0.2
        if self.avg_days_on_market is not None:
            score += 0.2
        if len(self.quarterly_price_index) >= 4:
            score += 0.2
        return score
