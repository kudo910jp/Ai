"""
市場動向分析エンジン

ポータルサイトの掲載情報追跡データから市場動向を分析する。
物件の出現・消滅パターン、価格変更履歴、売出期間（DOM）等から
エリアの市場温度を判定し、適正価格の推定に活用する。

【HOUSE Marketアプリデザイン参照】
- 販売された住宅数（四半期バーチャート）
- 平均販売価格（ラインチャート + 前年比%）
- 価格ウォッチ推定市場価格（1年/3年/5年/10年タブ切替）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from price_watch.config import MarketAnalysisConfig
from price_watch.models.market import (
    PortalListing,
    ListingStatus,
    AreaMarketData,
    MarketComparable,
)


@dataclass
class PriceHistoryPoint:
    """価格推移データポイント"""
    period: str          # "2025Q1", "2025-01" 等
    avg_price: float     # 平均価格
    median_price: float  # 中央値
    count: int           # データ件数
    yoy_change_pct: float | None = None  # 前年同期比（%）


@dataclass
class MarketTrendReport:
    """
    市場動向レポート

    HOUSE Marketアプリの市場トレンド画面に対応するデータ構造。
    """
    prefecture: str
    city: str
    district: str = ""
    analysis_date: date = field(default_factory=date.today)

    # 推定市場価格（価格ウォッチ推定市場価格）
    estimated_market_price_yen: int = 0
    price_change_1y_pct: float | None = None   # 1年間の変動率
    price_change_3y_pct: float | None = None   # 3年間の変動率
    price_change_5y_pct: float | None = None   # 5年間の変動率

    # 四半期ごとの価格推移
    quarterly_price_history: list[PriceHistoryPoint] = field(default_factory=list)

    # 販売件数推移
    quarterly_sales_volume: list[dict] = field(default_factory=list)
    # [{quarter: "2025Q1", count: 45, yoy_change_pct: 5.2}, ...]

    # 市場温度
    market_temperature: str = ""
    avg_days_on_market: float | None = None
    active_listing_count: int = 0
    monthly_absorption_count: int = 0


class MarketAnalyzer:
    """市場動向分析エンジン"""

    def __init__(self, config: MarketAnalysisConfig | None = None):
        self.config = config or MarketAnalysisConfig()

    def analyze_listings(
        self,
        listings: list[PortalListing],
        prefecture: str,
        city: str,
        district: str = "",
    ) -> MarketTrendReport:
        """
        掲載物件リストからエリアの市場動向を分析する
        """
        report = MarketTrendReport(
            prefecture=prefecture,
            city=city,
            district=district,
        )

        if not listings:
            report.market_temperature = "データ不足"
            return report

        # アクティブ物件数
        active = [l for l in listings if l.status == ListingStatus.ACTIVE]
        report.active_listing_count = len(active)

        # 売却済み物件の分析
        sold = [l for l in listings if l.status == ListingStatus.REMOVED_SOLD]

        # 平均掲載日数
        dom_values = [l.days_on_market for l in listings if l.days_on_market is not None]
        if dom_values:
            report.avg_days_on_market = sum(dom_values) / len(dom_values)

        # 四半期ごとの集計
        report.quarterly_price_history = self._calc_quarterly_prices(listings)
        report.quarterly_sales_volume = self._calc_quarterly_volume(sold)

        # 前年比の計算
        if len(report.quarterly_price_history) >= 5:
            current = report.quarterly_price_history[-1]
            prev_year = report.quarterly_price_history[-5]  # 4四半期前
            if prev_year.avg_price > 0:
                report.price_change_1y_pct = (
                    (current.avg_price - prev_year.avg_price) / prev_year.avg_price * 100
                )

        # 推定市場価格（アクティブ物件の中央値に値引率を適用）
        if active:
            prices = sorted([l.asking_price_yen for l in active if l.asking_price_yen > 0])
            if prices:
                n = len(prices)
                median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) // 2
                report.estimated_market_price_yen = int(
                    median * (1 - self.config.avg_negotiation_discount)
                )

        # 月間消化数と市場温度
        if sold:
            # 直近6ヶ月の売却数から月間消化数を推定
            six_months_ago = date.today() - timedelta(days=180)
            recent_sold = [
                l for l in sold
                if l.removed_date and l.removed_date >= six_months_ago
            ]
            report.monthly_absorption_count = max(1, len(recent_sold) // 6)

        # 在庫消化率（月）
        if report.monthly_absorption_count > 0 and report.active_listing_count > 0:
            absorption_rate = report.active_listing_count / report.monthly_absorption_count
            if absorption_rate < 6:
                report.market_temperature = "売り手市場"
            elif absorption_rate <= 9:
                report.market_temperature = "均衡市場"
            else:
                report.market_temperature = "買い手市場"
        else:
            report.market_temperature = "判定不能"

        return report

    def estimate_transaction_price(
        self,
        asking_price: int,
        days_on_market: int | None = None,
    ) -> int:
        """売出価格と掲載日数から推定成約価格を算出"""
        if days_on_market is None:
            discount = self.config.avg_negotiation_discount
        else:
            # DOM別の調整係数を適用
            rate = 1.0
            for dom_threshold, adj_rate in sorted(self.config.dom_adjustment.items()):
                if days_on_market <= dom_threshold:
                    rate = adj_rate
                    break
            else:
                rate = min(self.config.dom_adjustment.values())
            discount = 1.0 - rate

        return int(asking_price * (1 - discount))

    def find_comparables(
        self,
        target_price_per_sqm: float,
        target_area_sqm: float,
        listings: list[PortalListing],
        max_count: int = 10,
    ) -> list[MarketComparable]:
        """
        対象物件に類似する物件を抽出する

        類似度は面積差・価格差・築年数差等から総合的に算出。
        """
        comparables: list[MarketComparable] = []

        for listing in listings:
            if listing.asking_price_yen <= 0:
                continue

            land_area = listing.land_area_sqm or 0
            if land_area <= 0:
                continue

            listing_price_per_sqm = listing.asking_price_yen / land_area

            # 面積の類似度（±50%以内を対象）
            area_ratio = land_area / target_area_sqm if target_area_sqm > 0 else 0
            if area_ratio < 0.5 or area_ratio > 2.0:
                continue
            area_sim = 1.0 - abs(1.0 - area_ratio)

            # 価格帯の類似度
            price_ratio = listing_price_per_sqm / target_price_per_sqm if target_price_per_sqm > 0 else 0
            if price_ratio < 0.3 or price_ratio > 3.0:
                continue
            price_sim = 1.0 - min(1.0, abs(1.0 - price_ratio))

            # 総合類似度
            similarity = area_sim * 0.5 + price_sim * 0.5

            adjustments = {}
            if area_ratio != 1.0:
                adjustments["面積差補正"] = (1.0 - area_ratio) * 0.1

            comparables.append(MarketComparable(
                listing=listing,
                similarity_score=similarity,
                adjustments=adjustments,
            ))

        # 類似度順にソートして上位を返す
        comparables.sort(key=lambda c: c.similarity_score, reverse=True)
        return comparables[:max_count]

    def _calc_quarterly_prices(
        self, listings: list[PortalListing]
    ) -> list[PriceHistoryPoint]:
        """四半期ごとの価格推移を集計"""
        quarterly: dict[str, list[int]] = {}

        for listing in listings:
            if not listing.first_seen_date or listing.asking_price_yen <= 0:
                continue
            d = listing.first_seen_date
            quarter = f"{d.year}Q{(d.month - 1) // 3 + 1}"
            quarterly.setdefault(quarter, []).append(listing.asking_price_yen)

        result = []
        for quarter in sorted(quarterly.keys()):
            prices = sorted(quarterly[quarter])
            n = len(prices)
            avg = sum(prices) / n
            median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
            result.append(PriceHistoryPoint(
                period=quarter,
                avg_price=avg,
                median_price=median,
                count=n,
            ))

        # 前年同期比を計算
        for i, point in enumerate(result):
            # 4四半期前のデータを探す
            if i >= 4:
                prev = result[i - 4]
                if prev.avg_price > 0:
                    point.yoy_change_pct = (
                        (point.avg_price - prev.avg_price) / prev.avg_price * 100
                    )

        return result

    def _calc_quarterly_volume(
        self, sold_listings: list[PortalListing]
    ) -> list[dict]:
        """四半期ごとの販売件数を集計"""
        quarterly: dict[str, int] = {}

        for listing in sold_listings:
            d = listing.removed_date or listing.last_seen_date
            if d is None:
                continue
            quarter = f"{d.year}Q{(d.month - 1) // 3 + 1}"
            quarterly[quarter] = quarterly.get(quarter, 0) + 1

        result = []
        sorted_quarters = sorted(quarterly.keys())
        for i, quarter in enumerate(sorted_quarters):
            count = quarterly[quarter]
            yoy = None
            if i >= 4:
                prev_count = quarterly.get(sorted_quarters[i - 4], 0)
                if prev_count > 0:
                    yoy = (count - prev_count) / prev_count * 100
            result.append({
                "quarter": quarter,
                "count": count,
                "yoy_change_pct": yoy,
            })

        return result
