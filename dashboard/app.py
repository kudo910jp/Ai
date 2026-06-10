"""
価格ウォッチ 不動産査定ダッシュボード v2

Flask Webアプリケーション。
物件情報の入力・写真アップロードから自動査定を行い、
価格推移・市場動向・相続シミュレーションまで一画面で確認できる。
"""

import os
import uuid
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request, jsonify

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from price_watch.config import StructureType, PropertyType
from price_watch.models.property import (
    PropertyInfo, LandInfo, BuildingInfo, BuildingComponent,
    RenovationRecord, LandShape, LandFacing,
)
from price_watch.models.market import AreaMarketData
from price_watch.data_sources.government_data import GovernmentLandPrice
from price_watch.price_watch import PriceWatch

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# ── エリアデータ ──

CITY_OPTIONS = {
    "東京都": ["世田谷区", "渋谷区", "新宿区", "杉並区", "目黒区", "大田区", "練馬区", "板橋区", "港区", "中央区", "品川区", "豊島区", "文京区", "中野区", "江東区", "台東区", "墨田区", "荒川区", "足立区", "葛飾区", "江戸川区", "北区"],
    "神奈川県": ["横浜市", "川崎市", "相模原市", "鎌倉市", "藤沢市", "横須賀市"],
    "埼玉県": ["さいたま市", "川越市", "所沢市", "越谷市", "川口市"],
    "千葉県": ["千葉市", "船橋市", "市川市", "松戸市", "柏市", "浦安市"],
    "大阪府": ["大阪市", "堺市", "豊中市", "吹田市", "高槻市"],
    "愛知県": ["名古屋市", "豊田市", "岡崎市", "一宮市"],
    "福岡県": ["福岡市", "北九州市", "久留米市"],
}

AREA_LAND_PRICES = {
    "東京都/世田谷区": GovernmentLandPrice(rosenka_per_sqm=400_000, koji_chika_per_sqm=520_000, gov_transaction_per_sqm=550_000, reference_year=2025),
    "東京都/渋谷区": GovernmentLandPrice(rosenka_per_sqm=800_000, koji_chika_per_sqm=1_050_000, gov_transaction_per_sqm=1_100_000, reference_year=2025),
    "東京都/新宿区": GovernmentLandPrice(rosenka_per_sqm=650_000, koji_chika_per_sqm=850_000, gov_transaction_per_sqm=900_000, reference_year=2025),
    "東京都/杉並区": GovernmentLandPrice(rosenka_per_sqm=350_000, koji_chika_per_sqm=460_000, gov_transaction_per_sqm=480_000, reference_year=2025),
    "東京都/目黒区": GovernmentLandPrice(rosenka_per_sqm=600_000, koji_chika_per_sqm=780_000, gov_transaction_per_sqm=820_000, reference_year=2025),
    "東京都/大田区": GovernmentLandPrice(rosenka_per_sqm=320_000, koji_chika_per_sqm=420_000, gov_transaction_per_sqm=440_000, reference_year=2025),
    "東京都/練馬区": GovernmentLandPrice(rosenka_per_sqm=280_000, koji_chika_per_sqm=360_000, gov_transaction_per_sqm=380_000, reference_year=2025),
    "東京都/板橋区": GovernmentLandPrice(rosenka_per_sqm=270_000, koji_chika_per_sqm=350_000, gov_transaction_per_sqm=370_000, reference_year=2025),
    "東京都/港区": GovernmentLandPrice(rosenka_per_sqm=1_500_000, koji_chika_per_sqm=2_000_000, gov_transaction_per_sqm=2_100_000, reference_year=2025),
    "東京都/中央区": GovernmentLandPrice(rosenka_per_sqm=1_200_000, koji_chika_per_sqm=1_600_000, gov_transaction_per_sqm=1_700_000, reference_year=2025),
    "東京都/品川区": GovernmentLandPrice(rosenka_per_sqm=550_000, koji_chika_per_sqm=720_000, gov_transaction_per_sqm=750_000, reference_year=2025),
    "東京都/豊島区": GovernmentLandPrice(rosenka_per_sqm=500_000, koji_chika_per_sqm=650_000, gov_transaction_per_sqm=680_000, reference_year=2025),
    "東京都/文京区": GovernmentLandPrice(rosenka_per_sqm=580_000, koji_chika_per_sqm=760_000, gov_transaction_per_sqm=790_000, reference_year=2025),
    "東京都/中野区": GovernmentLandPrice(rosenka_per_sqm=420_000, koji_chika_per_sqm=550_000, gov_transaction_per_sqm=570_000, reference_year=2025),
    "神奈川県/横浜市": GovernmentLandPrice(rosenka_per_sqm=250_000, koji_chika_per_sqm=330_000, gov_transaction_per_sqm=350_000, reference_year=2025),
    "神奈川県/川崎市": GovernmentLandPrice(rosenka_per_sqm=280_000, koji_chika_per_sqm=370_000, gov_transaction_per_sqm=390_000, reference_year=2025),
    "神奈川県/鎌倉市": GovernmentLandPrice(rosenka_per_sqm=220_000, koji_chika_per_sqm=290_000, gov_transaction_per_sqm=310_000, reference_year=2025),
    "埼玉県/さいたま市": GovernmentLandPrice(rosenka_per_sqm=180_000, koji_chika_per_sqm=240_000, gov_transaction_per_sqm=250_000, reference_year=2025),
    "千葉県/千葉市": GovernmentLandPrice(rosenka_per_sqm=120_000, koji_chika_per_sqm=160_000, gov_transaction_per_sqm=170_000, reference_year=2025),
    "千葉県/浦安市": GovernmentLandPrice(rosenka_per_sqm=300_000, koji_chika_per_sqm=400_000, gov_transaction_per_sqm=420_000, reference_year=2025),
    "大阪府/大阪市": GovernmentLandPrice(rosenka_per_sqm=300_000, koji_chika_per_sqm=400_000, gov_transaction_per_sqm=420_000, reference_year=2025),
    "愛知県/名古屋市": GovernmentLandPrice(rosenka_per_sqm=220_000, koji_chika_per_sqm=290_000, gov_transaction_per_sqm=310_000, reference_year=2025),
    "福岡県/福岡市": GovernmentLandPrice(rosenka_per_sqm=200_000, koji_chika_per_sqm=260_000, gov_transaction_per_sqm=280_000, reference_year=2025),
}

# 未登録エリアはデフォルト値で補完
DEFAULT_LAND_PRICE = GovernmentLandPrice(rosenka_per_sqm=150_000, koji_chika_per_sqm=200_000, gov_transaction_per_sqm=210_000, reference_year=2025)


def _generate_price_history(base_price: int, years: int = 10) -> list[dict]:
    random.seed(base_price % 10000)
    history = []
    today = date.today()
    for i in range(years * 4, -1, -1):
        d = today - timedelta(days=i * 91)
        quarter = f"{d.year}Q{(d.month - 1) // 3 + 1}"
        trend = 1.0 + (years * 4 - i) * 0.003
        noise = random.uniform(-0.02, 0.02)
        current = int(base_price * trend * (1 + noise))
        history.append({"period": quarter, "date": d.isoformat(), "price": current})
    random.seed()
    return history


def _generate_nearby_transactions(prefecture: str, city: str, base_price_sqm: float) -> list[dict]:
    random.seed(hash(f"{prefecture}{city}") % 100000)
    transactions = []
    today = date.today()
    streets = ["1丁目", "2丁目", "3丁目", "4丁目", "5丁目"]
    structures = ["木造", "軽量鉄骨", "鉄骨造", "RC造"]

    for i in range(20):
        days_ago = random.randint(10, 540)
        area = random.uniform(60, 200)
        building_area = random.uniform(50, 160)
        age = random.randint(0, 45)
        price_var = random.uniform(0.70, 1.30)
        price_sqm = base_price_sqm * price_var
        total = int(area * price_sqm)
        age_factor = max(0.05, 1.0 - age / 35.0)
        building_value = int(building_area * 180_000 * age_factor)

        transactions.append({
            "id": i + 1,
            "address": f"{prefecture}{city}{random.choice(streets)}",
            "transaction_date": (today - timedelta(days=days_ago)).isoformat(),
            "price_yen": total,
            "price_per_sqm": int(price_sqm),
            "land_area_sqm": round(area, 2),
            "building_area_sqm": round(building_area, 2),
            "building_age_years": age,
            "structure": random.choice(structures),
            "property_type": "戸建て" if random.random() > 0.3 else "マンション",
            "building_value_yen": building_value,
            "land_value_yen": total - building_value,
        })

    transactions.sort(key=lambda x: x["transaction_date"], reverse=True)
    random.seed()
    return transactions


def _calc_inheritance_tax(assessed_value: int, is_residence: bool = True, heirs: int = 1) -> dict:
    tax_assessed = int(assessed_value * 0.8)
    reduction = int(tax_assessed * 0.8) if is_residence else 0
    taxable_land = max(0, tax_assessed - reduction)
    basic_deduction = 30_000_000 + 6_000_000 * heirs
    taxable_estate = max(0, taxable_land - basic_deduction)

    brackets = [
        (10_000_000, 0.10, 0),
        (30_000_000, 0.15, 500_000),
        (50_000_000, 0.20, 2_000_000),
        (100_000_000, 0.30, 7_000_000),
        (200_000_000, 0.40, 17_000_000),
        (300_000_000, 0.45, 27_000_000),
        (600_000_000, 0.50, 42_000_000),
        (float("inf"), 0.55, 72_000_000),
    ]
    tax, rate = 0, 0
    for upper, r, deduct in brackets:
        if taxable_estate <= upper:
            tax = int(taxable_estate * r - deduct)
            rate = int(r * 100)
            break
    tax = max(0, tax)

    # 5年後・10年後の予測（年2%上昇想定）
    future = []
    for yr in [0, 5, 10]:
        future_val = int(assessed_value * (1.02 ** yr))
        f_tax_assessed = int(future_val * 0.8)
        f_reduction = int(f_tax_assessed * 0.8) if is_residence else 0
        f_taxable = max(0, f_tax_assessed - f_reduction)
        f_taxable_estate = max(0, f_taxable - basic_deduction)
        f_tax = 0
        for upper, r, deduct in brackets:
            if f_taxable_estate <= upper:
                f_tax = max(0, int(f_taxable_estate * r - deduct))
                break
        future.append({"years_from_now": yr, "estimated_value": future_val, "estimated_tax": f_tax})

    strategies = _inheritance_strategies(assessed_value, tax, is_residence)

    return {
        "assessed_value": assessed_value,
        "tax_assessed_value": tax_assessed,
        "small_land_reduction": reduction,
        "taxable_land_value": taxable_land,
        "basic_deduction": basic_deduction,
        "taxable_estate": taxable_estate,
        "tax_rate_pct": rate,
        "estimated_tax": tax,
        "heirs": heirs,
        "is_residence": is_residence,
        "strategies": strategies,
        "future_projections": future,
    }


def _inheritance_strategies(assessed_value: int, current_tax: int, is_residence: bool) -> list[dict]:
    strategies = []
    if not is_residence:
        strategies.append({
            "title": "小規模宅地等の特例の適用",
            "description": "被相続人が居住していた宅地は、330㎡まで評価額を80%減額できます。同居親族が相続する等の要件を満たす必要があります。",
            "potential_saving": int(assessed_value * 0.8 * 0.8 * 0.2),
            "difficulty": "中",
        })
    if assessed_value > 50_000_000:
        strategies.append({
            "title": "生前贈与の活用",
            "description": "年間110万円の基礎控除を活用し、計画的に財産を移転。10年で1,100万円の非課税移転が可能です。",
            "potential_saving": min(current_tax, int(assessed_value * 0.05)),
            "difficulty": "低",
        })
        strategies.append({
            "title": "相続時精算課税制度",
            "description": "60歳以上の親から18歳以上の子への贈与に2,500万円の特別控除が適用されます。",
            "potential_saving": min(current_tax, 5_000_000),
            "difficulty": "中",
        })
    if assessed_value > 80_000_000:
        strategies.append({
            "title": "不動産の組み替え（賃貸併用住宅）",
            "description": "自宅を賃貸併用住宅に建て替えることで、貸家建付地として評価額を約21%圧縮できます。",
            "potential_saving": int(assessed_value * 0.15),
            "difficulty": "高",
        })
    strategies.append({
        "title": "配偶者控除の活用",
        "description": "配偶者は1億6,000万円または法定相続分のいずれか大きい金額まで非課税です。",
        "potential_saving": min(current_tax, int(current_tax * 0.5)),
        "difficulty": "低",
    })
    return strategies


# ── ルーティング ──

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/cities")
def get_cities():
    pref = request.args.get("prefecture", "東京都")
    return jsonify(CITY_OPTIONS.get(pref, []))


@app.route("/api/assess", methods=["POST"])
def assess():
    data = request.json
    prefecture = data.get("prefecture", "東京都")
    city = data.get("city", "世田谷区")
    district = data.get("district", "")
    address = f"{prefecture}{city}{district}"

    structure_map = {"木造": StructureType.WOOD, "軽量鉄骨": StructureType.LIGHT_STEEL, "鉄骨造": StructureType.STEEL, "RC造": StructureType.RC, "SRC造": StructureType.SRC}
    structure = structure_map.get(data.get("structure", "木造"), StructureType.WOOD)
    shape_map = {"整形": LandShape.RECTANGLE, "台形": LandShape.TRAPEZOID, "旗竿地": LandShape.FLAG, "不整形": LandShape.IRREGULAR, "三角形": LandShape.TRIANGLE}
    shape = shape_map.get(data.get("land_shape", "整形"), LandShape.RECTANGLE)
    facing_map = {"南": LandFacing.SOUTH, "南東": LandFacing.SOUTH_EAST, "南西": LandFacing.SOUTH_WEST, "東": LandFacing.EAST, "西": LandFacing.WEST, "北": LandFacing.NORTH, "角地": LandFacing.CORNER}
    facing = facing_map.get(data.get("facing", "南"), LandFacing.SOUTH)

    land_area = float(data.get("land_area", 100))
    building_area = float(data.get("building_area", 80))
    building_age = int(data.get("building_age", 10))
    built_date = date(max(1900, date.today().year - building_age), 1, 1)
    road_width = float(data.get("road_width", 4.0))
    rooms = data.get("rooms", "3LDK")

    renovations = []
    for ren in data.get("renovations", []):
        comp_map = {"基礎・躯体": BuildingComponent.FOUNDATION, "設備・水回り": BuildingComponent.EQUIPMENT, "内装・仕上げ": BuildingComponent.INTERIOR}
        comp = comp_map.get(ren.get("component", ""), BuildingComponent.INTERIOR)
        ren_year = int(ren.get("year", date.today().year))
        renovations.append(RenovationRecord(
            component=comp,
            renovation_date=date(ren_year, 6, 1),
            description=ren.get("description", ""),
            cost_yen=int(ren.get("cost", 0)),
        ))

    prop = PropertyInfo(
        property_type=PropertyType.DETACHED_HOUSE,
        land=LandInfo(area_sqm=land_area, address=address, prefecture=prefecture, city=city, district=district, land_shape=shape, facing=facing, road_width_m=road_width),
        building=BuildingInfo(total_floor_area_sqm=building_area, structure_type=structure, built_date=built_date, rooms=rooms, renovation_records=renovations),
    )

    pw = PriceWatch()
    area_key = f"{prefecture}/{city}"
    gov = AREA_LAND_PRICES.get(area_key, DEFAULT_LAND_PRICE)
    pw.gov_data.register_mock_data(area_key, gov)

    base_sqm = gov.gov_transaction_per_sqm or 300_000
    random.seed(hash(area_key) % 10000)
    market_data = AreaMarketData(
        prefecture=prefecture, city=city, district=district,
        avg_price_per_sqm=base_sqm * 1.05, median_price_per_sqm=base_sqm,
        price_trend_pct=round(random.uniform(-2, 5), 1),
        active_listing_count=random.randint(20, 80),
        avg_days_on_market=round(random.uniform(40, 120), 0),
        monthly_sold_count=random.randint(3, 15),
        absorption_rate=round(random.uniform(3, 12), 1),
    )
    random.seed()

    result = pw.assess_stage1(property_info=prop, market_data=market_data)

    price_history = _generate_price_history(result.total_assessed_price_yen)
    nearby = _generate_nearby_transactions(prefecture, city, base_sqm)
    heirs = int(data.get("heirs", 1))
    inheritance = _calc_inheritance_tax(result.total_assessed_price_yen, is_residence=data.get("is_residence", True), heirs=heirs)

    sale_sim = None
    if data.get("mortgage_balance") is not None:
        sim_result = pw.simulate_sale(
            sale_price_yen=result.recommended_listing_price_yen,
            mortgage_balance_yen=int(data.get("mortgage_balance", 0)),
            purchase_price_yen=int(data.get("purchase_price", 0)),
            purchase_costs_yen=int(data.get("purchase_costs", 0)),
            is_residence=data.get("is_residence", True),
            ownership_years=float(building_age),
        )
        sale_sim = {
            "sale_price": sim_result.sale_price_yen, "mortgage_balance": sim_result.mortgage_balance_yen,
            "brokerage_fee": sim_result.brokerage_fee_yen, "stamp_duty": sim_result.stamp_duty_yen,
            "registration_fee": sim_result.registration_fee_yen, "total_costs": sim_result.total_sale_costs_yen,
            "capital_gain": sim_result.capital_gain_yen, "tax_deduction": sim_result.tax_deduction_yen,
            "tax_amount": sim_result.tax_amount_yen, "tax_rate": sim_result.tax_rate_pct,
            "ownership_category": sim_result.ownership_category, "net_proceeds": sim_result.net_proceeds_yen,
        }

    land_detail = result.land_assessment
    building_detail = result.building_assessment

    # 近隣の㎡単価統計
    nearby_sqm_prices = [t["price_per_sqm"] for t in nearby]
    nearby_avg_sqm = sum(nearby_sqm_prices) / len(nearby_sqm_prices) if nearby_sqm_prices else 0

    response = {
        "property_summary": {
            "address": address, "land_area": land_area, "building_area": building_area,
            "building_age": building_age, "structure": data.get("structure", "木造"),
            "rooms": rooms, "facing": data.get("facing", "南"),
            "land_shape": data.get("land_shape", "整形"), "road_width": road_width,
            "renovation_count": len(renovations),
        },
        "assessment": {
            "total_price": result.total_assessed_price_yen,
            "price_range_low": result.price_range_low_yen,
            "price_range_high": result.price_range_high_yen,
            "recommended_listing_price": result.recommended_listing_price_yen,
            "land_price": land_detail.assessed_price_yen if land_detail else 0,
            "building_price": building_detail.assessed_price_yen if building_detail else 0,
            "confidence_score": result.confidence.overall_score if result.confidence else 0,
            "confidence_rank": result.confidence.rank.value.split(":")[0] if result.confidence else "D",
            "confidence_detail": {
                "data_source": result.confidence.data_source_score,
                "comparable": result.confidence.comparable_score,
                "liquidity": result.confidence.market_liquidity_score,
                "freshness": result.confidence.data_freshness_score,
            } if result.confidence else {},
            "market_temperature": result.market_temperature or "",
            "avg_days_to_sell": result.avg_days_to_sell or 0,
            "notes": result.assessment_notes or [],
        },
        "land_detail": {
            "base_price_per_sqm": land_detail.base_price_per_sqm if land_detail else 0,
            "effective_area": land_detail.effective_area_sqm if land_detail else 0,
            "shape_adj": land_detail.shape_adjustment if land_detail else 0,
            "facing_adj": land_detail.facing_adjustment if land_detail else 0,
            "road_adj": land_detail.road_width_adjustment if land_detail else 0,
            "trend_adj": land_detail.market_trend_adjustment if land_detail else 0,
            "total_adj": land_detail.total_adjustment if land_detail else 0,
            "price_sources": land_detail.price_sources if land_detail else {},
        },
        "building_detail": None,
        "price_history": price_history,
        "nearby_transactions": nearby,
        "nearby_stats": {"avg_sqm_price": int(nearby_avg_sqm), "count": len(nearby), "your_sqm_price": int(land_detail.base_price_per_sqm) if land_detail else 0},
        "inheritance": inheritance,
        "sale_simulation": sale_sim,
        "market": {
            "temperature": market_data.market_temperature,
            "active_listings": market_data.active_listing_count,
            "avg_dom": market_data.avg_days_on_market,
            "price_trend_pct": market_data.price_trend_pct,
            "absorption_rate": market_data.absorption_rate,
        },
    }

    if building_detail:
        response["building_detail"] = {
            "reconstruction_cost": building_detail.gross_reconstruction_cost,
            "foundation_value": building_detail.foundation_value_yen,
            "foundation_dep_rate": building_detail.foundation_depreciation_rate,
            "foundation_eff_age": building_detail.foundation_effective_age,
            "equipment_value": building_detail.equipment_value_yen,
            "equipment_dep_rate": building_detail.equipment_depreciation_rate,
            "equipment_eff_age": building_detail.equipment_effective_age,
            "interior_value": building_detail.interior_value_yen,
            "interior_dep_rate": building_detail.interior_depreciation_rate,
            "interior_eff_age": building_detail.interior_effective_age,
            "overall_dep_rate": building_detail.overall_depreciation_rate,
            "market_adj": building_detail.market_adjustment,
        }

    return jsonify(response)


@app.route("/api/upload_photo", methods=["POST"])
def upload_photo():
    if "photo" not in request.files:
        return jsonify({"error": "写真が選択されていません"}), 400
    file = request.files["photo"]
    if file.filename == "":
        return jsonify({"error": "ファイルが選択されていません"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return jsonify({"error": "JPG, PNG, WebP形式のみ対応"}), 400
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    return jsonify({"filename": filename, "url": f"/static/uploads/{filename}"})


if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
