"""
Step 3 - Load the clean data into SQLite and run the SQL analysis.

Input : data/clean/orders_clean.csv, sql/analysis_queries.sql
Output: data/orders.db                 (SQLite database - open it in DB Browser for SQLite)
        outputs/sql_results/*.csv      (one file per query)
        outputs/sql_results.md         (all results as readable tables)
        outputs/insights.md            (key findings + recommendations)
        docs/data.js                   (data for the web dashboard)
"""
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "orders_clean.csv"
DB = ROOT / "data" / "orders.db"
SQL = ROOT / "sql" / "analysis_queries.sql"
RESULTS = ROOT / "outputs" / "sql_results"
OUT = ROOT / "outputs"
DASH_DATA = ROOT / "docs" / "data.js"


def load_queries(path):
    """Split the .sql file on '-- name: xxx' markers."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\S+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def to_markdown(df):
    cols = list(df.columns)
    rows = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, float) and v.is_integer() and abs(v) >= 1000:
                cells.append(f"{int(v):,}")
            elif isinstance(v, int) and abs(v) >= 1000:
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def inr(x):
    """Format rupees in lakh / crore, the way Indian businesses report it."""
    if x >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.1f} L"
    return f"₹{x:,.0f}"


def write_insights(r):
    k = r["01_overall_kpis"].iloc[0]
    cour = r["03_courier_scorecard"].set_index("courier")
    best, worst = cour.index[0], cour.index[-1]
    fest = r["10_festive_vs_regular"].set_index("period")
    f, g = fest.loc["Festive (Oct-Nov)"], fest.loc["Regular (other months)"]
    sla = r["09_sla_vs_rating"].set_index("delivery")
    late, ontime = sla.loc["Late (SLA breached)"], sla.loc["On time"]
    pay = r["08_payment_mode_risk"].set_index("payment_mode")
    prepaid = pay.drop("COD")
    prepaid_cancel = (prepaid["cancel_rate_pct"] * prepaid["orders"]).sum() / prepaid["orders"].sum()
    prepaid_return = (prepaid["return_rate_pct"] * prepaid["orders"]).sum() / prepaid["orders"].sum()
    cat = r["04_category_performance"].set_index("category")
    top_cat = cat.index[0]
    fashion = cat.loc["Fashion"]
    fashion_reason = r["05_top_return_reason_by_category"].set_index("category").loc["Fashion"]
    reasons = r["06_return_reasons"]
    damaged = cour.sort_values("damaged_pct")
    least_damaged, most_damaged = damaged.index[0], damaged.index[-1]
    worst_city = r["07_city_performance"].sort_values("sla_breach_pct", ascending=False).iloc[0]

    lines = [
        "# Key findings and recommendations", "",
        "_All numbers are produced by `sql/analysis_queries.sql` on the cleaned data "
        f"({int(k.total_orders):,} orders, Jan-Dec 2025)._", "",
        "## Headline numbers", "",
        f"- **Net revenue:** {inr(k.net_revenue_inr)} from {int(k.total_orders):,} orders "
        f"and {int(k.unique_customers):,} customers",
        f"- **Average order value (delivered orders):** ₹{k.avg_order_value_inr:,.0f}",
        f"- **Average delivery time:** {k.avg_days_to_deliver} days from order",
        f"- **Late deliveries (SLA breach):** {k.sla_breach_pct}%",
        f"- **Return rate:** {k.return_rate_pct}%  |  **Cancellation rate:** {k.cancel_rate_pct}%",
        f"- **Average customer rating:** {k.avg_rating} / 5", "",
        "## Findings", "",
        f"1. **Festive season breaks the delivery promise.** In Oct-Nov the business handled "
        f"{int(f.orders_per_month):,} orders a month vs {int(g.orders_per_month):,} normally. Late deliveries jumped "
        f"from {g.sla_breach_pct}% to {f.sla_breach_pct}%, and time-to-ship went from {g.avg_days_to_ship} to "
        f"{f.avg_days_to_ship} days - the warehouse could not keep up.",
        f"2. **Courier choice makes a big difference.** {best} breaches the SLA on "
        f"{cour.loc[best, 'sla_breach_pct']}% of shipments; {worst} on {cour.loc[worst, 'sla_breach_pct']}% "
        f"({cour.loc[worst, 'avg_days_to_deliver']} days on average vs {cour.loc[best, 'avg_days_to_deliver']}). "
        f"Damage in transit is a separate problem: {most_damaged} has the highest damage rate "
        f"({damaged.loc[most_damaged, 'damaged_pct']}% of shipments come back damaged) vs "
        f"{damaged.loc[least_damaged, 'damaged_pct']}% for {least_damaged}.",
        f"3. **Late delivery costs ratings.** On-time orders average {ontime.avg_rating} stars; late ones "
        f"average {late.avg_rating}. {late.low_rating_pct}% of late orders get a 1-2 star rating vs "
        f"{ontime.low_rating_pct}% of on-time orders.",
        f"4. **Cash on Delivery is the riskiest payment mode.** COD orders are cancelled "
        f"{pay.loc['COD', 'cancel_rate_pct']}% of the time (prepaid: {prepaid_cancel:.1f}%) and returned "
        f"{pay.loc['COD', 'return_rate_pct']}% of the time (prepaid: {prepaid_return:.1f}%).",
        f"5. **Fashion drives returns.** Fashion has a {fashion.return_rate_pct}% return rate - the highest of any "
        f"category - and '{fashion_reason.top_reason}' explains {fashion_reason.share_of_category_returns_pct}% "
        f"of those returns. {top_cat} is the biggest revenue category "
        f"({cat.loc[top_cat, 'revenue_share_pct']}% of revenue).",
        f"6. **The top return reason overall is '{reasons.iloc[0].return_reason}'** "
        f"({reasons.iloc[0].share_pct}% of returns).",
        f"7. **{worst_city.city} has the worst delivery record** ({worst_city.sla_breach_pct}% late, "
        f"{worst_city.avg_days_to_deliver} days on average).", "",
        "## Recommendations", "",
        f"1. **Move volume away from {worst}.** Use it only where no other partner serves the pincode. "
        f"Shifting its shipments to {best} / the next-best partner should cut late deliveries noticeably. "
        f"Ask {most_damaged} for better packaging or a damage SLA.",
        "2. **Plan festive capacity in advance.** Add temporary packing staff and a second shift from late "
        "September, and show a longer delivery promise at checkout during sale weeks.",
        "3. **Nudge COD buyers to prepay.** A small prepaid discount or a COD handling fee, plus an order "
        "confirmation call/WhatsApp for high-value COD orders.",
        "4. **Fix Fashion sizing.** Add a size chart and 'fits true to size' feedback on product pages.",
        "5. **Track these weekly:** SLA breach % by courier, time-to-ship, return rate by category and COD "
        "cancellation rate. The dashboard in `docs/` does this.",
    ]
    (OUT / "insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Numbered findings / recommendations are shown on the dashboard too
    start_f, start_r = lines.index("## Findings"), lines.index("## Recommendations")
    strip = lambda ln: re.sub(r"^\d+\.\s*", "", ln)
    return {"findings": [strip(ln) for ln in lines[start_f + 2:start_r - 1]],
            "recommendations": [strip(ln) for ln in lines[start_r + 2:]]}


def write_dashboard_data(df, insights):
    """Compact row format so the web dashboard can filter in the browser."""
    dims = {
        "cities": sorted(df["city"].unique()),
        "categories": sorted(df["category"].unique()),
        "couriers": sorted(df["courier"].unique()),
        "payments": sorted(df["payment_mode"].unique()),
        "statuses": ["Delivered", "Returned", "Cancelled", "In Transit"],
        "reasons": sorted(df.loc[df["return_reason"].notna(), "return_reason"].unique()),
    }
    region = df.drop_duplicates("city").set_index("city")["region"].to_dict()
    tier = df.drop_duplicates("city").set_index("city")["city_tier"].astype(int).to_dict()
    idx = {k: {v: i for i, v in enumerate(vals)} for k, vals in dims.items()}

    rows = []
    for r in df.itertuples(index=False):
        rows.append([
            r.order_date,
            idx["cities"][r.city],
            idx["categories"][r.category],
            idx["couriers"][r.courier],
            idx["payments"][r.payment_mode],
            idx["statuses"][r.order_status],
            int(round(r.net_revenue)),
            -1 if pd.isna(r.days_to_deliver) else int(r.days_to_deliver),
            -1 if pd.isna(r.sla_breached) else int(r.sla_breached),
            0 if pd.isna(r.customer_rating) else int(r.customer_rating),
            -1 if pd.isna(r.return_reason) else idx["reasons"][r.return_reason],
            -1 if pd.isna(r.days_to_ship) else int(r.days_to_ship),
        ])
    payload = {
        **dims,
        "cityRegion": region,
        "cityTier": tier,
        "fields": ["date", "city", "category", "courier", "payment", "status", "revenue",
                   "deliverDays", "slaBreached", "rating", "reason", "shipDays"],
        "insights": insights,
        "rows": rows,
    }
    DASH_DATA.parent.mkdir(parents=True, exist_ok=True)
    DASH_DATA.write_text("// Generated by scripts/03_sql_analysis.py - do not edit by hand\n"
                         "window.ORDERS = " + json.dumps(payload, separators=(",", ":")) + ";\n",
                         encoding="utf-8")


def main():
    df = pd.read_csv(CLEAN)

    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    df.to_sql("orders", con, index=False)
    con.execute("CREATE INDEX idx_orders_month ON orders(order_month)")
    con.execute("CREATE INDEX idx_orders_courier ON orders(courier)")

    RESULTS.mkdir(parents=True, exist_ok=True)
    results, md = {}, ["# SQL results", "",
                       "Generated by `scripts/03_sql_analysis.py` from `sql/analysis_queries.sql`.", ""]
    for name, query in load_queries(SQL).items():
        res = pd.read_sql_query(query, con)
        results[name] = res
        res.to_csv(RESULTS / f"{name}.csv", index=False)
        comment = next((ln[3:] for ln in query.splitlines() if ln.startswith("-- ")), "")
        md += [f"## {name}", "", f"_{comment}_", "", to_markdown(res), ""]
    con.close()

    (OUT / "sql_results.md").write_text("\n".join(md), encoding="utf-8")
    insights = write_insights(results)
    write_dashboard_data(df, insights)
    print(f"[3/3] Ran {len(results)} SQL queries -> outputs/sql_results/, outputs/insights.md, docs/data.js")


if __name__ == "__main__":
    main()
