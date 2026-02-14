"""
Stage 2 現地査定エンジン

Stage 1の自動査定結果をベースに、現地調査の情報を加えて
査定精度を向上させる。査定員が現地で確認した状態・特記事項等を
反映し、最終的な査定結果を生成する。

【Stage 2 で追加される情報】
- 建物の実際の劣化状態（外壁・屋根・水回り等）
- 周辺環境の評価（騒音・日照・眺望等）
- 接道状況の実地確認
- リフォーム状態の詳細確認
- 不動産会社の市場感覚
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from price_watch.models.property import PropertyInfo
from price_watch.models.assessment import (
    AssessmentResult,
    AssessmentStage,
    ConfidenceScore,
)


@dataclass
class OnsiteInspection:
    """現地査定情報"""
    inspector_name: str = ""
    inspection_date: datetime = field(default_factory=datetime.now)

    # 建物状態評価（1-5、5が最良）
    exterior_condition: int = 3          # 外壁・屋根
    interior_condition: int = 3          # 内装
    equipment_condition: int = 3         # 設備・水回り
    foundation_condition: int = 3        # 基礎・構造

    # 周辺環境評価（1-5、5が最良）
    noise_level: int = 3                 # 騒音（5=静か）
    sunlight: int = 3                    # 日照
    view_quality: int = 3                # 眺望
    neighborhood: int = 3                # 周辺環境総合

    # 接道・敷地
    actual_road_width_m: float | None = None    # 実測前面道路幅員
    actual_frontage_m: float | None = None      # 実測間口

    # 特記事項
    positive_factors: list[str] = field(default_factory=list)
    # 例: ["角地で日当たり良好", "駅徒歩5分", "閑静な住宅街"]
    negative_factors: list[str] = field(default_factory=list)
    # 例: ["北側斜線の影響あり", "擁壁あり要補修", "前面道路が狭い"]

    appraiser_comment: str = ""
    recommended_price_yen: int | None = None    # 査定員の推奨価格

    @property
    def building_condition_score(self) -> float:
        """建物状態の総合スコア（0-1）"""
        total = (
            self.exterior_condition
            + self.interior_condition
            + self.equipment_condition
            + self.foundation_condition
        )
        return total / 20.0  # 最大20点を0-1に正規化

    @property
    def environment_score(self) -> float:
        """周辺環境の総合スコア（0-1）"""
        total = (
            self.noise_level
            + self.sunlight
            + self.view_quality
            + self.neighborhood
        )
        return total / 20.0


class Stage2OnsiteAssessment:
    """Stage 2 現地査定エンジン"""

    def refine(
        self,
        stage1_result: AssessmentResult,
        inspection: OnsiteInspection,
        property_info: PropertyInfo | None = None,
    ) -> AssessmentResult:
        """
        Stage 1 の結果を現地査定情報で補正する

        Stage 1 の価格をベースに、現地で確認した状態に応じて
        上方・下方に補正する。
        """
        result = AssessmentResult(
            stage=AssessmentStage.STAGE_2_ONSITE,
            assessment_date=inspection.inspection_date,
        )

        # Stage 1 の基本情報を引き継ぐ
        result.land_assessment = stage1_result.land_assessment
        result.building_assessment = stage1_result.building_assessment
        result.comparable_count = stage1_result.comparable_count

        base_price = stage1_result.total_assessed_price_yen

        # 建物状態による補正（±15%）
        building_adj = self._building_condition_adjustment(inspection)

        # 環境による補正（±10%）
        env_adj = self._environment_adjustment(inspection)

        # 特記事項による補正
        factor_adj = self._factor_adjustment(inspection)

        total_adj = building_adj + env_adj + factor_adj
        adjusted_price = int(base_price * (1 + total_adj))

        # 査定員推奨価格がある場合は加重平均
        if inspection.recommended_price_yen and inspection.recommended_price_yen > 0:
            # 計算値60% + 査定員推奨40%
            adjusted_price = int(
                adjusted_price * 0.6 + inspection.recommended_price_yen * 0.4
            )

        result.total_assessed_price_yen = adjusted_price

        # 価格レンジ（Stage 2 は精度が高いため幅を狭くする）
        result.price_range_low_yen = int(adjusted_price * 0.95)
        result.price_range_high_yen = int(adjusted_price * 1.05)
        result.recommended_listing_price_yen = int(adjusted_price * 1.03)

        # 信頼度（Stage 2 はデータが充実しているため高め）
        result.confidence = self._calc_confidence(stage1_result.confidence, inspection)

        # 市場コンテキスト引き継ぎ
        result.market_temperature = stage1_result.market_temperature
        result.avg_days_to_sell = stage1_result.avg_days_to_sell

        # 査定メモ
        result.assessment_notes = self._generate_notes(
            stage1_result, inspection, total_adj,
        )
        result.appraiser_comments = inspection.appraiser_comment

        return result

    def _building_condition_adjustment(self, inspection: OnsiteInspection) -> float:
        """建物状態による補正率"""
        score = inspection.building_condition_score
        # スコア0.6（標準）を基準に補正
        return (score - 0.6) * 0.25  # 最大±10%

    def _environment_adjustment(self, inspection: OnsiteInspection) -> float:
        """周辺環境による補正率"""
        score = inspection.environment_score
        return (score - 0.6) * 0.15  # 最大±6%

    def _factor_adjustment(self, inspection: OnsiteInspection) -> float:
        """特記事項による補正率"""
        adj = 0.0
        adj += len(inspection.positive_factors) * 0.01   # プラス要因1件あたり+1%
        adj -= len(inspection.negative_factors) * 0.015  # マイナス要因1件あたり-1.5%
        return max(-0.10, min(0.10, adj))  # 上限±10%

    def _calc_confidence(
        self, stage1_confidence: ConfidenceScore, inspection: OnsiteInspection,
    ) -> ConfidenceScore:
        """Stage 2 の信頼度スコアを算出"""
        # Stage 1 のスコアをベースに現地査定分を加算
        base = stage1_confidence.overall_score

        # 現地査定実施による信頼度向上（+0.15-0.25）
        onsite_boost = 0.15
        if inspection.appraiser_comment:
            onsite_boost += 0.05
        if inspection.recommended_price_yen:
            onsite_boost += 0.05

        overall = min(1.0, base + onsite_boost)

        sources = list(stage1_confidence.data_sources_used)
        sources.append("現地査定")

        return ConfidenceScore(
            overall_score=overall,
            data_source_score=min(1.0, stage1_confidence.data_source_score + 0.2),
            comparable_score=stage1_confidence.comparable_score,
            market_liquidity_score=stage1_confidence.market_liquidity_score,
            data_freshness_score=min(1.0, stage1_confidence.data_freshness_score + 0.15),
            data_sources_used=sources,
            comparable_count=stage1_confidence.comparable_count,
            notes=[],
        )

    def _generate_notes(
        self,
        stage1: AssessmentResult,
        inspection: OnsiteInspection,
        total_adj: float,
    ) -> list[str]:
        """査定メモ"""
        notes = [f"Stage 1 査定額からの補正率: {total_adj:+.1%}"]

        if inspection.positive_factors:
            notes.append("【プラス要因】" + "、".join(inspection.positive_factors))
        if inspection.negative_factors:
            notes.append("【マイナス要因】" + "、".join(inspection.negative_factors))

        if inspection.building_condition_score >= 0.8:
            notes.append("建物状態は良好です。")
        elif inspection.building_condition_score <= 0.4:
            notes.append("建物の劣化が進んでいます。修繕費用を考慮した価格設定を推奨します。")

        return notes
