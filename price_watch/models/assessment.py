"""
査定結果モデル

Stage 1（自動査定）とStage 2（現地査定）の結果を統一的に管理する。
査定金額だけでなく、信頼度・根拠・判断材料を包括的に提供する。

【チームの設計哲学】
「査定金額 = 正当な金額」ではない。市場が決める最終価格は誰にも予測できない。
したがって、金額の精度よりも「どのようにすべきかという判断ができる材料」を
提供することを最優先とする。信頼度スコア、価格レンジ、根拠の透明性が
ユーザーにとっての真の価値となる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AssessmentStage(Enum):
    """査定段階"""
    STAGE_1_AUTO = "Stage1_自動査定"
    STAGE_2_ONSITE = "Stage2_現地査定"


class ConfidenceRank(Enum):
    """信頼度ランク"""
    A = "A: 高信頼"
    B = "B: 中信頼"
    C = "C: 低信頼"
    D = "D: 参考程度"


@dataclass
class ConfidenceScore:
    """
    信頼度スコア

    査定結果の信頼性を多角的に評価し、ユーザーに判断材料を提供する。
    """
    overall_score: float = 0.0              # 総合スコア（0-1）
    data_source_score: float = 0.0          # データソーススコア
    comparable_score: float = 0.0           # 類似物件データスコア
    market_liquidity_score: float = 0.0     # 市場流動性スコア
    data_freshness_score: float = 0.0       # データ鮮度スコア
    data_sources_used: list[str] = field(default_factory=list)
    comparable_count: int = 0               # 参照した類似物件数
    notes: list[str] = field(default_factory=list)

    @property
    def rank(self) -> ConfidenceRank:
        if self.overall_score >= 0.80:
            return ConfidenceRank.A
        elif self.overall_score >= 0.60:
            return ConfidenceRank.B
        elif self.overall_score >= 0.40:
            return ConfidenceRank.C
        else:
            return ConfidenceRank.D


@dataclass
class LandAssessmentDetail:
    """土地査定詳細"""
    base_price_per_sqm: float = 0.0         # 基準㎡単価
    effective_area_sqm: float = 0.0         # 有効面積
    shape_adjustment: float = 0.0           # 形状補正（率）
    facing_adjustment: float = 0.0          # 接道補正（率）
    road_width_adjustment: float = 0.0      # 前面道路補正（率）
    market_trend_adjustment: float = 0.0    # 市場動向補正（率）
    total_adjustment: float = 0.0           # 合計補正率
    assessed_price_yen: int = 0             # 査定価格
    price_sources: dict = field(default_factory=dict)
    # 各データソースからの価格情報: {"路線価": 250000, "ポータル平均": 310000, ...}

    @property
    def explanation(self) -> str:
        """査定根拠の説明文"""
        lines = [
            f"【土地査定】",
            f"  基準単価: ¥{self.base_price_per_sqm:,.0f}/㎡",
            f"  有効面積: {self.effective_area_sqm:.2f}㎡",
            f"  形状補正: {self.shape_adjustment:+.1%}",
            f"  接道補正: {self.facing_adjustment:+.1%}",
            f"  道路幅員補正: {self.road_width_adjustment:+.1%}",
            f"  市場動向補正: {self.market_trend_adjustment:+.1%}",
            f"  合計補正率: {self.total_adjustment:+.1%}",
            f"  ─────────────",
            f"  土地査定額: ¥{self.assessed_price_yen:,}",
        ]
        if self.price_sources:
            lines.append(f"  参照価格:")
            for src, price in self.price_sources.items():
                lines.append(f"    {src}: ¥{price:,.0f}/㎡")
        return "\n".join(lines)


@dataclass
class BuildingAssessmentDetail:
    """建物査定詳細（3層減価償却モデル）"""
    # 再調達原価
    reconstruction_cost_per_sqm: float = 0.0  # 再調達原価（㎡単価）
    total_floor_area_sqm: float = 0.0
    gross_reconstruction_cost: int = 0         # 再調達原価（総額）

    # コンポーネント別評価
    foundation_value_yen: int = 0              # 基礎・躯体の残存価値
    foundation_depreciation_rate: float = 0.0  # 基礎・躯体の償却率
    foundation_effective_age: float = 0.0      # 基礎・躯体の実効築年数

    equipment_value_yen: int = 0               # 設備・水回りの残存価値
    equipment_depreciation_rate: float = 0.0   # 設備・水回りの償却率
    equipment_effective_age: float = 0.0        # 設備・水回りの実効築年数

    interior_value_yen: int = 0                # 内装の残存価値
    interior_depreciation_rate: float = 0.0    # 内装の償却率
    interior_effective_age: float = 0.0         # 内装の実効築年数

    # 補正
    market_adjustment: float = 0.0             # 市場補正率
    assessed_price_yen: int = 0                # 建物査定額

    @property
    def total_remaining_value(self) -> int:
        return self.foundation_value_yen + self.equipment_value_yen + self.interior_value_yen

    @property
    def overall_depreciation_rate(self) -> float:
        if self.gross_reconstruction_cost == 0:
            return 0.0
        return 1.0 - (self.total_remaining_value / self.gross_reconstruction_cost)

    @property
    def explanation(self) -> str:
        lines = [
            f"【建物査定（3層減価償却モデル）】",
            f"  再調達原価: ¥{self.reconstruction_cost_per_sqm:,.0f}/㎡ × {self.total_floor_area_sqm:.2f}㎡",
            f"           = ¥{self.gross_reconstruction_cost:,}",
            f"",
            f"  ┌ 基礎・躯体（{45}%）",
            f"  │ 実効築年数: {self.foundation_effective_age:.1f}年",
            f"  │ 償却率: {self.foundation_depreciation_rate:.1%}",
            f"  │ 残存価値: ¥{self.foundation_value_yen:,}",
            f"  │",
            f"  ├ 設備・水回り（{30}%）",
            f"  │ 実効築年数: {self.equipment_effective_age:.1f}年",
            f"  │ 償却率: {self.equipment_depreciation_rate:.1%}",
            f"  │ 残存価値: ¥{self.equipment_value_yen:,}",
            f"  │",
            f"  └ 内装・仕上げ（{25}%）",
            f"    実効築年数: {self.interior_effective_age:.1f}年",
            f"    償却率: {self.interior_depreciation_rate:.1%}",
            f"    残存価値: ¥{self.interior_value_yen:,}",
            f"",
            f"  建物残存価値合計: ¥{self.total_remaining_value:,}",
            f"  総合償却率: {self.overall_depreciation_rate:.1%}",
            f"  市場補正: {self.market_adjustment:+.1%}",
            f"  ─────────────",
            f"  建物査定額: ¥{self.assessed_price_yen:,}",
        ]
        return "\n".join(lines)


@dataclass
class AssessmentResult:
    """
    査定結果

    土地・建物の査定詳細、信頼度、価格レンジを包括的に提供する。
    「判断材料の品質」を最重視した設計。
    """
    stage: AssessmentStage
    assessment_date: datetime = field(default_factory=datetime.now)

    # 査定価格
    land_assessment: LandAssessmentDetail | None = None
    building_assessment: BuildingAssessmentDetail | None = None
    total_assessed_price_yen: int = 0

    # 価格レンジ（判断材料として重要）
    price_range_low_yen: int = 0             # 下限価格
    price_range_high_yen: int = 0            # 上限価格
    recommended_listing_price_yen: int = 0   # 推奨売出価格

    # 信頼度
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)

    # 市場コンテキスト
    market_temperature: str = ""             # 市場の温度感
    avg_days_to_sell: int | None = None      # 推定売却期間（日）
    comparable_count: int = 0                # 参照類似物件数

    # 根拠・メモ
    assessment_notes: list[str] = field(default_factory=list)
    appraiser_comments: str = ""             # Stage 2: 査定員コメント

    def generate_report(self) -> str:
        """査定レポートを生成"""
        lines = [
            "=" * 60,
            f"  価格ウォッチ 不動産査定レポート",
            f"  {self.stage.value}",
            f"  査定日: {self.assessment_date.strftime('%Y年%m月%d日')}",
            "=" * 60,
            "",
        ]

        if self.land_assessment:
            lines.append(self.land_assessment.explanation)
            lines.append("")

        if self.building_assessment:
            lines.append(self.building_assessment.explanation)
            lines.append("")

        lines.extend([
            "━" * 60,
            f"  査定価格: ¥{self.total_assessed_price_yen:,}",
            f"  価格レンジ: ¥{self.price_range_low_yen:,} 〜 ¥{self.price_range_high_yen:,}",
            f"  推奨売出価格: ¥{self.recommended_listing_price_yen:,}",
            "━" * 60,
            "",
            f"  信頼度: {self.confidence.rank.value}（スコア: {self.confidence.overall_score:.2f}）",
            f"  参照類似物件数: {self.comparable_count}件",
            f"  市場動向: {self.market_temperature}",
        ])

        if self.avg_days_to_sell:
            lines.append(f"  推定売却期間: 約{self.avg_days_to_sell}日")

        if self.confidence.notes:
            lines.append("")
            lines.append("  【信頼度に関する注記】")
            for note in self.confidence.notes:
                lines.append(f"  ・{note}")

        if self.assessment_notes:
            lines.append("")
            lines.append("  【査定メモ】")
            for note in self.assessment_notes:
                lines.append(f"  ・{note}")

        if self.appraiser_comments:
            lines.append("")
            lines.append("  【査定員コメント】")
            lines.append(f"  {self.appraiser_comments}")

        lines.extend([
            "",
            "=" * 60,
            "  ※本査定は参考価格であり、実際の売買価格を保証するものではありません。",
            "  ※最終的な売買価格は市場動向・交渉等により変動します。",
            "=" * 60,
        ])

        return "\n".join(lines)
