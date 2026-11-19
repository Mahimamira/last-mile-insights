"""
Step 2 - Clean the raw data with Pandas.

Every cleaning step is logged with the row count before and after, so the
final numbers can be traced back to the raw file.

Input : data/raw/orders_raw.csv
Output: data/clean/orders_clean.csv
        outputs/cleaning_report.md
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "orders_raw.csv"
CLEAN = ROOT / "data" / "clean" / "orders_clean.csv"
REPORT = ROOT / "outputs" / "cleaning_report.md"

CITY_FIX = {"bangalore": "Bengaluru", "bombay": "Mumbai", "new delhi": "Delhi", "calcutta": "Kolkata"}
CITY_REGION = {"Chennai": "South", "Bengaluru": "South", "Hyderabad": "South", "Kochi": "South",
               "Mumbai": "West", "Pune": "West", "Ahmedabad": "West",
               "Delhi": "North", "Jaipur": "North",
               "Kolkata": "East", "Bhubaneswar": "East"}
TIER_1 = {"Chennai", "Bengaluru", "Hyderabad", "Mumbai", "Delhi", "Kolkata"}
PAYMENT_FIX = {"upi": "UPI", "cod": "COD", "cash on delivery": "COD", "c.o.d": "COD",
               "card": "Card", "credit card": "Card", "debit card": "Card",
               "net banking": "Net Banking", "netbanking": "Net Banking",
               "wallet": "Wallet", "paytm wallet": "Wallet"}

log = []


def record(step, before, after, note):
    log.append((step, before, after, note))


def parse_mixed_dates(s):
    """Dates come as 2025-03-14, 14/03/2025 or 14-Mar-2025. Try each format in turn."""
    s = s.fillna("").astype(str).str.strip()
    out = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    for fmt in ("%d/%m/%Y", "%d-%b-%Y"):
        out = out.fillna(pd.to_datetime(s, format=fmt, errors="coerce"))
    return out


def main():
    df = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    n0 = len(df)

    # 1. Remove exact duplicate rows
    before = len(df)
    df = df.drop_duplicates()
    record("Remove exact duplicate rows", before, len(df), "Same order exported twice by the source system")

    # 2. Standardise text columns
    for col in df.columns:
        df[col] = df[col].str.strip()
    city_key = df["city"].str.lower()
    df["city"] = city_key.map(CITY_FIX).fillna(df["city"].str.title())
    df["payment_mode"] = df["payment_mode"].str.lower().map(PAYMENT_FIX).fillna(df["payment_mode"])
    record("Standardise city and payment labels", len(df), len(df),
           "e.g. 'bangalore' / 'BENGALURU' -> Bengaluru, 'Cash on Delivery' / 'cod' -> COD")

    # 3. Drop rows with no city (region and SLA cannot be worked out)
    before = len(df)
    df = df[df["city"] != ""]
    record("Drop rows with missing city", before, len(df), "City is needed for region and delivery SLA")

    # 4. Fill missing region from the city
    missing_region = (df["region"] == "").sum()
    df["region"] = df["city"].map(CITY_REGION)
    record("Fill missing region from city", len(df), len(df), f"{missing_region} blank regions recovered")

    # 5. Convert data types
    df["unit_price"] = pd.to_numeric(df["unit_price"].str.replace(r"[₹,]", "", regex=True))
    df["quantity"] = pd.to_numeric(df["quantity"]).astype(int)
    df["discount_pct"] = pd.to_numeric(df["discount_pct"]).astype(int)
    df["customer_rating"] = pd.to_numeric(df["customer_rating"].replace("", np.nan))
    for col in ["order_date", "ship_date", "delivery_date"]:
        df[col] = parse_mixed_dates(df[col])
    record("Convert prices, numbers and dates", len(df), len(df),
           "Removed ₹ and commas from prices; parsed 3 date formats into one")

    # 6. Drop invalid quantities
    before = len(df)
    df = df[df["quantity"] > 0]
    record("Drop rows with quantity <= 0", before, len(df), "Data-entry errors")

    # 7. Delivery before order date is impossible -> drop
    before = len(df)
    df = df[~(df["delivery_date"] < df["order_date"])]
    record("Drop rows where delivery date is before order date", before, len(df), "Impossible timeline")

    # 8. Any duplicate order IDs left?
    dup_ids = df["order_id"].duplicated().sum()
    record("Check order_id is unique", len(df), len(df), f"{dup_ids} duplicate IDs remaining")

    # 9. Derived columns used in the analysis
    df["order_month"] = df["order_date"].dt.strftime("%Y-%m")
    df["gross_amount"] = df["unit_price"] * df["quantity"]
    df["net_revenue"] = (df["gross_amount"] * (1 - df["discount_pct"] / 100)).round(2)
    # Revenue only counts if the order was kept by the customer
    df.loc[df["order_status"].isin(["Cancelled", "Returned"]), "net_revenue"] = 0.0
    df["city_tier"] = np.where(df["city"].isin(TIER_1), 1, 2)
    df["sla_days"] = np.where(df["city_tier"] == 1, 5, 7)
    df["days_to_ship"] = (df["ship_date"] - df["order_date"]).dt.days
    df["days_to_deliver"] = (df["delivery_date"] - df["order_date"]).dt.days
    df["sla_breached"] = np.where(df["days_to_deliver"].isna(), np.nan,
                                  (df["days_to_deliver"] > df["sla_days"]).astype(float))
    df["is_returned"] = (df["order_status"] == "Returned").astype(int)
    df["festive_season"] = df["order_date"].dt.month.isin([10, 11]).astype(int)
    record("Add derived columns", len(df), len(df),
           "order_month, net_revenue, days_to_ship, days_to_deliver, sla_days, sla_breached, is_returned ...")

    df = df.sort_values("order_date").reset_index(drop=True)
    for col in ["order_date", "ship_date", "delivery_date"]:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN, index=False)

    # Report
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Data cleaning report", "",
             f"Raw rows: **{n0:,}**  ->  Clean rows: **{len(df):,}** "
             f"({n0 - len(df):,} removed, {(n0 - len(df)) / n0:.1%})", "",
             "| # | Step | Rows before | Rows after | Note |", "|---|---|---:|---:|---|"]
    for i, (step, b, a, note) in enumerate(log, 1):
        lines.append(f"| {i} | {step} | {b:,} | {a:,} | {note} |")
    lines += ["", "## Missing values kept on purpose", "",
              "- `customer_rating` is blank when the customer did not rate. It is **not** filled in, "
              "because a made-up rating would bias the average.",
              "- `ship_date` / `delivery_date` are blank for cancelled and in-transit orders.", "",
              f"Missing ratings: {df['customer_rating'].isna().sum():,} "
              f"({df['customer_rating'].isna().mean():.1%} of orders)"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[2/3] Clean data written: {CLEAN.relative_to(ROOT)} ({len(df):,} rows, {n0 - len(df)} removed)")


if __name__ == "__main__":
    main()
