/**
 * 価格ウォッチ ダッシュボード v2
 */

let state = { data: null, priceHistory: [], charts: {} };

// ── ユーティリティ ──
function yen(n) {
    if (n == null || n === 0) return "¥0";
    if (Math.abs(n) >= 1e8) return `¥${(n / 1e8).toFixed(2)}億`;
    if (Math.abs(n) >= 1e4) return `¥${Math.round(n / 1e4).toLocaleString()}万`;
    return `¥${n.toLocaleString()}`;
}
function yenFull(n) { return `¥${(n || 0).toLocaleString()}`; }
function pct(n, d=1) { return n == null ? "--" : `${n >= 0 ? "+" : ""}${n.toFixed(d)}%`; }

// ── 都道府県→市区町村連動 ──
async function loadCities() {
    const pref = document.getElementById("prefecture").value;
    const resp = await fetch(`/api/cities?prefecture=${encodeURIComponent(pref)}`);
    const cities = await resp.json();
    const sel = document.getElementById("city");
    sel.innerHTML = cities.map(c => `<option value="${c}">${c}</option>`).join("");
}
document.getElementById("prefecture").addEventListener("change", loadCities);
loadCities();

// ── リフォーム履歴の動的追加 ──
let renovationIdx = 0;
document.getElementById("btnAddRenovation").addEventListener("click", function() {
    const list = document.getElementById("renovationList");
    const div = document.createElement("div");
    div.className = "renovation-entry";
    div.innerHTML = `
        <div class="field-grid">
            <div class="field-row"><label>部位</label>
                <select data-ren="component">
                    <option value="設備・水回り">設備・水回り</option>
                    <option value="内装・仕上げ">内装・仕上げ</option>
                    <option value="基礎・躯体">基礎・躯体</option>
                </select>
            </div>
            <div class="field-row"><label>実施年</label>
                <input type="number" data-ren="year" value="${new Date().getFullYear() - 3}" min="1970" max="${new Date().getFullYear()}">
            </div>
        </div>
        <div class="field-grid">
            <div class="field-row"><label>内容</label>
                <input type="text" data-ren="description" placeholder="キッチン交換等">
            </div>
            <div class="field-row"><label>費用（万円）</label>
                <input type="number" data-ren="cost" value="200" min="0">
            </div>
        </div>
        <button type="button" class="btn-remove-ren" onclick="this.closest('.renovation-entry').remove()">&#10005; 削除</button>
    `;
    list.appendChild(div);
    renovationIdx++;
});

function collectRenovations() {
    const entries = document.querySelectorAll(".renovation-entry");
    return Array.from(entries).map(el => ({
        component: el.querySelector("[data-ren='component']").value,
        year: parseInt(el.querySelector("[data-ren='year']").value),
        description: el.querySelector("[data-ren='description']").value,
        cost: parseInt(el.querySelector("[data-ren='cost']").value || "0") * 10000,
    }));
}

// ── フォーム送信 ──
document.getElementById("assessForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    document.getElementById("emptyState").style.display = "none";
    document.getElementById("results").style.display = "none";
    document.getElementById("loading").style.display = "flex";
    const btn = document.getElementById("btnAssess");
    btn.disabled = true; btn.textContent = "査定中...";

    const fd = new FormData(this);
    const payload = {
        prefecture: fd.get("prefecture"), city: fd.get("city"), district: fd.get("district") || "",
        land_area: parseFloat(fd.get("land_area")), land_shape: fd.get("land_shape"),
        facing: fd.get("facing"), road_width: parseFloat(fd.get("road_width")),
        building_area: parseFloat(fd.get("building_area")), structure: fd.get("structure"),
        building_age: parseInt(fd.get("building_age")), rooms: fd.get("rooms"),
        is_residence: fd.get("is_residence") === "on",
        heirs: parseInt(fd.get("heirs") || "1"),
        mortgage_balance: parseInt(fd.get("mortgage_balance") || "0") * 10000,
        purchase_price: parseInt(fd.get("purchase_price") || "0") * 10000,
        purchase_costs: parseInt(fd.get("purchase_costs") || "0") * 10000,
        renovations: collectRenovations(),
    };

    try {
        const resp = await fetch("/api/assess", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        state.data = await resp.json();
        state.priceHistory = state.data.price_history || [];
        renderDashboard();
        document.getElementById("btnPrint").style.display = "flex";
    } catch(err) {
        alert("査定に失敗しました: " + err.message);
    } finally {
        document.getElementById("loading").style.display = "none";
        btn.disabled = false; btn.textContent = "査定を実行";
    }
});

// ── メイン描画 ──
function renderDashboard() {
    const d = state.data;
    document.getElementById("results").style.display = "block";

    renderPropertySummary();
    renderPriceHero();
    renderPriceHistory(3);
    renderBreakdown();
    renderDepreciation();
    renderConfidence();
    renderMarketMetrics();
    renderNearbyCompare();
    renderNearby();
    renderSaleSimulation();
    renderInheritance();
    renderNotes();

    // スクロールトップ
    document.getElementById("dashboard").scrollTo({ top: 0, behavior: "smooth" });
}

// ── 物件概要バー ──
function renderPropertySummary() {
    const p = state.data.property_summary;
    document.getElementById("propertySummary").innerHTML = `
        <div class="summary-tag"><b>${p.address}</b></div>
        <div class="summary-tag">土地 ${p.land_area}&#13217;</div>
        <div class="summary-tag">建物 ${p.building_area}&#13217;</div>
        <div class="summary-tag">築${p.building_age}年</div>
        <div class="summary-tag">${p.structure}</div>
        <div class="summary-tag">${p.rooms}</div>
        <div class="summary-tag">${p.facing}向き</div>
        ${p.renovation_count > 0 ? `<div class="summary-tag accent">リフォーム${p.renovation_count}件</div>` : ""}
    `;
}

// ── 価格ヒーロー ──
function renderPriceHero() {
    const a = state.data.assessment;
    document.getElementById("totalPrice").textContent = yen(a.total_price);
    document.getElementById("priceRange").textContent = `価格レンジ: ${yen(a.price_range_low)} 〜 ${yen(a.price_range_high)}　｜　推奨売出: ${yen(a.recommended_listing_price)}`;

    const confEl = document.getElementById("confidenceRank");
    confEl.textContent = a.confidence_rank;
    confEl.style.color = a.confidence_rank === "A" ? "#059669" : a.confidence_rank === "B" ? "#1a56db" : a.confidence_rank === "C" ? "#d97706" : "#dc2626";

    document.getElementById("marketTemp").textContent = a.market_temperature || "--";
    document.getElementById("avgDom").textContent = a.avg_days_to_sell ? `約${a.avg_days_to_sell}日` : "--";
}

// ── 価格推移 ──
function renderPriceHistory(years) {
    const h = state.priceHistory;
    const filtered = h.slice(Math.max(0, h.length - years * 4));
    const ctx = document.getElementById("priceHistoryChart");
    if (state.charts.ph) state.charts.ph.destroy();

    // 変動率の計算
    const firstP = filtered[0]?.price || 1;
    const lastP = filtered[filtered.length-1]?.price || 0;
    const changePct = ((lastP - firstP) / firstP * 100).toFixed(1);

    state.charts.ph = new Chart(ctx, {
        type: "line",
        data: {
            labels: filtered.map(p => p.period),
            datasets: [{
                label: `推定価格 (${years}年: ${changePct >= 0 ? "+" : ""}${changePct}%)`,
                data: filtered.map(p => p.price),
                borderColor: "#1a56db", backgroundColor: "rgba(26,86,219,0.06)",
                borderWidth: 2.5, fill: true, tension: 0.3, pointRadius: 2, pointHoverRadius: 6,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: true, position: "top", labels: { font: { size: 12 } } }, tooltip: { callbacks: { label: c => yenFull(c.raw) } } },
            scales: { y: { ticks: { callback: v => yen(v) }, grid: { color: "#f3f4f6" } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } } },
        },
    });
}

document.getElementById("periodTabs").addEventListener("click", function(e) {
    if (!e.target.classList.contains("tab")) return;
    this.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    e.target.classList.add("active");
    renderPriceHistory(parseInt(e.target.dataset.years));
});

// ── 査定内訳 ──
function renderBreakdown() {
    const d = state.data, landP = d.assessment.land_price, buildP = d.assessment.building_price;
    const ctx = document.getElementById("breakdownChart");
    if (state.charts.bd) state.charts.bd.destroy();

    state.charts.bd = new Chart(ctx, {
        type: "doughnut",
        data: { labels: ["土地", "建物"], datasets: [{ data: [landP, buildP], backgroundColor: ["#1a56db", "#60a5fa"], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: "65%", plugins: { tooltip: { callbacks: { label: c => `${c.label}: ${yen(c.raw)}` } } } },
        plugins: [{
            id: "centerTotal", afterDraw(chart) {
                const {ctx:c, width:w, height:h} = chart; c.save();
                c.font = "bold 16px sans-serif"; c.fillStyle = "#1f2937"; c.textAlign = "center"; c.textBaseline = "middle";
                c.fillText(yen(landP + buildP), w/2, h/2); c.restore();
            }
        }],
    });

    const ld = d.land_detail;
    const landPct = Math.round(landP / (landP + buildP) * 100);
    document.getElementById("breakdownDetail").innerHTML = `
        <div class="detail-row"><span class="label">土地査定額（${landPct}%）</span><span class="value">${yen(landP)}</span></div>
        <div class="detail-row"><span class="label">建物査定額（${100-landPct}%）</span><span class="value">${yen(buildP)}</span></div>
        <div class="detail-row"><span class="label">基準&#13217;単価</span><span class="value">${yenFull(Math.round(ld.base_price_per_sqm))}/&#13217;</span></div>
        <div class="detail-row"><span class="label">有効面積</span><span class="value">${ld.effective_area}&#13217;</span></div>
        <div class="detail-row"><span class="label">形状補正</span><span class="value">${pct(ld.shape_adj*100)}</span></div>
        <div class="detail-row"><span class="label">接道補正</span><span class="value">${pct(ld.facing_adj*100)}</span></div>
        <div class="detail-row"><span class="label">道路幅員補正</span><span class="value">${pct(ld.road_adj*100)}</span></div>
        <div class="detail-row"><span class="label">市場動向補正</span><span class="value">${pct(ld.trend_adj*100)}</span></div>
        <div class="detail-row total"><span class="label">補正合計</span><span class="value">${pct(ld.total_adj*100)}</span></div>
    `;
}

// ── 建物減価償却 ──
function renderDepreciation() {
    const bd = state.data.building_detail;
    if (!bd) { document.getElementById("depreciationDetail").innerHTML = "<p>建物なし（土地のみ）</p>"; return; }

    const ctx = document.getElementById("depreciationChart");
    if (state.charts.dep) state.charts.dep.destroy();

    const maxVal = Math.max(bd.foundation_value, bd.equipment_value, bd.interior_value, 1);
    state.charts.dep = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["基礎・躯体\n(45%)", "設備・水回り\n(30%)", "内装・仕上げ\n(25%)"],
            datasets: [{ label: "残存価値", data: [bd.foundation_value, bd.equipment_value, bd.interior_value], backgroundColor: ["#1e40af", "#3b82f6", "#93c5fd"], borderRadius: 6 }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, indexAxis: "y",
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => yen(c.raw) } } },
            scales: { x: { ticks: { callback: v => yen(v) }, grid: { color: "#f3f4f6" } }, y: { grid: { display: false } } },
        },
    });

    document.getElementById("depreciationDetail").innerHTML = `
        <div class="detail-row"><span class="label">再調達原価</span><span class="value">${yen(bd.reconstruction_cost)}</span></div>
        <div class="detail-row"><span class="label">基礎・躯体（実効${bd.foundation_eff_age?.toFixed(1) || "--"}年）</span><span class="value">償却 ${(bd.foundation_dep_rate*100).toFixed(1)}%</span></div>
        <div class="detail-row"><span class="label">設備・水回り（実効${bd.equipment_eff_age?.toFixed(1) || "--"}年）</span><span class="value">償却 ${(bd.equipment_dep_rate*100).toFixed(1)}%</span></div>
        <div class="detail-row"><span class="label">内装・仕上げ（実効${bd.interior_eff_age?.toFixed(1) || "--"}年）</span><span class="value">償却 ${(bd.interior_dep_rate*100).toFixed(1)}%</span></div>
        <div class="detail-row total"><span class="label">総合償却率</span><span class="value">${(bd.overall_dep_rate*100).toFixed(1)}%</span></div>
    `;
}

// ── 信頼度レーダー ──
function renderConfidence() {
    const d = state.data, score = d.assessment.confidence_score, cd = d.assessment.confidence_detail;
    const ctx = document.getElementById("confidenceChart");
    if (state.charts.conf) state.charts.conf.destroy();

    state.charts.conf = new Chart(ctx, {
        type: "radar",
        data: {
            labels: ["データソース", "類似物件", "市場流動性", "データ鮮度"],
            datasets: [{
                label: "スコア",
                data: [cd.data_source || 0, cd.comparable || 0, cd.liquidity || 0, cd.freshness || 0],
                backgroundColor: "rgba(26,86,219,0.15)", borderColor: "#1a56db", borderWidth: 2, pointBackgroundColor: "#1a56db",
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { r: { min: 0, max: 1, ticks: { stepSize: 0.25, display: false }, grid: { color: "#e5e7eb" }, pointLabels: { font: { size: 11 } } } },
            plugins: { legend: { display: false } },
        },
    });

    const p = Math.round(score * 100);
    const notes = d.assessment.notes || [];
    document.getElementById("confidenceNotes").innerHTML =
        `<li><b>総合信頼度: ${p}%</b>（ランク ${d.assessment.confidence_rank}）</li>` +
        notes.map(n => `<li>${n}</li>`).join("");
}

// ── 市場指標 ──
function renderMarketMetrics() {
    const m = state.data.market;
    const tCls = m.price_trend_pct >= 0 ? "positive" : "negative";
    const aCls = m.absorption_rate < 6 ? "positive" : m.absorption_rate > 9 ? "negative" : "";
    const tempCls = m.temperature === "売り手市場" ? "positive" : m.temperature === "買い手市場" ? "negative" : "";

    document.getElementById("marketMetrics").innerHTML = `
        <div class="market-metric-item"><div class="mm-label">市場温度</div><div class="mm-value ${tempCls}">${m.temperature || "--"}</div></div>
        <div class="market-metric-item"><div class="mm-label">価格トレンド（前年比）</div><div class="mm-value ${tCls}">${pct(m.price_trend_pct)}</div></div>
        <div class="market-metric-item"><div class="mm-label">平均掲載日数</div><div class="mm-value">${m.avg_dom ? Math.round(m.avg_dom) + "日" : "--"}</div></div>
        <div class="market-metric-item"><div class="mm-label">在庫物件数</div><div class="mm-value">${m.active_listings}件</div></div>
        <div class="market-metric-item"><div class="mm-label">在庫消化率</div><div class="mm-value ${aCls}">${m.absorption_rate ? m.absorption_rate.toFixed(1) + "ヶ月" : "--"}</div></div>
        <div class="market-metric-item"><div class="mm-label">消化率判定</div><div class="mm-value small">${m.absorption_rate < 6 ? "需要 > 供給" : m.absorption_rate > 9 ? "供給 > 需要" : "需給均衡"}</div></div>
    `;
}

// ── 近隣㎡単価比較チャート ──
function renderNearbyCompare() {
    const txns = state.data.nearby_transactions || [];
    const ns = state.data.nearby_stats;
    const ctx = document.getElementById("nearbyCompareChart");
    if (state.charts.nc) state.charts.nc.destroy();

    // 近隣取引を㎡単価でソート、ヒストグラム風に表示
    const sorted = [...txns].sort((a,b) => a.price_per_sqm - b.price_per_sqm);
    const labels = sorted.map((t,i) => `事例${i+1}`);
    const prices = sorted.map(t => t.price_per_sqm);

    // あなたの物件の位置を示す線
    const yourPrice = ns.your_sqm_price;

    state.charts.nc = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "近隣取引 ㎡単価",
                data: prices,
                backgroundColor: prices.map(p => p <= yourPrice ? "#93c5fd" : "#60a5fa"),
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => `${yenFull(c.raw)}/㎡` } },
                annotation: {},
            },
            scales: {
                y: { ticks: { callback: v => yen(v) }, grid: { color: "#f3f4f6" } },
                x: { grid: { display: false }, ticks: { display: false } },
            },
        },
        plugins: [{
            id: "yourLine",
            afterDraw(chart) {
                const {ctx:c, chartArea, scales} = chart;
                const yPos = scales.y.getPixelForValue(yourPrice);
                if (yPos >= chartArea.top && yPos <= chartArea.bottom) {
                    c.save();
                    c.beginPath(); c.setLineDash([6,4]);
                    c.strokeStyle = "#dc2626"; c.lineWidth = 2;
                    c.moveTo(chartArea.left, yPos); c.lineTo(chartArea.right, yPos);
                    c.stroke();
                    c.fillStyle = "#dc2626"; c.font = "bold 12px sans-serif"; c.textAlign = "right";
                    c.fillText(`あなたの物件: ${yenFull(yourPrice)}/㎡`, chartArea.right, yPos - 6);
                    c.restore();
                }
            }
        }],
    });
}

// ── 近隣売買事例テーブル ──
function renderNearby() {
    document.getElementById("nearbyBody").innerHTML = (state.data.nearby_transactions || []).map(t => `
        <tr>
            <td>${t.transaction_date}</td><td>${t.address}</td><td>${t.property_type}</td><td>${t.structure}</td>
            <td>${t.land_area_sqm}&#13217;</td><td>${t.building_area_sqm}&#13217;</td><td>${t.building_age_years}年</td>
            <td class="price-cell">${yenFull(t.price_per_sqm)}/&#13217;</td><td class="price-cell">${yen(t.price_yen)}</td>
        </tr>
    `).join("");
}

// ── 売却シミュレーション ──
function renderSaleSimulation() {
    const sim = state.data.sale_simulation;
    const card = document.getElementById("saleSimCard");
    if (!sim) { card.style.display = "none"; return; }
    card.style.display = "block";

    const netCls = sim.net_proceeds >= 0 ? "" : "negative-total";
    document.getElementById("saleSimContent").innerHTML = `
        <div class="sim-item"><span class="sim-label">売却価格</span><span class="sim-value">${yen(sim.sale_price)}</span></div>
        <div class="sim-item"><span class="sim-label">ローン残高</span><span class="sim-value">-${yen(sim.mortgage_balance)}</span></div>
        <div class="sim-item"><span class="sim-label">仲介手数料</span><span class="sim-value">-${yen(sim.brokerage_fee)}</span></div>
        <div class="sim-item"><span class="sim-label">印紙税 + 登記費用</span><span class="sim-value">-${yen(sim.stamp_duty + sim.registration_fee)}</span></div>
        <div class="sim-item"><span class="sim-label">譲渡所得税（${sim.ownership_category}）</span><span class="sim-value">-${yen(sim.tax_amount)}</span></div>
        <div class="sim-item"><span class="sim-label">特別控除（マイホーム3,000万）</span><span class="sim-value">${yen(sim.tax_deduction)}</span></div>
        <div class="sim-item total ${netCls}"><span class="sim-label">総売却益（手取り額）</span><span class="sim-value">${yen(sim.net_proceeds)}</span></div>
    `;
}

// ── 相続シミュレーション ──
function renderInheritance() {
    const inh = state.data.inheritance;
    if (!inh) return;

    const taxFree = inh.estimated_tax === 0;
    const fp = inh.future_projections || [];

    // 相続税タイムラインチャートを動的に作成
    let futureChartHtml = "";
    if (fp.length > 1) {
        futureChartHtml = `<div class="inheritance-timeline"><h4>相続発生時期による税額予測</h4><div class="chart-container-sm"><canvas id="inheritanceFutureChart"></canvas></div></div>`;
    }

    const stratHtml = (inh.strategies || []).map(s => `
        <div class="strategy-item">
            <h4>${s.title}</h4>
            <p>${s.description}</p>
            <span class="strategy-saving">節税効果: ${yen(s.potential_saving)}</span>
            <span class="strategy-difficulty">難易度: ${s.difficulty}</span>
        </div>
    `).join("");

    document.getElementById("inheritanceContent").innerHTML = `
        <div class="inheritance-summary">
            <div class="inh-card"><div class="inh-label">相続税評価額</div><div class="inh-value">${yen(inh.tax_assessed_value)}</div></div>
            <div class="inh-card"><div class="inh-label">基礎控除</div><div class="inh-value">${yen(inh.basic_deduction)}</div></div>
            <div class="inh-card ${taxFree ? 'tax-free' : 'tax-due'}"><div class="inh-label">概算相続税額</div><div class="inh-value">${taxFree ? "非課税" : yen(inh.estimated_tax)}</div></div>
        </div>
        <div class="inheritance-grid">
            <div class="sim-item"><span class="sim-label">時価（査定額）</span><span class="sim-value">${yen(inh.assessed_value)}</span></div>
            <div class="sim-item"><span class="sim-label">路線価評価（時価×80%）</span><span class="sim-value">${yen(inh.tax_assessed_value)}</span></div>
            <div class="sim-item"><span class="sim-label">小規模宅地特例（居住用80%減額）</span><span class="sim-value">-${yen(inh.small_land_reduction)}</span></div>
            <div class="sim-item"><span class="sim-label">課税評価額</span><span class="sim-value">${yen(inh.taxable_land_value)}</span></div>
            <div class="sim-item"><span class="sim-label">基礎控除（3,000万+600万×${inh.heirs}人）</span><span class="sim-value">-${yen(inh.basic_deduction)}</span></div>
            <div class="sim-item"><span class="sim-label">課税遺産総額</span><span class="sim-value">${yen(inh.taxable_estate)}</span></div>
        </div>
        ${futureChartHtml}
        <div class="strategy-list"><h4>相続対策の提案</h4>${stratHtml}</div>
    `;

    // タイムラインチャート描画
    if (fp.length > 1) {
        setTimeout(() => {
            const fCtx = document.getElementById("inheritanceFutureChart");
            if (!fCtx) return;
            if (state.charts.inhFuture) state.charts.inhFuture.destroy();
            state.charts.inhFuture = new Chart(fCtx, {
                type: "bar",
                data: {
                    labels: fp.map(f => f.years_from_now === 0 ? "現在" : `${f.years_from_now}年後`),
                    datasets: [
                        { label: "推定時価", data: fp.map(f => f.estimated_value), backgroundColor: "#dbeafe", borderColor: "#3b82f6", borderWidth: 1, borderRadius: 4 },
                        { label: "概算相続税", data: fp.map(f => f.estimated_tax), backgroundColor: fp.map(f => f.estimated_tax > 0 ? "#fecaca" : "#d1fae5"), borderColor: fp.map(f => f.estimated_tax > 0 ? "#dc2626" : "#059669"), borderWidth: 1, borderRadius: 4 },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${yen(c.raw)}` } } },
                    scales: { y: { ticks: { callback: v => yen(v) }, grid: { color: "#f3f4f6" } }, x: { grid: { display: false } } },
                },
            });
        }, 100);
    }
}

// ── 査定メモ ──
function renderNotes() {
    const notes = state.data.assessment.notes || [];
    document.getElementById("assessmentNotes").innerHTML = notes.map(n => `<li>${n}</li>`).join("");
}

// ── 写真アップロード ──
const dropZone = document.getElementById("photoDropZone");
const photoInput = document.getElementById("photoInput");
const photoPreview = document.getElementById("photoPreview");

dropZone.addEventListener("click", () => photoInput.click());
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", e => { e.preventDefault(); dropZone.classList.remove("dragover"); handleFiles(e.dataTransfer.files); });
photoInput.addEventListener("change", e => handleFiles(e.target.files));

function handleFiles(files) {
    for (const file of files) {
        const reader = new FileReader();
        reader.onload = e => {
            const wrap = document.createElement("div");
            wrap.className = "photo-thumb";
            wrap.innerHTML = `<img src="${e.target.result}"><button type="button" class="photo-remove" onclick="this.parentElement.remove()">×</button>`;
            photoPreview.appendChild(wrap);
        };
        reader.readAsDataURL(file);
        const fd = new FormData();
        fd.append("photo", file);
        fetch("/api/upload_photo", { method: "POST", body: fd }).catch(err => console.error(err));
    }
}
