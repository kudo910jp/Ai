"""
価格ウォッチ 査定デモ

実際の使い方を示すサンプルスクリプト。
東京都世田谷区の築15年木造戸建てを例に、
Stage 1 自動査定 → 売却シミュレーションの流れを実行する。
"""

from datetime import date

from price_watch.config import StructureType, PropertyType
from price_watch.models.property import (
    PropertyInfo,
    LandInfo,
    BuildingInfo,
    BuildingComponent,
    RenovationRecord,
    LandShape,
    LandFacing,
)
from price_watch.models.market import AreaMarketData
from price_watch.data_sources.government_data import GovernmentLandPrice
from price_watch.price_watch import PriceWatch


def main():
    # ── 価格ウォッチ初期化 ──
    pw = PriceWatch()

    # ── 公的データの登録（将来はAPI自動取得） ──
    pw.gov_data.register_mock_data(
        "東京都/世田谷区",
        GovernmentLandPrice(
            rosenka_per_sqm=400_000,         # 路線価: 40万/㎡
            koji_chika_per_sqm=520_000,      # 公示地価: 52万/㎡
            gov_transaction_per_sqm=550_000, # 取引事例: 55万/㎡
            reference_year=2025,
        ),
    )

    # ── 物件情報の入力 ──
    property_info = PropertyInfo(
        property_type=PropertyType.DETACHED_HOUSE,
        land=LandInfo(
            area_sqm=120.50,
            address="東京都世田谷区上北沢3丁目",
            prefecture="東京都",
            city="世田谷区",
            district="上北沢",
            zoning="第一種低層住居専用地域",
            building_coverage_ratio=0.50,
            floor_area_ratio=1.00,
            land_shape=LandShape.RECTANGLE,
            facing=LandFacing.SOUTH,
            frontage_m=8.5,
            depth_m=14.2,
            road_width_m=6.0,
        ),
        building=BuildingInfo(
            total_floor_area_sqm=98.50,
            structure_type=StructureType.WOOD,
            built_date=date(2010, 6, 1),
            floors_above=2,
            rooms="3LDK",
            parking=True,
            renovation_records=[
                # 5年前に水回りをフルリフォーム
                RenovationRecord(
                    component=BuildingComponent.EQUIPMENT,
                    renovation_date=date(2020, 8, 1),
                    description="キッチン・浴室・トイレ全面交換",
                    cost_yen=3_500_000,
                ),
            ],
        ),
    )

    # ── エリア市場データ ──
    market_data = AreaMarketData(
        prefecture="東京都",
        city="世田谷区",
        district="上北沢",
        avg_price_per_sqm=580_000,
        median_price_per_sqm=560_000,
        price_trend_pct=2.5,  # 前年比+2.5%
        active_listing_count=45,
        avg_days_on_market=65.0,
        monthly_sold_count=8,
        absorption_rate=5.6,  # 売り手市場
    )

    # ── Stage 1 自動査定の実行 ──
    print("=" * 60)
    print("  Stage 1 自動査定を実行中...")
    print("=" * 60)
    print()
    print(f"物件概要: {property_info.summary}")
    print()

    result = pw.assess_stage1(
        property_info=property_info,
        market_data=market_data,
    )

    # 査定レポート出力
    print(result.generate_report())

    # ── 売却シミュレーション ──
    print()
    print()
    sim_result = pw.simulate_sale(
        sale_price_yen=result.recommended_listing_price_yen,
        mortgage_balance_yen=25_000_000,
        purchase_price_yen=55_000_000,
        purchase_costs_yen=3_000_000,
        is_residence=True,
        ownership_years=15.0,
    )
    print(sim_result.generate_summary())

    # ── 市場動向分析 ──
    print()
    print()
    trend = pw.analyze_market(
        prefecture="東京都",
        city="世田谷区",
        district="上北沢",
    )
    print("━" * 50)
    print("  エリア市場動向")
    print("━" * 50)
    print(f"  市場温度: {trend.market_temperature}")
    print(f"  アクティブ物件数: {trend.active_listing_count}件")
    if trend.avg_days_on_market:
        print(f"  平均掲載日数: {trend.avg_days_on_market:.0f}日")


if __name__ == "__main__":
    main()
