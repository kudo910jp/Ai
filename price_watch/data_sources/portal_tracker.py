"""
ポータルサイト追跡データソース

ハウスマーケットが追跡するポータルサイトの掲載物件データを管理する。
物件の出現・消滅・価格変更を時系列で追跡し、
疑似的な取引データとして活用する。

【将来の実装計画】
- SUUMO, HOME'S, at home等のスクレイピング
- ハウスマーケットDB APIとの連携
- 物件マッチング（同一物件の名寄せ）
"""

from __future__ import annotations

from price_watch.data_sources.base import DataSourceBase
from price_watch.models.market import PortalListing, AreaMarketData


class PortalTracker(DataSourceBase):
    """
    ポータルサイト追跡データソース

    物件の掲載状況を追跡し、市場動向の分析に使用する。
    """

    def __init__(self):
        self._listings: list[PortalListing] = []

    def add_listing(self, listing: PortalListing) -> None:
        """掲載物件を登録"""
        self._listings.append(listing)

    def add_listings(self, listings: list[PortalListing]) -> None:
        """掲載物件を一括登録"""
        self._listings.extend(listings)

    def get_listings_by_area(
        self, prefecture: str, city: str,
    ) -> list[PortalListing]:
        """エリアの掲載物件一覧を取得"""
        return [
            l for l in self._listings
            if l.prefecture == prefecture and l.city == city
        ]

    def get_all_listings(self) -> list[PortalListing]:
        return list(self._listings)

    def fetch_land_price(
        self, prefecture: str, city: str, district: str = "",
    ) -> dict | None:
        """エリアの平均土地単価を取得"""
        listings = self.get_listings_by_area(prefecture, city)
        prices = []
        for l in listings:
            if l.price_per_sqm_land and l.price_per_sqm_land > 0:
                prices.append(l.price_per_sqm_land)
        if not prices:
            return None
        return {
            "avg_price_per_sqm": sum(prices) / len(prices),
            "count": len(prices),
        }

    def is_available(self) -> bool:
        return len(self._listings) > 0
