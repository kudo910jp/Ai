"""
価格ウォッチ メインファサード

全エンジンを統合し、シンプルなインターフェースで
査定・シミュレーション・市場分析を提供する。

使い方:
    pw = PriceWatch()
    result = pw.assess_stage1(property_info)
    print(result.generate_report())
"""

from __future__ import annotations

from price_watch.config import (
    LandValuationConfig,
    DepreciationConfig,
    MarketAnalysisConfig,
    ConfidenceConfig,
)
from price_watch.models.property import PropertyInfo
from price_watch.models.market import AreaMarketData, MarketComparable, PortalListing
from price_watch.models.assessment import AssessmentResult
from price_watch.engines.stage1_auto import Stage1AutoAssessment
from price_watch.engines.stage2_onsite import Stage2OnsiteAssessment, OnsiteInspection
from price_watch.engines.market_analyzer import MarketAnalyzer, MarketTrendReport
from price_watch.engines.sale_simulation import (
    SaleSimulator,
    SaleSimulationInput,
    SaleSimulationResult,
)
from price_watch.data_sources.government_data import GovernmentDataSource
from price_watch.data_sources.portal_tracker import PortalTracker


class PriceWatch:
    """
    価格ウォッチ メインクラス

    不動産査定に必要な全機能を統合した公開インターフェース。
    """

    def __init__(
        self,
        land_config: LandValuationConfig | None = None,
        depreciation_config: DepreciationConfig | None = None,
        market_config: MarketAnalysisConfig | None = None,
        confidence_config: ConfidenceConfig | None = None,
    ):
        self.stage1 = Stage1AutoAssessment(
            land_config=land_config,
            depreciation_config=depreciation_config,
            market_config=market_config,
            confidence_config=confidence_config,
        )
        self.stage2 = Stage2OnsiteAssessment()
        self.market_analyzer = MarketAnalyzer(market_config)
        self.sale_simulator = SaleSimulator()

        # データソース
        self.gov_data = GovernmentDataSource()
        self.portal_tracker = PortalTracker()

    def assess_stage1(
        self,
        property_info: PropertyInfo,
        market_data: AreaMarketData | None = None,
        comparables: list[MarketComparable] | None = None,
    ) -> AssessmentResult:
        """
        Stage 1 自動査定を実行

        物件情報を入力するだけで自動査定結果を返す。
        公的データソースの参照も自動で行う。
        """
        # 公的データの自動取得
        rosenka = None
        koji_chika = None
        gov_transaction = None

        gov_prices = self.gov_data.fetch_land_price(
            prefecture=property_info.land.prefecture,
            city=property_info.land.city,
            district=property_info.land.district,
        )
        if gov_prices:
            rosenka = gov_prices.rosenka_per_sqm
            koji_chika = gov_prices.koji_chika_per_sqm
            gov_transaction = gov_prices.gov_transaction_per_sqm

        # ポータルデータから類似物件を自動検索
        if comparables is None and self.portal_tracker.is_available():
            portal_listings = self.portal_tracker.get_listings_by_area(
                prefecture=property_info.land.prefecture,
                city=property_info.land.city,
            )
            if portal_listings:
                # 簡易的な㎡単価の推定
                target_price = 0.0
                if rosenka:
                    target_price = rosenka / 0.8
                elif koji_chika:
                    target_price = koji_chika * 1.05

                if target_price > 0:
                    comparables = self.market_analyzer.find_comparables(
                        target_price_per_sqm=target_price,
                        target_area_sqm=property_info.land.area_sqm,
                        listings=portal_listings,
                    )

        return self.stage1.assess(
            property_info=property_info,
            market_data=market_data,
            comparables=comparables,
            rosenka_price_per_sqm=rosenka,
            koji_chika_price_per_sqm=koji_chika,
            gov_transaction_price_per_sqm=gov_transaction,
        )

    def assess_stage2(
        self,
        stage1_result: AssessmentResult,
        inspection: OnsiteInspection,
        property_info: PropertyInfo | None = None,
    ) -> AssessmentResult:
        """
        Stage 2 現地査定を実行

        Stage 1 の結果を現地調査情報で補正する。
        """
        return self.stage2.refine(
            stage1_result=stage1_result,
            inspection=inspection,
            property_info=property_info,
        )

    def analyze_market(
        self,
        prefecture: str,
        city: str,
        district: str = "",
        listings: list[PortalListing] | None = None,
    ) -> MarketTrendReport:
        """
        エリアの市場動向を分析

        HOUSE Marketアプリの市場トレンド画面に対応するデータを生成。
        """
        if listings is None:
            listings = self.portal_tracker.get_listings_by_area(prefecture, city)

        return self.market_analyzer.analyze_listings(
            listings=listings,
            prefecture=prefecture,
            city=city,
            district=district,
        )

    def simulate_sale(
        self,
        sale_price_yen: int,
        mortgage_balance_yen: int = 0,
        purchase_price_yen: int = 0,
        purchase_costs_yen: int = 0,
        is_residence: bool = True,
        ownership_years: float = 0.0,
    ) -> SaleSimulationResult:
        """
        売却シミュレーション

        HOUSE Marketアプリの売却シミュレーション画面に対応。
        """
        return self.sale_simulator.simulate(SaleSimulationInput(
            sale_price_yen=sale_price_yen,
            mortgage_balance_yen=mortgage_balance_yen,
            purchase_price_yen=purchase_price_yen,
            purchase_costs_yen=purchase_costs_yen,
            is_residence=is_residence,
            ownership_years=ownership_years,
        ))
