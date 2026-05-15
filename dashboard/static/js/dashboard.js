/**
 * 価格ウォッチ ダッシュボード JavaScript
 */

// ── 状態管理 ──
let state = {
    data: null,
    priceHistory: [],
    charts: {},
};

// ── ユーティリティ ──
function formatYen(n) {
    if (n === 0 || n == null) return "¥0";
    if (Math.abs(n) >= 100_000_000) {
        return `¥${(n / 100_000_000).toFixed(2)}億`;
    }
    if (Math.abs(n) >= 10_000) {
        return `¥${Math.round(n / 10_000).toLocaleString()}万`;
    }
    return `¥${n.toLocaleString()}`;
}

function formatYenFull(n) {
    return `¥${n.toLocaleString()}`;
}

function formatPct(n, digits = 1) {
    if (n == null) return "--";
    return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

// ── フォーム送信 ──
document.getElementById("assessForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    document.getElementById("emptyState").style.display = "none";
    document.getElementById("results").style.display = "none";
    document.getElementById("loading").style.display = "flex";

    const fd = new FormData(this);
    const payload = {
        prefecture: fd.get("prefecture"),
        city: fd.get("city"),
        district: fd.get("district") || "",
        land_area: parseFloat(fd.get("land_area")),
        land_shape: fd.get("land_shape"),
        facing: fd.get("facing"),
        road_width: parseFloat(fd.get("road_width")),
        building_area: parseFloat(fd.get("building_area")),
        structure: fd.get("structure"),
        building_age: parseInt(fd.get("building_age")),
        rooms: fd.get("rooms"),
        is_residence: fd.get("is_residence") === "on",
        heirs: parseInt(fd.get("heirs") || "1"),
        mortgage_balance: parseInt(fd.get("mortgage_balance") || "0") * 10000,
        purchase_price: parseInt(fd.get("purchase_price") || "0") * 10000,
        purchase_costs: parseInt(fd.get("purchase_costs") || "0") * 10000,
        renovations: [],
    };

    try {
        const resp = await fetch("/api/assess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        state.data = await resp.json();
        state.priceHistory = state.data.price_history || [];
        renderDashboard();
    } catch (err) {
        alert("査定に失敗しました: " + err.message);
    } finally {
        document.getElementById("loading").style.display = "none";
    }
});

// ── ダッシュボード描画 ──
function renderDashboard() {
    const d = state.data;
    document.getElementById("results").style.display = "block";

    // 1. 価格ヒーロー
    document.getElementById("totalPrice").textContent = formatYen(d.assessment.total_price);
    document.getElementById("priceRange").textContent =
        `価格レンジ: ${formatYen(d.assessment.price_range_low)} 〜 ${formatYen(d.assessment.price_range_high)}　／　推奨売出: ${formatYen(d.assessment.recommended_listing_price)}`;
    document.getElementById("confidenceRank").textContent = d.assessment.confidence_rank;

    const tempEl = document.getElementById("marketTemp");
    tempEl.textContent = d.assessment.market_temperature || "--";

    const domEl = document.getElementById("avgDom");
    domEl.textContent = d.assessment.avg_days_to_sell ? `約${d.assessment.avg_days_to_sell}日` : "--";

    // 信頼度ランクの色分け
    const confEl = document.getElementById("confidenceRank");
    confEl.className = "metric-value";
    if (d.assessment.confidence_rank === "A") confEl.style.color = "#059669";
    else if (d.assessment.confidence_rank === "B") confEl.style.color = "#1a56db";
    else if (d.assessment.confidence_rank === "C") confEl.style.color = "#d97706";
    else confEl.style.color = "#dc2626";

    // 2. 価格推移チャート
    renderPriceHistory(3);

    // 3. 査定内訳
    renderBreakdown();

    // 4. 建物減価償却
    renderDepreciation();

    // 5. 信頼度
    renderConfidence();

    // 6. 市場指標
    renderMarketMetrics();

    // 7. 近隣売買
    renderNearby();

    // 8. 売却シミュレーション
    renderSaleSimulation();

    // 9. 相続
    renderInheritance();

    // 10. 査定メモ
    renderNotes();
}

// ── 価格推移チャート ──
function renderPriceHistory(years) {
    const history = state.priceHistory;
    const cutoff = history.length - years * 4;
    const filtered = history.slice(Math.max(0, cutoff));

    const ctx = document.getElementById("priceHistoryChart");
    if (state.charts.priceHistory) state.charts.priceHistory.destroy();

    state.charts.priceHistory = new Chart(ctx, {
        type: "line",
        data: {
            labels: filtered.map(p => p.period),
            datasets: [{
                label: "推定価格",
                data: filtered.map(p => p.price),
                borderColor: "#1a56db",
                backgroundColor: "rgba(26, 86, 219, 0.08)",
                borderWidth: 2.5,
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => formatYenFull(ctx.raw),
                    },
                },
            },
            scales: {
                y: {
                    ticks: {
                        callback: v => formatYen(v),
                    },
                    grid: { color: "#f3f4f6" },
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12 },
                },
            },
        },
    });
}

// 期間タブ
document.getElementById("periodTabs").addEventListener("click", function (e) {
    if (!e.target.classList.contains("tab")) return;
    this.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    e.target.classList.add("active");
    renderPriceHistory(parseInt(e.target.dataset.years));
});

// ── 査定内訳 ──
function renderBreakdown() {
    const d = state.data;
    const landPrice = d.assessment.land_price;
    const buildingPrice = d.assessment.building_price;
    const ctx = document.getElementById("breakdownChart");
    if (state.charts.breakdown) state.charts.breakdown.destroy();

    state.charts.breakdown = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["土地", "建物"],
            datasets: [{
                data: [landPrice, buildingPrice],
                backgroundColor: ["#1a56db", "#60a5fa"],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "65%",
            plugins: {
                tooltip: {
                    callbacks: { label: ctx => `${ctx.label}: ${formatYen(ctx.raw)}` },
                },
            },
        },
    });

    const detail = document.getElementById("breakdownDetail");
    const ld = d.land_detail;
    detail.innerHTML = `
        <div class="detail-row"><span class="label">土地査定額</span><span class="value">${formatYen(landPrice)}</span></div>
        <div class="detail-row"><span class="label">建物査定額</span><span class="value">${formatYen(buildingPrice)}</span></div>
        <div class="detail-row"><span class="label">基準㎡単価</span><span class="value">${formatYenFull(Math.round(ld.base_price_per_sqm))}/㎡</span></div>
        <div class="detail-row"><span class="label">有効面積</span><span class="value">${ld.effective_area}㎡</span></div>
        <div class="detail-row"><span class="label">補正合計</span><span class="value">${formatPct(ld.total_adj * 100)}</span></div>
    `;
}

// ── 建物減価償却 ──
function renderDepreciation() {
    const bd = state.data.building_detail;
    if (!bd) return;

    const ctx = document.getElementById("depreciationChart");
    if (state.charts.depreciation) state.charts.depreciation.destroy();

    state.charts.depreciation = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["基礎・躯体", "設備・水回り", "内装・仕上げ"],
            datasets: [
                {
                    label: "残存価値",
                    data: [bd.foundation_value, bd.equipment_value, bd.interior_value],
                    backgroundColor: ["#1a56db", "#3b82f6", "#93c5fd"],
                    borderRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: { label: ctx => formatYen(ctx.raw) },
                },
            },
            scales: {
                y: {
                    ticks: { callback: v => formatYen(v) },
                    grid: { color: "#f3f4f6" },
                },
                x: { grid: { display: false } },
            },
        },
    });

    const detail = document.getElementById("depreciationDetail");
    detail.innerHTML = `
        <div class="detail-row"><span class="label">再調達原価</span><span class="value">${formatYen(bd.reconstruction_cost)}</span></div>
        <div class="detail-row"><span class="label">基礎・躯体 償却率</span><span class="value">${(bd.foundation_dep_rate * 100).toFixed(1)}%</span></div>
        <div class="detail-row"><span class="label">設備・水回り 償却率</span><span class="value">${(bd.equipment_dep_rate * 100).toFixed(1)}%</span></div>
        <div class="detail-row"><span class="label">内装・仕上げ 償却率</span><span class="value">${(bd.interior_dep_rate * 100).toFixed(1)}%</span></div>
        <div class="detail-row"><span class="label">総合償却率</span><span class="value">${(bd.overall_dep_rate * 100).toFixed(1)}%</span></div>
    `;
}

// ── 信頼度 ──
function renderConfidence() {
    const d = state.data;
    const score = d.assessment.confidence_score;
    const ctx = document.getElementById("confidenceChart");
    if (state.charts.confidence) state.charts.confidence.destroy();

    const pct = Math.round(score * 100);
    state.charts.confidence = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["信頼度", ""],
            datasets: [{
                data: [pct, 100 - pct],
                backgroundColor: [
                    pct >= 80 ? "#059669" : pct >= 60 ? "#1a56db" : pct >= 40 ? "#d97706" : "#dc2626",
                    "#f3f4f6",
                ],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "75%",
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false },
            },
        },
        plugins: [{
            id: "centerText",
            afterDraw(chart) {
                const { ctx, width, height } = chart;
                ctx.save();
                ctx.font = "bold 28px sans-serif";
                ctx.fillStyle = "#1f2937";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(`${pct}%`, width / 2, height / 2);
                ctx.restore();
            },
        }],
    });

    const notes = document.getElementById("confidenceNotes");
    const noteItems = d.assessment.notes || [];
    notes.innerHTML = noteItems.map(n => `<li>${n}</li>`).join("");
}

// ── 市場指標 ──
function renderMarketMetrics() {
    const m = state.data.market;
    const el = document.getElementById("marketMetrics");
    const trendClass = m.price_trend_pct >= 0 ? "positive" : "negative";
    const absClass = m.absorption_rate < 6 ? "positive" : m.absorption_rate > 9 ? "negative" : "";

    el.innerHTML = `
        <div class="market-metric-item">
            <div class="mm-label">価格トレンド（前年比）</div>
            <div class="mm-value ${trendClass}">${formatPct(m.price_trend_pct)}</div>
        </div>
        <div class="market-metric-item">
            <div class="mm-label">平均掲載日数</div>
            <div class="mm-value">${m.avg_dom ? Math.round(m.avg_dom) + "日" : "--"}</div>
        </div>
        <div class="market-metric-item">
            <div class="mm-label">在庫物件数</div>
            <div class="mm-value">${m.active_listings}件</div>
        </div>
        <div class="market-metric-item">
            <div class="mm-label">在庫消化率</div>
            <div class="mm-value ${absClass}">${m.absorption_rate ? m.absorption_rate.toFixed(1) + "ヶ月" : "--"}</div>
        </div>
    `;
}

// ── 近隣売買事例 ──
function renderNearby() {
    const tbody = document.getElementById("nearbyBody");
    const txns = state.data.nearby_transactions || [];
    tbody.innerHTML = txns.map(t => `
        <tr>
            <td>${t.transaction_date}</td>
            <td>${t.address}</td>
            <td>${t.property_type}</td>
            <td>${t.structure}</td>
            <td>${t.land_area_sqm}㎡</td>
            <td>${t.building_area_sqm}㎡</td>
            <td>${t.building_age_years}年</td>
            <td class="price-cell">${formatYenFull(t.price_per_sqm)}/㎡</td>
            <td class="price-cell">${formatYen(t.price_yen)}</td>
        </tr>
    `).join("");
}

// ── 売却シミュレーション ──
function renderSaleSimulation() {
    const sim = state.data.sale_simulation;
    const card = document.getElementById("saleSimCard");
    if (!sim) { card.style.display = "none"; return; }
    card.style.display = "block";

    document.getElementById("saleSimContent").innerHTML = `
        <div class="sim-item"><span class="sim-label">売却価格</span><span class="sim-value">${formatYen(sim.sale_price)}</span></div>
        <div class="sim-item"><span class="sim-label">ローン残高</span><span class="sim-value">-${formatYen(sim.mortgage_balance)}</span></div>
        <div class="sim-item"><span class="sim-label">仲介手数料</span><span class="sim-value">-${formatYen(sim.brokerage_fee)}</span></div>
        <div class="sim-item"><span class="sim-label">印紙税</span><span class="sim-value">-${formatYen(sim.stamp_duty)}</span></div>
        <div class="sim-item"><span class="sim-label">登記費用</span><span class="sim-value">-${formatYen(sim.registration_fee)}</span></div>
        <div class="sim-item"><span class="sim-label">譲渡所得税</span><span class="sim-value">-${formatYen(sim.tax_amount)}</span></div>
        <div class="sim-item"><span class="sim-label">税率 (${sim.ownership_category})</span><span class="sim-value">${sim.tax_rate}%</span></div>
        <div class="sim-item"><span class="sim-label">特別控除</span><span class="sim-value">${formatYen(sim.tax_deduction)}</span></div>
        <div class="sim-item total"><span class="sim-label">総売却益（手取り額）</span><span class="sim-value">${formatYen(sim.net_proceeds)}</span></div>
    `;
}

// ── 相続シミュレーション ──
function renderInheritance() {
    const inh = state.data.inheritance;
    if (!inh) return;

    const taxFree = inh.estimated_tax === 0;
    const content = document.getElementById("inheritanceContent");

    let strategiesHtml = "";
    if (inh.strategies && inh.strategies.length > 0) {
        strategiesHtml = `<div class="strategy-list"><h4 style="margin-bottom:10px; font-size:0.95rem;">相続対策の提案</h4>` +
            inh.strategies.map(s => `
                <div class="strategy-item">
                    <h4>${s.title}</h4>
                    <p>${s.description}</p>
                    <span class="strategy-saving">節税効果: ${formatYen(s.potential_saving)}</span>
                    <span class="strategy-difficulty">難易度: ${s.difficulty}</span>
                </div>
            `).join("") + "</div>";
    }

    content.innerHTML = `
        <div class="inheritance-summary">
            <div class="inh-card">
                <div class="inh-label">相続税評価額</div>
                <div class="inh-value">${formatYen(inh.tax_assessed_value)}</div>
            </div>
            <div class="inh-card">
                <div class="inh-label">基礎控除</div>
                <div class="inh-value">${formatYen(inh.basic_deduction)}</div>
            </div>
            <div class="inh-card ${taxFree ? 'tax-free' : 'tax-due'}">
                <div class="inh-label">概算相続税額</div>
                <div class="inh-value">${taxFree ? "非課税" : formatYen(inh.estimated_tax)}</div>
            </div>
        </div>
        <div class="sim-item"><span class="sim-label">時価（査定額）</span><span class="sim-value">${formatYen(inh.assessed_value)}</span></div>
        <div class="sim-item"><span class="sim-label">路線価評価（時価×80%）</span><span class="sim-value">${formatYen(inh.tax_assessed_value)}</span></div>
        <div class="sim-item"><span class="sim-label">小規模宅地等の特例（居住用80%減額）</span><span class="sim-value">-${formatYen(inh.small_land_reduction)}</span></div>
        <div class="sim-item"><span class="sim-label">課税評価額</span><span class="sim-value">${formatYen(inh.taxable_land_value)}</span></div>
        <div class="sim-item"><span class="sim-label">基礎控除（3,000万+600万×${inh.heirs}人）</span><span class="sim-value">-${formatYen(inh.basic_deduction)}</span></div>
        <div class="sim-item"><span class="sim-label">課税遺産総額</span><span class="sim-value">${formatYen(inh.taxable_estate)}</span></div>
        <div class="sim-item"><span class="sim-label">税率</span><span class="sim-value">${inh.tax_rate_pct}%</span></div>
        ${strategiesHtml}
    `;
}

// ── 査定メモ ──
function renderNotes() {
    const notes = state.data.assessment.notes || [];
    document.getElementById("assessmentNotes").innerHTML =
        notes.map(n => `<li>${n}</li>`).join("");
}

// ── 写真アップロード ──
const dropZone = document.getElementById("photoDropZone");
const photoInput = document.getElementById("photoInput");
const photoPreview = document.getElementById("photoPreview");

dropZone.addEventListener("click", () => photoInput.click());
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    handleFiles(e.dataTransfer.files);
});
photoInput.addEventListener("change", e => handleFiles(e.target.files));

function handleFiles(files) {
    for (const file of files) {
        // プレビュー表示
        const reader = new FileReader();
        reader.onload = e => {
            const img = document.createElement("img");
            img.src = e.target.result;
            photoPreview.appendChild(img);
        };
        reader.readAsDataURL(file);

        // アップロード
        const fd = new FormData();
        fd.append("photo", file);
        fetch("/api/upload_photo", { method: "POST", body: fd })
            .catch(err => console.error("Upload error:", err));
    }
}
