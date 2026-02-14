"""
土地評価エンジン

複数データソースの加重平均により土地価格を算出する。
日本特有の「一物四価」と市場実勢データを統合し、
信頼度付きの土地評価を提供する。
"""

from __future__ import annotations

from price_watch.config import (
    LandValuationConfig,
    DataSourceType,
)
from price_watch.models.property import LandInfo, LandShape, LandFacing
from price_watch.models.market import AreaMarketData, MarketComparable
from price_watch.models.assessment import LandAssessmentDetail


class LandValuationEngine:
    """土地評価エンジン"""

    def __init__(self, config: LandValuationConfig | None = None):
        self.config = config or LandValuationConfig()

        # 形状補正率テーブル
        self._shape_adjustments: dict[LandShape, float] = {
            LandShape.RECTANGLE: 0.00,
            LandShape.TRAPEZOID: -0.03,
            LandShape.FLAG: -0.15,
            LandShape.IRREGULAR: -0.10,
            LandShape.TRIANGLE: -0.12,
        }

        # 接道方向補正率テーブル
        self._facing_adjustments: dict[LandFacing, float] = {
            LandFacing.SOUTH: 0.00,
            LandFacing.SOUTH_EAST: -0.01,
            LandFacing.SOUTH_WEST: -0.01,
            LandFacing.EAST: -0.03,
            LandFacing.WEST: -0.04,
            LandFacing.NORTH: -0.07,
            LandFacing.CORNER: 0.05,
        }

    def evaluate(
        self,
        land: LandInfo,
        market_data: AreaMarketData | None = None,
        comparables: list[MarketComparable] | None = None,
        rosenka_price_per_sqm: float | None = None,
        koji_chika_price_per_sqm: float | None = None,
        gov_transaction_price_per_sqm: float | None = None,
    ) -> LandAssessmentDetail:
        """
        土地を評価する

        複数データソースの加重平均で基準㎡単価を算出し、
        形状・接道・道路幅員等の補正を適用する。
        """
        price_sources: dict[str, float] = {}
        weighted_prices: list[tuple[float, float]] = []  # (price, weight)

        # 1. 路線価ベースの市場価格推定
        if rosenka_price_per_sqm is not None and rosenka_price_per_sqm > 0:
            market_from_rosenka = rosenka_price_per_sqm / self.config.rosenka_to_market_ratio
            price_sources["路線価"] = rosenka_price_per_sqm
            price_sources["路線価→市場推定"] = market_from_rosenka
            weighted_prices.append((market_from_rosenka, self.config.weight_rosenka))

        # 2. 公示地価ベース
        if koji_chika_price_per_sqm is not None and koji_chika_price_per_sqm > 0:
            market_from_koji = koji_chika_price_per_sqm * self.config.koji_chika_market_adjustment
            price_sources["公示地価"] = koji_chika_price_per_sqm
            price_sources["公示地価→市場推定"] = market_from_koji
            weighted_prices.append((market_from_koji, self.config.weight_koji_chika))

        # 3. 国土交通省取引事例
        if gov_transaction_price_per_sqm is not None and gov_transaction_price_per_sqm > 0:
            price_sources["国交省取引事例"] = gov_transaction_price_per_sqm
            weighted_prices.append((gov_transaction_price_per_sqm, self.config.weight_gov_transaction))

        # 4. ポータルサイト・ハウスマーケットDB（類似物件から算出）
        if comparables:
            comparable_prices = []
            for comp in comparables:
                adj_price = comp.adjusted_price_per_sqm
                if adj_price is not None and adj_price > 0:
                    comparable_prices.append(adj_price)

            if comparable_prices:
                # 類似物件の中央値を採用（外れ値の影響を軽減）
                comparable_prices.sort()
                n = len(comparable_prices)
                if n % 2 == 0:
                    median_price = (comparable_prices[n // 2 - 1] + comparable_prices[n // 2]) / 2
                else:
                    median_price = comparable_prices[n // 2]

                price_sources["類似物件中央値"] = median_price
                # ポータル + ハウスマーケットDBの合算ウェイト
                combined_weight = self.config.weight_portal_data + self.config.weight_house_market_db
                weighted_prices.append((median_price, combined_weight))

        # 5. エリア市場データ
        if market_data and market_data.avg_price_per_sqm:
            price_sources["エリア平均"] = market_data.avg_price_per_sqm
            # エリア平均は参考値として低めのウェイトで加算
            if not weighted_prices:
                weighted_prices.append((market_data.avg_price_per_sqm, 1.0))

        # 加重平均で基準㎡単価を算出
        if not weighted_prices:
            return LandAssessmentDetail(
                price_sources=price_sources,
            )

        total_weight = sum(w for _, w in weighted_prices)
        base_price = sum(p * w for p, w in weighted_prices) / total_weight

        # 補正の適用
        shape_adj = self._shape_adjustments.get(land.land_shape, 0.0)
        facing_adj = self._facing_adjustments.get(land.facing, 0.0)
        road_width_adj = self._calc_road_width_adjustment(land.road_width_m)
        market_trend_adj = self._calc_market_trend_adjustment(market_data)

        total_adj = shape_adj + facing_adj + road_width_adj + market_trend_adj
        effective_area = land.effective_area_sqm
        assessed_price = int(base_price * (1 + total_adj) * effective_area)

        return LandAssessmentDetail(
            base_price_per_sqm=base_price,
            effective_area_sqm=effective_area,
            shape_adjustment=shape_adj,
            facing_adjustment=facing_adj,
            road_width_adjustment=road_width_adj,
            market_trend_adjustment=market_trend_adj,
            total_adjustment=total_adj,
            assessed_price_yen=assessed_price,
            price_sources=price_sources,
        )

    def _calc_road_width_adjustment(self, road_width_m: float | None) -> float:
        """前面道路幅員による補正"""
        if road_width_m is None:
            return 0.0
        if road_width_m >= 6.0:
            return 0.03    # 6m以上：プラス補正
        elif road_width_m >= 4.0:
            return 0.0     # 4-6m：標準
        elif road_width_m >= 3.0:
            return -0.05   # 3-4m：やや狭い
        else:
            return -0.10   # 3m未満：狭隘道路

    def _calc_market_trend_adjustment(self, market_data: AreaMarketData | None) -> float:
        """市場動向補正"""
        if market_data is None or market_data.price_trend_pct is None:
            return 0.0
        # 価格トレンド（前年比%）をそのまま補正率として使用（上限±10%）
        trend = market_data.price_trend_pct / 100.0
        return max(-0.10, min(0.10, trend))
