"""
物件データモデル

不動産物件の情報を構造化して保持する。
土地・建物・リフォーム履歴を分離して管理することで、
3層減価償却モデルに対応する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from price_watch.config import StructureType, PropertyType


class BuildingComponent(Enum):
    """建物コンポーネント種別（3層モデル）"""
    FOUNDATION = "基礎・躯体"
    EQUIPMENT = "設備・水回り"
    INTERIOR = "内装・仕上げ"


class LandShape(Enum):
    """土地形状"""
    RECTANGLE = "整形地"
    FLAG = "旗竿地"
    IRREGULAR = "不整形地"
    TRIANGLE = "三角地"
    TRAPEZOID = "台形地"


class LandFacing(Enum):
    """接道方向"""
    SOUTH = "南"
    EAST = "東"
    WEST = "西"
    NORTH = "北"
    SOUTH_EAST = "南東"
    SOUTH_WEST = "南西"
    CORNER = "角地"


@dataclass
class RenovationRecord:
    """
    リフォーム履歴

    建物の各コンポーネントのリフォーム実施記録。
    3層減価償却モデルにおいて、リフォーム実施済みコンポーネントは
    リフォーム時点から再度償却を開始する。
    """
    component: BuildingComponent
    renovation_date: date
    description: str = ""
    cost_yen: int | None = None  # リフォーム費用（把握している場合）

    @property
    def years_since_renovation(self) -> float:
        """リフォームからの経過年数"""
        delta = date.today() - self.renovation_date
        return delta.days / 365.25


@dataclass
class LandInfo:
    """土地情報"""
    area_sqm: float                          # 土地面積（㎡）
    address: str                             # 住所
    prefecture: str = ""                     # 都道府県
    city: str = ""                           # 市区町村
    district: str = ""                       # 町丁目
    zoning: str = ""                         # 用途地域
    building_coverage_ratio: float | None = None  # 建ぺい率
    floor_area_ratio: float | None = None    # 容積率
    land_shape: LandShape = LandShape.RECTANGLE
    facing: LandFacing = LandFacing.SOUTH
    frontage_m: float | None = None          # 間口（m）
    depth_m: float | None = None             # 奥行（m）
    road_width_m: float | None = None        # 前面道路幅員（m）
    is_setback_required: bool = False        # セットバック必要か
    setback_area_sqm: float = 0.0            # セットバック面積（㎡）

    @property
    def effective_area_sqm(self) -> float:
        """有効面積（セットバック控除後）"""
        return self.area_sqm - self.setback_area_sqm


@dataclass
class BuildingInfo:
    """建物情報"""
    total_floor_area_sqm: float              # 延床面積（㎡）
    structure_type: StructureType            # 構造種別
    built_date: date                         # 建築年月
    floors_above: int = 1                    # 地上階数
    floors_below: int = 0                    # 地下階数
    rooms: str = ""                          # 間取り（例: "3LDK"）
    parking: bool = False                    # 駐車場有無
    renovation_records: list[RenovationRecord] = field(default_factory=list)

    @property
    def building_age_years(self) -> float:
        """築年数"""
        delta = date.today() - self.built_date
        return delta.days / 365.25

    def latest_renovation_for(self, component: BuildingComponent) -> RenovationRecord | None:
        """指定コンポーネントの最新リフォーム記録を返す"""
        records = [r for r in self.renovation_records if r.component == component]
        if not records:
            return None
        return max(records, key=lambda r: r.renovation_date)

    def effective_age_for(self, component: BuildingComponent) -> float:
        """
        コンポーネント別の実効築年数

        リフォーム済みの場合はリフォーム時点からの経過年数を返す。
        未リフォームの場合は建物の築年数を返す。
        """
        renovation = self.latest_renovation_for(component)
        if renovation:
            return renovation.years_since_renovation
        return self.building_age_years


@dataclass
class PropertyInfo:
    """
    物件総合情報

    土地と建物を統合した物件情報。
    査定の入力データとして使用される。
    """
    property_type: PropertyType
    land: LandInfo
    building: BuildingInfo | None = None  # 土地のみの場合はNone
    owner_name: str = ""                  # 所有者名（個人情報・非公開）
    registration_number: str = ""         # 不動産識別番号（将来対応）
    notes: str = ""

    @property
    def is_land_only(self) -> bool:
        return self.building is None

    @property
    def summary(self) -> str:
        """物件概要の文字列表現"""
        parts = [
            f"種別: {self.property_type.value}",
            f"所在: {self.land.address}",
            f"土地: {self.land.area_sqm:.2f}㎡",
        ]
        if self.building:
            parts.extend([
                f"建物: {self.building.total_floor_area_sqm:.2f}㎡",
                f"構造: {self.building.structure_type.value}",
                f"築年数: {self.building.building_age_years:.1f}年",
                f"間取り: {self.building.rooms}",
            ])
        return " / ".join(parts)
