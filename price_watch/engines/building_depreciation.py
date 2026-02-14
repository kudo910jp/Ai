"""
建物減価償却エンジン（3層モデル）

建物を3つのコンポーネント（基礎・躯体、設備・水回り、内装・仕上げ）に
分離し、それぞれ異なる耐用年数と償却率で評価する。
リフォーム済みコンポーネントはリフォーム時点から再度償却を開始する。

【従来手法との違い】
従来: 建物全体を法定耐用年数で一律に減価償却
  → 築30年の木造は残存価値ほぼゼロ
本モデル: コンポーネント別に実効築年数で償却
  → 築30年でも水回り・内装リフォーム済みなら適正な残存価値を算出
"""

from __future__ import annotations

import math

from price_watch.config import (
    DepreciationConfig,
    StructureType,
    STRUCTURE_USEFUL_LIFE,
)
from price_watch.models.property import BuildingInfo, BuildingComponent
from price_watch.models.assessment import BuildingAssessmentDetail


# 構造種別ごとの再調達原価（㎡単価）目安
# 実務では地域差があるが、全国平均値をベースとする
RECONSTRUCTION_COST_PER_SQM: dict[StructureType, float] = {
    StructureType.WOOD: 180_000,
    StructureType.LIGHT_STEEL: 210_000,
    StructureType.STEEL: 250_000,
    StructureType.RC: 300_000,
    StructureType.SRC: 330_000,
}


class BuildingDepreciationEngine:
    """建物減価償却エンジン（3層モデル）"""

    def __init__(self, config: DepreciationConfig | None = None):
        self.config = config or DepreciationConfig()

    def evaluate(
        self,
        building: BuildingInfo,
        market_adjustment: float = 0.0,
        custom_reconstruction_cost: float | None = None,
    ) -> BuildingAssessmentDetail:
        """
        建物を3層モデルで評価する

        Args:
            building: 建物情報
            market_adjustment: 市場補正率（例: 人気エリアなら+0.05）
            custom_reconstruction_cost: カスタム再調達原価㎡単価（指定時は標準値を上書き）
        """
        # 再調達原価
        cost_per_sqm = custom_reconstruction_cost or RECONSTRUCTION_COST_PER_SQM.get(
            building.structure_type, 180_000
        )
        gross_cost = int(cost_per_sqm * building.total_floor_area_sqm)

        # 構造種別の耐用年数テーブル
        useful_life = STRUCTURE_USEFUL_LIFE.get(building.structure_type, {
            "legal": 22, "foundation": 35, "equipment": 20, "interior": 12,
        })

        # 各コンポーネントの評価
        foundation = self._evaluate_component(
            gross_cost=gross_cost,
            ratio=self.config.foundation_ratio,
            residual=self.config.foundation_residual,
            useful_life_years=useful_life["foundation"],
            effective_age=building.effective_age_for(BuildingComponent.FOUNDATION),
        )

        equipment = self._evaluate_component(
            gross_cost=gross_cost,
            ratio=self.config.equipment_ratio,
            residual=self.config.equipment_residual,
            useful_life_years=useful_life["equipment"],
            effective_age=building.effective_age_for(BuildingComponent.EQUIPMENT),
        )

        interior = self._evaluate_component(
            gross_cost=gross_cost,
            ratio=self.config.interior_ratio,
            residual=self.config.interior_residual,
            useful_life_years=useful_life["interior"],
            effective_age=building.effective_age_for(BuildingComponent.INTERIOR),
        )

        # 建物残存価値合計
        total_remaining = foundation["value"] + equipment["value"] + interior["value"]

        # 市場補正を適用した最終査定額
        assessed_price = int(total_remaining * (1 + market_adjustment))

        return BuildingAssessmentDetail(
            reconstruction_cost_per_sqm=cost_per_sqm,
            total_floor_area_sqm=building.total_floor_area_sqm,
            gross_reconstruction_cost=gross_cost,
            foundation_value_yen=foundation["value"],
            foundation_depreciation_rate=foundation["depreciation_rate"],
            foundation_effective_age=foundation["effective_age"],
            equipment_value_yen=equipment["value"],
            equipment_depreciation_rate=equipment["depreciation_rate"],
            equipment_effective_age=equipment["effective_age"],
            interior_value_yen=interior["value"],
            interior_depreciation_rate=interior["depreciation_rate"],
            interior_effective_age=interior["effective_age"],
            market_adjustment=market_adjustment,
            assessed_price_yen=assessed_price,
        )

    def _evaluate_component(
        self,
        gross_cost: int,
        ratio: float,
        residual: float,
        useful_life_years: float,
        effective_age: float,
    ) -> dict:
        """
        コンポーネント単体の減価償却を計算

        定率法ベースの償却カーブを使用。
        完全に耐用年数を超過しても残存価値率分は残る。
        """
        component_cost = gross_cost * ratio

        if useful_life_years <= 0:
            depreciation_rate = 1.0 - residual
        else:
            # 年数経過率
            age_ratio = min(effective_age / useful_life_years, 1.0)
            # S字カーブ的な償却（初期は緩やか→中盤加速→終盤は残存価値に収束）
            depreciation_rate = (1.0 - residual) * (1.0 - math.exp(-3.0 * age_ratio))

        remaining_value = int(component_cost * (1.0 - depreciation_rate))

        return {
            "value": remaining_value,
            "depreciation_rate": depreciation_rate,
            "effective_age": effective_age,
        }
