"""
Stage 1 自動査定エンジン

住所・面積・築年数・構造等の基本情報から自動で査定を行う。
ユーザーが物件情報を入力するだけで即座に査定結果を返す。

【処理フロー】
1. 土地評価エンジンで土地価格を算出
2. 建物減価償却エンジンで建物残存価値を算出
3. 合計金額、価格レンジ、信頼度スコアを統合
4. 査定レポートを生成
"""

from __future__ import annotations

from datetime import datetime

from price_watch.config import (
    LandValuationConfig,
    DepreciationConfig,
    MarketAnalysisConfig,
    ConfidenceConfig,
    DataSourceType,
)
from price_watch.models.property import PropertyInfo
from price_watch.models.market import AreaMarketData, MarketComparable
from price_watch.models.assessment import (
    AssessmentResult,
    AssessmentStage,
    ConfidenceScore,
)
from price_watch.engines.land_valuation import LandValuationEngine
from price_watch.engines.building_depreciation import BuildingDepreciationEngine


class Stage1AutoAssessment:
    """Stage 1 自動査定エンジン"""

    def __init__(
        self,
        land_config: LandValuationConfig | None = None,
        depreciation_config: DepreciationConfig | None = None,
        market_config: MarketAnalysisConfig | None = None,
        confidence_config: ConfidenceConfig | None = None,
    ):
        self.land_engine = LandValuationEngine(land_config)
        self.building_engine = BuildingDepreciationEngine(depreciation_config)
        self.market_config = market_config or MarketAnalysisConfig()
        self.confidence_config = confidence_config or ConfidenceConfig()

    def assess(
        self,
        property_info: PropertyInfo,
        market_data: AreaMarketData | None = None,
        comparables: list[MarketComparable] | None = None,
        rosenka_price_per_sqm: float | None = None,
        koji_chika_price_per_sqm: float | None = None,
        gov_transaction_price_per_sqm: float | None = None,
    ) -> AssessmentResult:
        """
        Stage 1 自動査定を実行する

        Args:
            property_info: 物件情報
            market_data: エリア市場データ（あれば精度向上）
            comparables: 類似物件データ（あれば精度向上）
            rosenka_price_per_sqm: 路線価㎡単価
            koji_chika_price_per_sqm: 公示地価㎡単価
            gov_transaction_price_per_sqm: 国交省取引事例㎡単価
        """
        result = AssessmentResult(
            stage=AssessmentStage.STAGE_1_AUTO,
            assessment_date=datetime.now(),
        )

        # 1. 土地評価
        land_detail = self.land_engine.evaluate(
            land=property_info.land,
            market_data=market_data,
            comparables=comparables,
            rosenka_price_per_sqm=rosenka_price_per_sqm,
            koji_chika_price_per_sqm=koji_chika_price_per_sqm,
            gov_transaction_price_per_sqm=gov_transaction_price_per_sqm,
        )
        result.land_assessment = land_detail

        # 2. 建物評価（建物がある場合）
        building_detail = None
        if property_info.building:
            market_adj = 0.0
            if market_data and market_data.price_trend_pct is not None:
                market_adj = min(0.10, max(-0.10, market_data.price_trend_pct / 100))

            building_detail = self.building_engine.evaluate(
                building=property_info.building,
                market_adjustment=market_adj,
            )
            result.building_assessment = building_detail

        # 3. 合計査定価格
        land_price = land_detail.assessed_price_yen
        building_price = building_detail.assessed_price_yen if building_detail else 0
        total = land_price + building_price
        result.total_assessed_price_yen = total

        # 4. 価格レンジ（信頼度に応じて幅を調整）
        confidence = self._calc_confidence(
            market_data=market_data,
            comparables=comparables,
            has_rosenka=rosenka_price_per_sqm is not None,
            has_koji_chika=koji_chika_price_per_sqm is not None,
            has_gov_data=gov_transaction_price_per_sqm is not None,
        )
        result.confidence = confidence

        # 信頼度が低いほど価格レンジを広くする
        range_factor = self._range_factor(confidence.overall_score)
        result.price_range_low_yen = int(total * (1 - range_factor))
        result.price_range_high_yen = int(total * (1 + range_factor))

        # 推奨売出価格（査定額のやや上に設定、交渉余地を確保）
        result.recommended_listing_price_yen = int(total * 1.05)

        # 5. 市場コンテキスト
        if market_data:
            result.market_temperature = market_data.market_temperature
            if market_data.avg_days_on_market:
                result.avg_days_to_sell = int(market_data.avg_days_on_market)

        if comparables:
            result.comparable_count = len(comparables)

        # 6. 査定メモ
        result.assessment_notes = self._generate_notes(
            property_info, land_detail, building_detail, market_data,
        )

        return result

    def _calc_confidence(
        self,
        market_data: AreaMarketData | None,
        comparables: list[MarketComparable] | None,
        has_rosenka: bool,
        has_koji_chika: bool,
        has_gov_data: bool,
    ) -> ConfidenceScore:
        """信頼度スコアを算出"""
        conf = self.confidence_config

        # データソーススコア（利用可能なソース数に応じて）
        source_count = sum([has_rosenka, has_koji_chika, has_gov_data])
        sources_used = []
        if has_rosenka:
            sources_used.append(DataSourceType.ROSENKA.value)
        if has_koji_chika:
            sources_used.append(DataSourceType.KOJI_CHIKA.value)
        if has_gov_data:
            sources_used.append(DataSourceType.GOVERNMENT_TRANSACTION.value)

        if comparables:
            source_count += 1
            sources_used.append(DataSourceType.PORTAL_SITE.value)
        if market_data:
            source_count += 1
            sources_used.append(DataSourceType.HOUSE_MARKET_DB.value)

        data_source_score = min(1.0, source_count / 4)  # 4ソース以上で最高

        # 類似物件スコア
        comp_count = len(comparables) if comparables else 0
        comparable_score = min(1.0, comp_count / 10)  # 10件以上で最高

        # 市場流動性スコア
        liquidity_score = 0.0
        if market_data:
            liquidity_score = market_data.data_quality_score

        # データ鮮度スコア（Stage1ではデータ有無で簡易判定）
        freshness_score = 0.5  # ベースライン
        if market_data and market_data.active_listing_count > 5:
            freshness_score = 0.8
        if comparables and len(comparables) >= 3:
            freshness_score = min(1.0, freshness_score + 0.2)

        # 総合スコア
        overall = (
            data_source_score * conf.weight_data_source_count
            + comparable_score * conf.weight_comparable_count
            + liquidity_score * conf.weight_market_liquidity
            + freshness_score * conf.weight_data_freshness
        )

        notes = []
        if source_count <= 1:
            notes.append("データソースが限定的です。複数ソースでの検証を推奨します。")
        if comp_count < 3:
            notes.append("類似物件データが少ないため、価格レンジが広くなっています。")
        if market_data is None:
            notes.append("エリア市場データがありません。市場動向を反映できていません。")

        return ConfidenceScore(
            overall_score=overall,
            data_source_score=data_source_score,
            comparable_score=comparable_score,
            market_liquidity_score=liquidity_score,
            data_freshness_score=freshness_score,
            data_sources_used=sources_used,
            comparable_count=comp_count,
            notes=notes,
        )

    def _range_factor(self, confidence_score: float) -> float:
        """信頼度スコアに応じた価格レンジ幅を返す"""
        if confidence_score >= 0.80:
            return 0.05  # ±5%
        elif confidence_score >= 0.60:
            return 0.10  # ±10%
        elif confidence_score >= 0.40:
            return 0.15  # ±15%
        else:
            return 0.20  # ±20%

    def _generate_notes(
        self,
        prop: PropertyInfo,
        land_detail,
        building_detail,
        market_data: AreaMarketData | None,
    ) -> list[str]:
        """査定メモを生成"""
        notes = []

        if prop.is_land_only:
            notes.append("土地のみの査定です。")
        else:
            notes.append(f"土地＋建物の総合査定です。")

        if land_detail.assessed_price_yen == 0:
            notes.append("⚠ 土地価格の算出に十分なデータがありませんでした。")

        if building_detail:
            dep_rate = building_detail.overall_depreciation_rate
            if dep_rate > 0.80:
                notes.append(
                    "建物の償却率が高く、建物価値は限定的です。"
                    "土地値での売却を検討ください。"
                )

        if market_data:
            temp = market_data.market_temperature
            if temp == "売り手市場":
                notes.append("現在は売り手市場です。売出価格を強気に設定できる可能性があります。")
            elif temp == "買い手市場":
                notes.append("現在は買い手市場です。早期売却には価格面での柔軟性が必要です。")

        return notes
