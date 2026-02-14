"""
売却シミュレーションエンジン

HOUSE Marketアプリの「売却シミュレーション」画面に対応。
売却価格、住宅ローン残高、購入時価格・諸費用等から
総売却益（手取り額）を算出する。

【シミュレーション項目（アプリデザイン参照）】
- 売却価格（想定売出価格）
- 住宅ローン残高
- 購入時価格
- 購入時諸費用
- 居住用 / 非居住用
- 所有期間（5年超 / 5年以下）
→ 総売却益（税引後手取り額）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SaleSimulationInput:
    """売却シミュレーション入力"""
    sale_price_yen: int                   # 想定売却価格
    mortgage_balance_yen: int = 0         # 住宅ローン残高
    purchase_price_yen: int = 0           # 購入時価格
    purchase_costs_yen: int = 0           # 購入時諸費用
    is_residence: bool = True             # 居住用か（マイホーム特例適用可否）
    ownership_years: float = 0.0          # 所有期間（年）


@dataclass
class SaleSimulationResult:
    """
    売却シミュレーション結果

    HOUSE Marketアプリの結果表示に対応:
    - 総売却益
    - 居住ステータス
    - 所有期間区分
    - 各種費用の内訳
    """
    # 入力値の参照
    sale_price_yen: int = 0
    mortgage_balance_yen: int = 0

    # 売却諸費用
    brokerage_fee_yen: int = 0            # 仲介手数料
    stamp_duty_yen: int = 0               # 印紙税
    registration_fee_yen: int = 0         # 登記費用
    other_costs_yen: int = 0              # その他費用
    total_sale_costs_yen: int = 0         # 売却諸費用合計

    # 譲渡所得税
    capital_gain_yen: int = 0             # 譲渡所得
    tax_deduction_yen: int = 0            # 特別控除額
    taxable_gain_yen: int = 0             # 課税譲渡所得
    tax_rate_pct: float = 0.0             # 税率（%）
    tax_amount_yen: int = 0               # 譲渡所得税額
    ownership_category: str = ""          # "長期譲渡（5年超）" or "短期譲渡（5年以下）"
    residence_status: str = ""            # "居住用" or "非居住用"

    # 最終結果
    net_proceeds_yen: int = 0             # 総売却益（手取り額）

    # 内訳表示用
    breakdown: list[dict] = field(default_factory=list)

    def generate_summary(self) -> str:
        """シミュレーション結果サマリー"""
        lines = [
            "━" * 50,
            "  売却シミュレーション結果",
            "━" * 50,
            "",
            f"  売却価格:       ¥{self.sale_price_yen:,}",
            f"  ローン残高:     ¥{self.mortgage_balance_yen:,}",
            f"  売却諸費用:     ¥{self.total_sale_costs_yen:,}",
            f"    内訳:",
            f"      仲介手数料: ¥{self.brokerage_fee_yen:,}",
            f"      印紙税:     ¥{self.stamp_duty_yen:,}",
            f"      登記費用:   ¥{self.registration_fee_yen:,}",
            "",
            f"  譲渡所得:       ¥{self.capital_gain_yen:,}",
            f"  特別控除:       ¥{self.tax_deduction_yen:,}",
            f"  課税譲渡所得:   ¥{self.taxable_gain_yen:,}",
            f"  税率:           {self.tax_rate_pct:.1f}%（{self.ownership_category}）",
            f"  譲渡所得税:     ¥{self.tax_amount_yen:,}",
            "",
            "━" * 50,
            f"  総売却益（手取り額）: ¥{self.net_proceeds_yen:,}",
            "━" * 50,
            f"  居住ステータス: {self.residence_status}",
            f"  所有期間区分:   {self.ownership_category}",
        ]
        return "\n".join(lines)


class SaleSimulator:
    """売却シミュレーションエンジン"""

    def simulate(self, input_data: SaleSimulationInput) -> SaleSimulationResult:
        """売却シミュレーションを実行"""
        result = SaleSimulationResult(
            sale_price_yen=input_data.sale_price_yen,
            mortgage_balance_yen=input_data.mortgage_balance_yen,
        )

        # 1. 売却諸費用の算出
        result.brokerage_fee_yen = self._calc_brokerage_fee(input_data.sale_price_yen)
        result.stamp_duty_yen = self._calc_stamp_duty(input_data.sale_price_yen)
        result.registration_fee_yen = 30_000  # 抵当権抹消登記費用（概算）
        result.other_costs_yen = 50_000       # その他雑費（概算）
        result.total_sale_costs_yen = (
            result.brokerage_fee_yen
            + result.stamp_duty_yen
            + result.registration_fee_yen
            + result.other_costs_yen
        )

        # 2. 譲渡所得の計算
        acquisition_cost = input_data.purchase_price_yen + input_data.purchase_costs_yen
        if acquisition_cost == 0:
            # 取得費不明の場合：売却価格の5%をみなし取得費とする
            acquisition_cost = int(input_data.sale_price_yen * 0.05)

        result.capital_gain_yen = max(
            0,
            input_data.sale_price_yen - acquisition_cost - result.total_sale_costs_yen,
        )

        # 3. 特別控除
        result.residence_status = "居住用" if input_data.is_residence else "非居住用"
        if input_data.is_residence and result.capital_gain_yen > 0:
            # マイホーム特例: 3,000万円特別控除
            result.tax_deduction_yen = min(result.capital_gain_yen, 30_000_000)
        else:
            result.tax_deduction_yen = 0

        result.taxable_gain_yen = max(0, result.capital_gain_yen - result.tax_deduction_yen)

        # 4. 税率（所有期間による区分）
        if input_data.ownership_years > 5:
            result.ownership_category = "長期譲渡（5年超）"
            result.tax_rate_pct = 20.315  # 所得税15.315% + 住民税5%
        else:
            result.ownership_category = "短期譲渡（5年以下）"
            result.tax_rate_pct = 39.63   # 所得税30.63% + 住民税9%

        # 5. 税額
        result.tax_amount_yen = int(result.taxable_gain_yen * result.tax_rate_pct / 100)

        # 6. 手取り額
        result.net_proceeds_yen = (
            input_data.sale_price_yen
            - input_data.mortgage_balance_yen
            - result.total_sale_costs_yen
            - result.tax_amount_yen
        )

        # 内訳データ
        result.breakdown = [
            {"label": "売却価格", "amount": input_data.sale_price_yen, "type": "income"},
            {"label": "ローン残高", "amount": -input_data.mortgage_balance_yen, "type": "expense"},
            {"label": "仲介手数料", "amount": -result.brokerage_fee_yen, "type": "expense"},
            {"label": "印紙税", "amount": -result.stamp_duty_yen, "type": "expense"},
            {"label": "登記費用", "amount": -result.registration_fee_yen, "type": "expense"},
            {"label": "譲渡所得税", "amount": -result.tax_amount_yen, "type": "expense"},
            {"label": "総売却益", "amount": result.net_proceeds_yen, "type": "total"},
        ]

        return result

    def _calc_brokerage_fee(self, sale_price: int) -> int:
        """
        仲介手数料の計算（宅建業法の上限）

        速算式:
        - 400万円超: 売買価格 × 3% + 6万円 + 消費税
        - 200万円超400万円以下: 売買価格 × 4% + 2万円 + 消費税
        - 200万円以下: 売買価格 × 5% + 消費税
        """
        tax_rate = 1.10  # 消費税10%

        if sale_price > 4_000_000:
            fee = sale_price * 0.03 + 60_000
        elif sale_price > 2_000_000:
            fee = sale_price * 0.04 + 20_000
        else:
            fee = sale_price * 0.05

        return int(fee * tax_rate)

    def _calc_stamp_duty(self, sale_price: int) -> int:
        """
        印紙税額（不動産売買契約書）

        軽減税率適用後の金額（2027年3月31日まで）
        """
        if sale_price <= 1_000_000:
            return 500
        elif sale_price <= 5_000_000:
            return 1_000
        elif sale_price <= 10_000_000:
            return 5_000
        elif sale_price <= 50_000_000:
            return 10_000
        elif sale_price <= 100_000_000:
            return 30_000
        elif sale_price <= 500_000_000:
            return 60_000
        else:
            return 320_000
