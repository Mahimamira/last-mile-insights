/* Order Operations Dashboard
 * Reads window.ORDERS (written by scripts/03_sql_analysis.py), applies the
 * filters in the browser and redraws every chart and table.
 */
(function () {
  const D = window.ORDERS;
  const $ = (id) => document.getElementById(id);

  // ---------- Decode compact rows ----------
  const orders = D.rows.map((r) => {
    const city = D.cities[r[1]];
    return {
      month: r[0].slice(0, 7),
      city,
      region: D.cityRegion[city],
      category: D.categories[r[2]],
      courier: D.couriers[r[3]],
      payment: D.payments[r[4]],
      status: D.statuses[r[5]],
      revenue: r[6],
      deliverDays: r[7],
      late: r[8],          // 1 late, 0 on time, -1 not delivered yet
      rating: r[9],        // 0 = not rated
      reason: r[10] >= 0 ? D.reasons[r[10]] : null,
    };
  });
  const months = [...new Set(orders.map((o) => o.month))].sort();
  const regions = [...new Set(Object.values(D.cityRegion))].sort();

  // ---------- Formatting ----------
  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthLabel = (m) => MONTH_NAMES[Number(m.slice(5)) - 1] + " " + m.slice(2, 4);
  const num = (n) => n.toLocaleString("en-IN");
  const pct = (n) => (isFinite(n) ? n.toFixed(1) + "%" : "–");
  const inr = (n) => {
    if (n >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " Cr";
    if (n >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " L";
    return "₹" + num(Math.round(n));
  };
  const bold = (s) => s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");

  // ---------- Metrics ----------
  function metrics(list) {
    let revenue = 0, dSum = 0, dN = 0, lateN = 0, lateD = 0, ret = 0, can = 0, rSum = 0, rN = 0;
    for (const o of list) {
      revenue += o.revenue;
      if (o.deliverDays >= 0) { dSum += o.deliverDays; dN++; }
      if (o.late >= 0) { lateN += o.late; lateD++; }
      if (o.status === "Returned") ret++;
      if (o.status === "Cancelled") can++;
      if (o.rating > 0) { rSum += o.rating; rN++; }
    }
    const n = list.length;
    return {
      orders: n, revenue,
      avgDays: dN ? dSum / dN : NaN,
      latePct: lateD ? (100 * lateN) / lateD : NaN,
      returnPct: n ? (100 * ret) / n : NaN,
      cancelPct: n ? (100 * can) / n : NaN,
      rating: rN ? rSum / rN : NaN,
      rated: rN, delivered: dN,
    };
  }
  function groupBy(list, key) {
    const m = new Map();
    for (const o of list) {
      const k = o[key];
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(o);
    }
    return m;
  }

  // ---------- Filters ----------
  const F = { region: "f-region", category: "f-category", courier: "f-courier", payment: "f-payment" };
  function fillSelect(id, values, allLabel) {
    $(id).innerHTML = `<option value="">${allLabel}</option>` +
      values.map((v) => `<option value="${v}">${v}</option>`).join("");
  }
  fillSelect(F.region, regions, "All regions");
  fillSelect(F.category, D.categories, "All categories");
  fillSelect(F.courier, D.couriers, "All couriers");
  fillSelect(F.payment, D.payments, "All payments");
  $("f-from").innerHTML = months.map((m) => `<option value="${m}">${monthLabel(m)}</option>`).join("");
  $("f-to").innerHTML = $("f-from").innerHTML;
  $("f-to").value = months[months.length - 1];

  function current() {
    let from = $("f-from").value, to = $("f-to").value;
    if (from > to) [from, to] = [to, from];
    return {
      region: $(F.region).value, category: $(F.category).value,
      courier: $(F.courier).value, payment: $(F.payment).value, from, to,
    };
  }
  function applyFilters(f) {
    return orders.filter((o) =>
      (!f.region || o.region === f.region) &&
      (!f.category || o.category === f.category) &&
      (!f.courier || o.courier === f.courier) &&
      (!f.payment || o.payment === f.payment) &&
      o.month >= f.from && o.month <= f.to);
  }
  function reset() {
    Object.values(F).forEach((id) => ($(id).value = ""));
    $("f-from").value = months[0];
    $("f-to").value = months[months.length - 1];
    render();
  }

  // ---------- Charts ----------
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  let C = {};
  const charts = {};
  const legendTop = { display: true, position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } };

  function readColors() {
    C = {
      text: css("--text"), muted: css("--muted"), grid: css("--grid"),
      s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"), warn: css("--warn"),
    };
    Chart.defaults.color = C.muted;
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.borderColor = C.grid;
  }

  const baseOpts = (extra = {}) => ({
    responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: "rgba(20,23,31,.92)", padding: 10, cornerRadius: 8 },
    },
    ...extra,
  });
  const pctAxis = () => ({ beginAtZero: true, grid: { color: C.grid }, ticks: { callback: (v) => v + "%" } });

  function upsert(id, type, data, options) {
    if (charts[id]) {
      charts[id].data = data;
      charts[id].options = options;
      charts[id].update();
    } else {
      charts[id] = new Chart($(id), { type, data, options });
    }
  }

  // Horizontal bar chart; `highlight` = index of the bar to colour as a warning (or -1)
  function hbar(id, labels, values, fmt, highlight = -1) {
    const colors = values.map((_, i) => (i === highlight ? C.warn : C.s1));
    const data = { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 4, barThickness: 16 }] };
    const opts = baseOpts({
      indexAxis: "y",
      scales: {
        x: { beginAtZero: true, grid: { color: C.grid }, ticks: { callback: (v) => fmt(v) } },
        y: { grid: { display: false }, ticks: { color: C.text } },
      },
    });
    opts.plugins.tooltip.callbacks = { label: (ctx) => " " + fmt(ctx.parsed.x) };
    upsert(id, "bar", data, opts);
  }

  function drawMonthly(list, f) {
    const by = groupBy(list, "month");
    const ms = months.filter((m) => m >= f.from && m <= f.to);
    const counts = ms.map((m) => (by.get(m) || []).length);
    const late = ms.map((m) => { const x = metrics(by.get(m) || []).latePct; return isFinite(x) ? +x.toFixed(1) : null; });
    const data = {
      labels: ms.map(monthLabel),
      datasets: [
        { type: "bar", label: "Orders", data: counts, backgroundColor: C.s3, borderRadius: 4, yAxisID: "y", order: 2 },
        { type: "line", label: "Late deliveries %", data: late, borderColor: C.warn, backgroundColor: C.warn,
          pointRadius: 3, pointHoverRadius: 5, borderWidth: 2, tension: 0.25, yAxisID: "y1", order: 1 },
      ],
    };
    const opts = baseOpts({
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: C.grid }, title: { display: true, text: "Orders" } },
        y1: { position: "right", beginAtZero: true, suggestedMax: 70, grid: { display: false },
          ticks: { callback: (v) => v + "%" }, title: { display: true, text: "Late %" } },
      },
    });
    opts.plugins.legend = legendTop;
    opts.plugins.tooltip.callbacks = {
      label: (ctx) => ctx.dataset.yAxisID === "y1" ? ` Late: ${ctx.parsed.y}%` : ` Orders: ${num(ctx.parsed.y)}`,
    };
    upsert("c-monthly", "bar", data, opts);
  }

  function drawCourier(list) {
    const rows = [...groupBy(list, "courier")].map(([k, v]) => [k, metrics(v).latePct]).filter((r) => isFinite(r[1]));
    rows.sort((a, b) => a[1] - b[1]);
    hbar("c-courier", rows.map((r) => r[0]), rows.map((r) => +r[1].toFixed(1)), (v) => v + "%",
      rows.length > 1 ? rows.length - 1 : -1);
  }

  function drawCategory(list) {
    const rows = [...groupBy(list, "category")].map(([k, v]) => [k, metrics(v).returnPct]);
    rows.sort((a, b) => b[1] - a[1]);
    hbar("c-category", rows.map((r) => r[0]), rows.map((r) => +r[1].toFixed(1)), (v) => v + "%",
      rows.length > 1 ? 0 : -1);
  }

  function drawReasons(list) {
    const ret = list.filter((o) => o.reason);
    const rows = [...groupBy(ret, "reason")].map(([k, v]) => [k, (100 * v.length) / ret.length]);
    rows.sort((a, b) => b[1] - a[1]);
    hbar("c-reasons", rows.map((r) => r[0]), rows.map((r) => +r[1].toFixed(1)), (v) => v + "%");
  }

  function drawPayment(list) {
    const rows = [...groupBy(list, "payment")].map(([k, v]) => [k, metrics(v)]);
    rows.sort((a, b) => b[1].orders - a[1].orders);
    const data = {
      labels: rows.map((r) => r[0]),
      datasets: [
        { label: "Cancelled %", data: rows.map((r) => +r[1].cancelPct.toFixed(1)), backgroundColor: C.s2, borderRadius: 4 },
        { label: "Returned %", data: rows.map((r) => +r[1].returnPct.toFixed(1)), backgroundColor: C.s1, borderRadius: 4 },
      ],
    };
    const opts = baseOpts({ scales: { x: { grid: { display: false }, ticks: { color: C.text } }, y: pctAxis() } });
    opts.plugins.legend = legendTop;
    opts.plugins.tooltip.callbacks = { label: (ctx) => ` ${ctx.dataset.label.replace(" %", "")}: ${ctx.parsed.y}%` };
    upsert("c-payment", "bar", data, opts);
  }

  function drawRating(list) {
    const dist = (sub) => {
      const rated = sub.filter((o) => o.rating > 0);
      return [1, 2, 3, 4, 5].map((s) => rated.length ? +((100 * rated.filter((o) => o.rating === s).length) / rated.length).toFixed(1) : 0);
    };
    const onTime = list.filter((o) => o.late === 0), late = list.filter((o) => o.late === 1);
    const mOn = metrics(onTime).rating, mLate = metrics(late).rating;
    const data = {
      labels: ["1★", "2★", "3★", "4★", "5★"],
      datasets: [
        { label: `On time (avg ${isFinite(mOn) ? mOn.toFixed(2) : "–"})`, data: dist(onTime), backgroundColor: C.s1, borderRadius: 4 },
        { label: `Late (avg ${isFinite(mLate) ? mLate.toFixed(2) : "–"})`, data: dist(late), backgroundColor: C.warn, borderRadius: 4 },
      ],
    };
    const opts = baseOpts({ scales: { x: { grid: { display: false }, ticks: { color: C.text } }, y: pctAxis() } });
    opts.plugins.legend = legendTop;
    opts.plugins.tooltip.callbacks = { label: (ctx) => ` ${ctx.dataset.label.split(" (")[0]}: ${ctx.parsed.y}% of ratings` };
    upsert("c-rating", "bar", data, opts);
  }

  function drawRevenue(list) {
    const rows = [...groupBy(list, "category")].map(([k, v]) => [k, metrics(v).revenue]);
    rows.sort((a, b) => b[1] - a[1]);
    hbar("c-revenue", rows.map((r) => r[0]), rows.map((r) => r[1]), inr);
  }

  function drawCityTable(list) {
    const rows = [...groupBy(list, "city")].map(([k, v]) => ({ city: k, region: D.cityRegion[k], ...metrics(v) }));
    rows.sort((a, b) => b.revenue - a.revenue);
    const maxLate = Math.max(1, ...rows.map((r) => (isFinite(r.latePct) ? r.latePct : 0)));
    const overall = metrics(list).latePct;
    $("t-city").querySelector("tbody").innerHTML = rows.map((r) => {
      const hot = isFinite(r.latePct) && r.latePct > overall * 1.25;
      const w = isFinite(r.latePct) ? Math.round((r.latePct / maxLate) * 100) : 0;
      return `<tr><td>${r.city}</td><td>${r.region}</td><td class="n">${num(r.orders)}</td>
        <td class="n">${inr(r.revenue)}</td><td class="n">${isFinite(r.avgDays) ? r.avgDays.toFixed(1) : "–"}</td>
        <td><div class="bar${hot ? " hot" : ""}"><em>${pct(r.latePct)}</em><span style="width:${w}px"></span></div></td></tr>`;
    }).join("");
  }

  // ---------- KPIs ----------
  function drawKpis(list, all) {
    const m = metrics(list), a = metrics(all);
    $("k-revenue").textContent = inr(m.revenue);
    $("k-revenue-s").textContent = `${((100 * m.revenue) / a.revenue).toFixed(0)}% of the year's total`;
    $("k-orders").textContent = num(m.orders);
    $("k-orders-s").textContent = `${pct(m.cancelPct)} cancelled`;
    $("k-days").textContent = isFinite(m.avgDays) ? m.avgDays.toFixed(1) + " days" : "–";
    $("k-days-s").textContent = "order to doorstep";
    $("k-late").textContent = pct(m.latePct);
    $("k-late-s").textContent = "delivered after promised date";
    $("k-return").textContent = pct(m.returnPct);
    $("k-return-s").textContent = "of orders sent back";
    $("k-rating").textContent = isFinite(m.rating) ? m.rating.toFixed(2) + " / 5" : "–";
    $("k-rating-s").textContent = `from ${num(m.rated)} ratings`;
  }

  // ---------- Render ----------
  function render() {
    const f = current();
    const list = applyFilters(f);
    const active = [f.region, f.category, f.courier, f.payment].filter(Boolean);
    const range = f.from === months[0] && f.to === months[months.length - 1] ? "all of 2025" : `${monthLabel(f.from)} – ${monthLabel(f.to)}`;
    $("showing").textContent = `Showing ${num(list.length)} of ${num(orders.length)} orders · ${range}` +
      (active.length ? ` · ${active.join(", ")}` : "");

    const empty = list.length === 0;
    $("empty").hidden = !empty;
    $("charts").hidden = empty;
    drawKpis(list, orders);
    if (empty) return;

    drawMonthly(list, f);
    drawCourier(list);
    drawCategory(list);
    drawReasons(list);
    drawPayment(list);
    drawRating(list);
    drawRevenue(list);
    drawCityTable(list);
  }

  // ---------- Static content ----------
  $("totalOrders").textContent = num(orders.length);
  $("findings").innerHTML = D.insights.findings.map((s) => `<li>${bold(s)}</li>`).join("");
  $("recs").innerHTML = D.insights.recommendations.map((s) => `<li>${bold(s)}</li>`).join("");

  // ---------- Events ----------
  [...Object.values(F), "f-from", "f-to"].forEach((id) => $(id).addEventListener("change", render));
  $("reset").addEventListener("click", reset);
  $("reset2").addEventListener("click", reset);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    readColors();
    Object.values(charts).forEach((c) => c.destroy());
    Object.keys(charts).forEach((k) => delete charts[k]);
    render();
  });

  readColors();
  render();
})();
