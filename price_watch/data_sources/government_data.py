"""
公的データソース

路線価（国税庁）、公示地価（国土交通省）、基準地価（都道府県）、
国土交通省取引事例等の公的データを取得する。

【将来の実装計画】
- 国土交通省 不動産取引価格情報API
- 国税庁 路線価データ（PDFスクレイピング or API）
- 国土交通省 地価公示データ
"""

from __future__ import annotations

from dataclasses import dataclass

from price_watch.data_sources.base import DataSourceBase


@dataclass
class GovernmentLandPrice:
    """公的土地価格データ"""
    rosenka_per_sqm: float | None = None        # 路線価（㎡単価）
    koji_chika_per_sqm: float | None = None     # 公示地価（㎡単価）
    kijun_chika_per_sqm: float | None = None    # 基準地価（㎡単価）
    gov_transaction_per_sqm: float | None = None # 国交省取引事例（㎡単価）
    reference_year: int | None = None            # データの基準年


class GovernmentDataSource(DataSourceBase):
    """
    公的データソース

    現時点ではモックデータを返す。
    将来、各省庁のAPIやデータベースと接続する。
    """

    def __init__(self):
        self._mock_data: dict[str, GovernmentLandPrice] = {}

    def register_mock_data(self, key: str, data: GovernmentLandPrice) -> None:
        """テスト・開発用のモックデータを登録"""
        self._mock_data[key] = data

    def fetch_land_price(
        self, prefecture: str, city: str, district: str = "",
    ) -> GovernmentLandPrice | None:
        """公的土地価格データを取得"""
        # 完全一致キー → 市区町村キー → 都道府県キーの順で探索
        for key in [
            f"{prefecture}/{city}/{district}",
            f"{prefecture}/{city}",
            prefecture,
        ]:
            if key in self._mock_data:
                return self._mock_data[key]
        return None

    def is_available(self) -> bool:
        return True
