/**
 * TRANSACTIONGUARD DASHBOARD CORE LOGIC
 * Vanilla JS ES6+ (Real-time updates, Custom SVG Charts, Simulation Manager)
 */

// Configure your Production Render Backend URL here
const PRODUCTION_BACKEND_URL = "https://risktrack-backend.onrender.com";

const getApiUrl = () => {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }
    return PRODUCTION_BACKEND_URL;
};

const API_BASE = getApiUrl();
let knownTxnIds = new Set();
let statsInterval = null;
let currentUsers = [];

// DOM Elements
const statusDot = document.getElementById("status-dot");
const statusLabel = document.getElementById("status-label");
const btnRefresh = document.getElementById("btn-refresh");
const selectUser = document.getElementById("select-user");
const valTotal = document.getElementById("val-total");
const valReview = document.getElementById("val-review");
const valBlocked = document.getElementById("val-blocked");
const valApprovalRate = document.getElementById("val-approval-rate");
const txnTableBody = document.getElementById("txn-table-body");
const profilesList = document.getElementById("profiles-list");
const distChartWrapper = document.getElementById("dist-chart-wrapper");
const trendChartWrapper = document.getElementById("trend-chart-wrapper");
const detailModal = document.getElementById("detail-modal");
const modalClose = document.getElementById("modal-close");
const modalContent = document.getElementById("modal-content");

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
    initApp();
    setupEventListeners();
});

async function initApp() {
    updateConnectionStatus("connecting", "Connecting to Risk Engine...");
    
    // Fetch users first to populate dropdowns and baselines
    await fetchUsers();
    
    // Initial fetch of statistics and transaction logs
    await fetchDashboardStats();
    
    // Poll stats every 3 seconds for real-time dashboard reactivity
    statsInterval = setInterval(fetchDashboardStats, 3000);
}

function setupEventListeners() {
    // Refresh button click
    btnRefresh.addEventListener("click", () => {
        fetchDashboardStats();
    });

    // Simulation triggers
    const simButtons = document.querySelectorAll(".btn-sim");
    simButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            const btnTarget = e.currentTarget;
            const scenarioType = btnTarget.getAttribute("data-type");
            const selectedUserId = selectUser.value;
            triggerSimulation(scenarioType, selectedUserId, btnTarget);
        });
    });

    // Modal Close handlers
    modalClose.addEventListener("click", () => {
        detailModal.classList.remove("active");
    });
    
    detailModal.addEventListener("click", (e) => {
        if (e.target === detailModal) {
            detailModal.classList.remove("active");
        }
    });
}

function updateConnectionStatus(state, message) {
    statusDot.className = "status-indicator";
    if (state === "online") {
        statusDot.classList.add("live");
        statusLabel.textContent = `Live: ${message}`;
        statusLabel.style.color = "var(--text-primary)";
    } else if (state === "error") {
        statusDot.classList.add("error");
        statusLabel.textContent = `Offline: ${message}`;
        statusLabel.style.color = "var(--color-block)";
    } else {
        statusLabel.textContent = message;
        statusLabel.style.color = "var(--text-secondary)";
    }
}

// Fetch users baseline details from API
async function fetchUsers() {
    try {
        const response = await fetch(`${API_BASE}/api/users`);
        if (!response.ok) throw new Error("Could not fetch user baselines");
        
        currentUsers = await response.json();
        
        // Populate select element
        selectUser.innerHTML = '<option value="">-- Random Customer Profile --</option>';
        currentUsers.forEach(u => {
            const option = document.createElement("option");
            option.value = u.id;
            option.textContent = `${u.name} (${u.id})`;
            selectUser.appendChild(option);
        });

        // Render profile cards in left panel
        renderProfileBaselines(currentUsers);
        
    } catch (err) {
        console.error("Error loading user baselines:", err);
        updateConnectionStatus("error", "Database initialization failed");
    }
}

// Render baseline information cards in simulator panel
function renderProfileBaselines(users) {
    profilesList.innerHTML = "";
    users.forEach(u => {
        const card = document.createElement("div");
        card.className = "profile-card";
        
        // Format location metadata
        let locationName = "Global Baseline";
        if (u.id === "USR1001") locationName = "Mumbai, IN";
        else if (u.id === "USR1002") locationName = "London, UK";
        else if (u.id === "USR1003") locationName = "San Francisco, US";

        card.innerHTML = `
            <div class="profile-info">
                <span class="profile-name">${u.name}</span>
                <span class="profile-meta">📍 Last known: ${locationName}</span>
                <span class="profile-meta">🕒 Active: ${u.common_hours}</span>
            </div>
            <div class="profile-stats text-muted">
                <span>Avg: ₹${u.avg_amount.toLocaleString()}</span>
            </div>
        `;
        profilesList.appendChild(card);
    });
}

// Fetch main dashboard operational stats
async function fetchDashboardStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (!response.ok) throw new Error("Stats request failed");
        
        const stats = await response.json();
        
        // Update Connection Status
        updateConnectionStatus("online", `Connected to ${API_BASE}`);

        // Update KPIs
        valTotal.textContent = stats.total_transactions.toLocaleString();
        valReview.textContent = stats.review_count.toLocaleString();
        valBlocked.textContent = stats.blocked_count.toLocaleString();
        valApprovalRate.textContent = `${stats.approval_rate}%`;

        // Render Custom SVG charts
        renderDistributionChart(stats.risk_buckets);
        renderTrendsChart(stats.hourly_trends);

        // Update logs table
        updateTransactionsTable(stats.recent_transactions);

    } catch (err) {
        console.error("Stats fetching error:", err);
        updateConnectionStatus("error", "Failed to retrieve live stats");
    }
}

// Populate Recent evaluations audit log table
function updateTransactionsTable(transactions) {
    if (transactions.length === 0) {
        txnTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-8">No transaction logs available.</td></tr>`;
        return;
    }

    const currentTxnIds = new Set(transactions.map(t => t.id));
    
    // Draw rows
    txnTableBody.innerHTML = "";
    transactions.forEach(tx => {
        const tr = document.createElement("tr");
        tr.id = `row-${tx.id}`;
        
        // Check if this is a newly discovered transaction during polling
        const isNew = knownTxnIds.size > 0 && !knownTxnIds.has(tx.id);
        if (isNew) {
            tr.className = "txn-row-new";
        }

        const score = tx.evaluation ? tx.evaluation.risk_score : 0;
        const decision = tx.evaluation ? tx.evaluation.decision : "UNKNOWN";
        
        let badgeClass = "badge-approve";
        let fillClass = "var(--color-approve)";
        if (decision === "BLOCK") {
            badgeClass = "badge-block";
            fillClass = "var(--color-block)";
        } else if (decision === "REVIEW") {
            badgeClass = "badge-review";
            fillClass = "var(--color-review)";
        }

        tr.innerHTML = `
            <td><strong>${tx.id}</strong></td>
            <td>${tx.user_name}</td>
            <td>₹${tx.amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td>
                <div class="table-score-wrapper">
                    <div class="table-score-bar">
                        <div class="table-score-fill" style="width: ${score}%; background: ${fillClass}"></div>
                    </div>
                    <strong>${score}</strong>
                </div>
            </td>
            <td><span class="badge ${badgeClass}">${decision}</span></td>
        `;

        // Click handler to open explanation report
        tr.addEventListener("click", () => {
            showTransactionDetail(tx.id);
        });

        txnTableBody.appendChild(tr);
    });

    // Update global list of known IDs
    knownTxnIds = currentTxnIds;
}

// Show risk explanation modal
async function showTransactionDetail(txnId) {
    try {
        const response = await fetch(`${API_BASE}/api/transactions/${txnId}`);
        if (!response.ok) throw new Error("Could not fetch evaluation details");
        
        const tx = await response.json();
        const ev = tx.evaluation;
        
        if (!ev) {
            alert("No risk assessment evaluation data exists for this historical transaction.");
            return;
        }

        let scoreClass = "score-low";
        if (ev.decision === "BLOCK") scoreClass = "score-high";
        else if (ev.decision === "REVIEW") scoreClass = "score-med";

        // Generate reasons list HTML
        const reasonsHtml = ev.reasons.map(r => `<li>${r}</li>`).join("");

        // Set geographic distance visualizer properties
        let distanceDetail = "Local Location (Home Baseline)";
        let impliedSpeedText = "Implied Speed: N/A";
        
        // Find if this was Priya (London), Rahul (Mumbai), or Vikram (SF) and extract baseline locations
        let baseLocationName = "Home Baseline";
        let targetLocationName = "Current Transaction Location";
        
        if (tx.user_id === "USR1001") {
            baseLocationName = "Mumbai (Home)";
            if (tx.location_lat !== 19.0760) targetLocationName = `Mumbai Offset (${tx.location_lat.toFixed(3)}, ${tx.location_lon.toFixed(3)})`;
            else targetLocationName = "Mumbai Central";
        } else if (tx.user_id === "USR1002") {
            baseLocationName = "London (Home)";
            if (tx.location_lat !== 51.5074) targetLocationName = `London Offset (${tx.location_lat.toFixed(3)}, ${tx.location_lon.toFixed(3)})`;
            else targetLocationName = "London Central";
        } else if (tx.user_id === "USR1003") {
            baseLocationName = "San Francisco (Home)";
            if (tx.location_lat !== 37.7749) targetLocationName = `SF Offset (${tx.location_lat.toFixed(3)}, ${tx.location_lon.toFixed(3)})`;
            else targetLocationName = "SF Financial Dist";
        }

        // Draw geographic summary
        let geoDetailsHtml = "";
        const travelReason = ev.reasons.find(r => r.includes("Travel") || r.includes("Geo"));
        if (travelReason) {
            geoDetailsHtml = `<p class="text-center font-semibold text-red-500 mt-2">${travelReason}</p>`;
        }

        // Format dates
        const txnDateStr = new Date(tx.timestamp).toLocaleString();
        const evalDateStr = new Date(ev.evaluated_at).toLocaleString();

        modalContent.innerHTML = `
            <div class="report-header-summary">
                <div class="report-gauge">
                    <div class="radial-score ${scoreClass}">${ev.risk_score}</div>
                    <div>
                        <span class="badge ${ev.decision === 'BLOCK' ? 'badge-block' : ev.decision === 'REVIEW' ? 'badge-review' : 'badge-approve'}">${ev.decision}</span>
                        <h3 class="mt-1" style="font-size: 1.1rem; font-weight:700;">Final Risk Verdict: ${ev.decision}</h3>
                        <p class="text-muted" style="font-size: 0.75rem;">Calculated at ${evalDateStr}</p>
                    </div>
                </div>
                <div class="text-right text-muted" style="font-size:0.75rem;">
                    <span>System ID: <strong>${tx.id}</strong></span>
                </div>
            </div>

            <div class="report-details-grid">
                <div class="meta-item">
                    <div class="meta-item-label">CUSTOMER NAME</div>
                    <div class="meta-item-value">${tx.user_name} (${tx.user_id})</div>
                </div>
                <div class="meta-item">
                    <div class="meta-item-label">TRANSACTION AMOUNT</div>
                    <div class="meta-item-value">₹${tx.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-item-label">MERCHANT / BRAND</div>
                    <div class="meta-item-value">${tx.merchant}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-item-label">TRANSACTION HOUR & DATE</div>
                    <div class="meta-item-value">${txnDateStr}</div>
                </div>
            </div>

            <!-- Rules breakdown -->
            <div class="rules-breakdown">
                <h3>🔍 Rule Scoring Breakdown (Weighted)</h3>
                
                <!-- Velocity Check Row -->
                <div class="rule-metric-row">
                    <div class="rule-metric-header">
                        <span class="rule-name">Velocity Limit Check</span>
                        <span class="rule-weight-badge">Weight: 30%</span>
                        <strong>${ev.velocity_score} / 100</strong>
                    </div>
                    <div class="rule-bar-outer">
                        <div class="rule-bar-fill" id="fill-vel" style="background: var(--color-block)"></div>
                    </div>
                </div>

                <!-- Amount Anomaly Row -->
                <div class="rule-metric-row">
                    <div class="rule-metric-header">
                        <span class="rule-name">Historical Amount Anomaly</span>
                        <span class="rule-weight-badge">Weight: 25%</span>
                        <strong>${ev.amount_anomaly_score} / 100</strong>
                    </div>
                    <div class="rule-bar-outer">
                        <div class="rule-bar-fill" id="fill-amt" style="background: var(--color-review)"></div>
                    </div>
                </div>

                <!-- Geo Mismatch Row -->
                <div class="rule-metric-row">
                    <div class="rule-metric-header">
                        <span class="rule-name">Geographic Implausible Travel</span>
                        <span class="rule-weight-badge">Weight: 25%</span>
                        <strong>${ev.geo_mismatch_score} / 100</strong>
                    </div>
                    <div class="rule-bar-outer">
                        <div class="rule-bar-fill" id="fill-geo" style="background: var(--color-accent)"></div>
                    </div>
                </div>

                <!-- Unusual Hour Row -->
                <div class="rule-metric-row">
                    <div class="rule-metric-header">
                        <span class="rule-name">Unusual Time Outlier</span>
                        <span class="rule-weight-badge">Weight: 10%</span>
                        <strong>${ev.unusual_hour_score} / 100</strong>
                    </div>
                    <div class="rule-bar-outer">
                        <div class="rule-bar-fill" id="fill-hour" style="background: #8b5cf6"></div>
                    </div>
                </div>

                <!-- New Merchant Row -->
                <div class="rule-metric-row">
                    <div class="rule-metric-header">
                        <span class="rule-name">New Merchant Baseline check</span>
                        <span class="rule-weight-badge">Weight: 10%</span>
                        <strong>${ev.new_merchant_score} / 100</strong>
                    </div>
                    <div class="rule-bar-outer">
                        <div class="rule-bar-fill" id="fill-merch" style="background: var(--text-secondary)"></div>
                    </div>
                </div>
            </div>

            <!-- Geographic Mapping Visualization -->
            <div class="geo-visualizer">
                <h3>🗺️ Spatial Geo-Mismatch Visualizer</h3>
                <div class="geo-radar-drawing">
                    <div class="radar-sweep"></div>
                    <div class="radar-distance-line"></div>
                    <div class="radar-node node-origin"></div>
                    <span class="node-label" style="left: 20%; top: 58%;">${baseLocationName}</span>
                    <div class="radar-node node-destination"></div>
                    <span class="node-label" style="right: 18%; top: 48%;">${targetLocationName}</span>
                    
                    <div class="radar-speed-overlay">
                        ${ev.geo_mismatch_score > 0 ? "⚠️ GEOGRAPHIC VELOCITY DEVIATION DETECTED" : "✅ GEO POSITION STABLE"}
                    </div>
                </div>
                ${geoDetailsHtml}
            </div>

            <!-- Audit Trail Reasons -->
            <div class="chart-container mt-4">
                <h3 style="margin-bottom: 0.5rem; color:#ffffff;">📋 Audit Justification Trail</h3>
                <ul class="text-muted" style="font-size:0.75rem; padding-left: 1.2rem; line-height: 1.5;">
                    ${reasonsHtml}
                </ul>
            </div>
        `;

        // Open Modal
        detailModal.classList.add("active");

        // Micro-timeout to animate progress bars
        setTimeout(() => {
            document.getElementById("fill-vel").style.width = `${ev.velocity_score}%`;
            document.getElementById("fill-amt").style.width = `${ev.amount_anomaly_score}%`;
            document.getElementById("fill-geo").style.width = `${ev.geo_mismatch_score}%`;
            document.getElementById("fill-hour").style.width = `${ev.unusual_hour_score}%`;
            document.getElementById("fill-merch").style.width = `${ev.new_merchant_score}%`;
        }, 100);

    } catch (err) {
        console.error("Modal detail fetch failure:", err);
        alert("Failed to fetch detailed transaction audit record.");
    }
}

// Trigger simulation of different fraud scenarios
async function triggerSimulation(scenarioType, userId, btnElement) {
    // Prevent double clicking
    btnElement.style.pointerEvents = "none";
    btnElement.style.opacity = "0.5";
    
    try {
        let queryParams = `scenario_type=${scenarioType}`;
        if (userId) queryParams += `&user_id=${userId}`;
        
        const response = await fetch(`${API_BASE}/api/simulate?${queryParams}`, {
            method: "POST"
        });
        
        if (!response.ok) throw new Error("Simulation trigger failed");
        
        const res = await response.json();
        
        // Instantly fetch dashboard stats to reflect the new transaction
        await fetchDashboardStats();
        
        // Highlight row in table
        const row = document.getElementById(`row-${res.id}`);
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            // Highlight row by flashing
            row.className = "txn-row-new";
            setTimeout(() => {
                row.className = "";
            }, 2500);
        }

    } catch (err) {
        console.error("Simulation error:", err);
        alert(`Failed to simulate scenario: ${err.message}`);
    } finally {
        btnElement.style.pointerEvents = "auto";
        btnElement.style.opacity = "1";
    }
}

// Render Risk Score Distribution Chart (Custom Inline SVG)
function renderDistributionChart(buckets) {
    const maxVal = Math.max(...buckets, 1); // Avoid division by zero
    const labels = ["0-20", "21-40", "41-60", "61-80", "81-100"];
    
    // Canvas size
    const width = 450;
    const height = 180;
    const padding = 30;
    const chartHeight = height - padding * 2;
    const chartWidth = width - padding * 2;
    
    const barWidth = chartWidth / buckets.length - 12;
    
    let svgContent = `<svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" style="font-family: var(--font-body)">`;
    
    // Draw Y axis lines
    for (let i = 0; i <= 4; i++) {
        const y = padding + (chartHeight / 4) * i;
        svgContent += `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="var(--border-color)" stroke-width="1" />`;
    }
    
    // Draw bars
    buckets.forEach((val, idx) => {
        const barHeight = (val / maxVal) * chartHeight;
        const x = padding + idx * (chartWidth / buckets.length) + 6;
        const y = height - padding - barHeight;
        
        // Style color based on severity index
        let color = "rgba(16, 185, 129, 0.4)"; // low risk
        if (idx === 4 || idx === 3) color = "rgba(239, 68, 68, 0.5)"; // high risk
        else if (idx === 2) color = "rgba(245, 158, 11, 0.5)"; // medium risk
        
        svgContent += `
            <rect class="chart-bar" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="${color}" rx="4" />
            <text x="${x + barWidth/2}" y="${height - 10}" fill="var(--text-secondary)" font-size="9" text-anchor="middle">${labels[idx]}</text>
            <text x="${x + barWidth/2}" y="${y - 6}" fill="#ffffff" font-size="10" font-weight="600" text-anchor="middle">${val}</text>
        `;
    });
    
    svgContent += `</svg>`;
    distChartWrapper.innerHTML = svgContent;
}

// Render Risk Trends Chart (Custom Inline SVG Line Chart)
function renderTrendsChart(trends) {
    if (!trends || trends.length === 0) {
        trendChartWrapper.innerHTML = `<span class="text-muted text-xs">Awaiting data baseline...</span>`;
        return;
    }

    // Canvas size
    const width = 450;
    const height = 180;
    const padding = 30;
    const chartHeight = height - padding * 2;
    const chartWidth = width - padding * 2;
    
    // Map trends points
    // Max average risk is 100
    const points = trends.map((t, idx) => {
        const x = padding + (idx * (chartWidth / (trends.length - 1)));
        const y = height - padding - (t.avg_risk / 100) * chartHeight;
        return { x, y, hour: t.hour, value: t.avg_risk };
    });

    let pathD = "";
    let areaD = `M ${points[0].x} ${height - padding} `;
    
    points.forEach((p, idx) => {
        if (idx === 0) {
            pathD += `M ${p.x} ${p.y} `;
        } else {
            pathD += `L ${p.x} ${p.y} `;
        }
        areaD += `L ${p.x} ${p.y} `;
    });
    areaD += `L ${points[points.length - 1].x} ${height - padding} Z`;

    let svgContent = `<svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">`;
    
    // Draw background guide grid lines (X & Y axes)
    for (let i = 0; i <= 4; i++) {
        const y = padding + (chartHeight / 4) * i;
        svgContent += `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="var(--border-color)" stroke-width="1" stroke-dasharray="2,4" />`;
    }
    
    // Render filled gradient area under the line
    svgContent += `
        <defs>
            <linearGradient id="chart-area-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--color-accent)" stop-opacity="0.2"/>
                <stop offset="100%" stop-color="var(--color-accent)" stop-opacity="0.0"/>
            </linearGradient>
        </defs>
        <path d="${areaD}" fill="url(#chart-area-grad)" />
    `;
    
    // Draw continuous trend path line
    svgContent += `<path class="chart-line" d="${pathD}" fill="none" stroke="var(--color-accent)" stroke-width="2" />`;
    
    // Render key point nodes on coordinates
    points.forEach((p, idx) => {
        // Show point only if there were actual transactions or every 4 hours to avoid clutter
        if (p.hour % 4 === 0 || idx === 0 || idx === points.length - 1) {
            svgContent += `
                <circle cx="${p.x}" cy="${p.y}" r="4" fill="#ffffff" stroke="var(--color-accent)" stroke-width="2" />
                <text x="${p.x}" y="${height - 10}" fill="var(--text-secondary)" font-size="8" text-anchor="middle">${p.hour}:00</text>
                <text x="${p.x}" y="${p.y - 8}" fill="#ffffff" font-size="8" font-weight="600" text-anchor="middle">${Math.round(p.value)}</text>
            `;
        }
    });

    svgContent += `</svg>`;
    trendChartWrapper.innerHTML = svgContent;
}
