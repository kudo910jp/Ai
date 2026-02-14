"""データソース基底クラス"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DataSourceBase(ABC):
    """データソースの基底インターフェース"""

    @abstractmethod
    def fetch_land_price(self, prefecture: str, city: str, district: str = "") -> dict | None:
        """土地価格データを取得"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """データソースが利用可能か"""
        ...
