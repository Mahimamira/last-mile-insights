"""
Step 1 - Generate the raw dataset.

Creates a realistic (synthetic) e-commerce order file for 2025 with the kinds of
problems you find in real operations exports: duplicate rows, mixed date formats,
inconsistent city / payment labels, prices stored as text, missing values and a
few invalid records. Step 2 cleans all of this up.

The random seed is fixed, so every run produces the same file.
Output: data/raw/orders_raw.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "orders_raw.csv"

rng = np.random.default_rng(42)
N_ORDERS = 6000

# city -> (region, tier, share of orders)
CITIES = {
    "Chennai":   ("South", 1, 0.15),
    "Bengaluru": ("South", 1, 0.16),
    "Hyderabad": ("South", 1, 0.11),
    "Kochi":     ("South", 2, 0.04),
    "Mumbai":    ("West", 1, 0.14),
    "Pune":      ("West", 2, 0.07),
    "Ahmedabad": ("West", 2, 0.05),
    "Delhi":     ("North", 1, 0.13),
    "Jaipur":    ("North", 2, 0.05),
    "Kolkata":   ("East", 1, 0.07),
    "Bhubaneswar": ("East", 2, 0.03),
}

# category -> (price low, price high, base return rate)
CATEGORIES = {
    "Electronics":    (899, 24999, 0.07),
    "Fashion":        (299, 2999, 0.16),
    "Home & Kitchen": (249, 5999, 0.06),
    "Beauty":         (149, 1999, 0.05),
    "Books":          (149, 899, 0.02),
    "Grocery":        (99, 1499, 0.03),
}
CATEGORY_SHARE = [0.20, 0.24, 0.18, 0.13, 0.10, 0.15]

# courier -> (mean transit days, share of shipments, damage risk)
COURIERS = {
    "BlueDart":     (2.0, 0.22, 0.010),
    "Delhivery":    (2.6, 0.30, 0.015),
    "Ecom Express": (3.0, 0.18, 0.020),
    "XpressBees":   (2.8, 0.18, 0.018),
    "India Post":   (4.6, 0.12, 0.035),
}

PAYMENTS = {"UPI": 0.42, "Card": 0.20, "COD": 0.24, "Net Banking": 0.06, "Wallet": 0.08}

# More orders in Oct-Nov (festive season / Diwali sale)
MONTH_WEIGHT = np.array([0.95, 0.85, 0.95, 0.9, 0.95, 0.9, 1.0, 1.05, 1.1, 1.6, 1.7, 1.25])


def pick(options, weights, size):
    weights = np.asarray(weights, dtype=float)
    return rng.choice(list(options), size=size, p=weights / weights.sum())


def make_dates(size):
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
    w = MONTH_WEIGHT[days.month - 1] * np.where(days.day_of_week >= 5, 1.15, 1.0)
    return pd.to_datetime(rng.choice(days.values, size=size, p=w / w.sum()))


def build_clean_orders():
    n = N_ORDERS
    df = pd.DataFrame({
        "order_date": make_dates(n),
        "customer_id": [f"CUST-{x}" for x in rng.integers(10001, 13500, n)],
        "city": pick(CITIES, [v[2] for v in CITIES.values()], n),
        "category": pick(CATEGORIES, CATEGORY_SHARE, n),
        "payment_mode": pick(PAYMENTS, list(PAYMENTS.values()), n),
        "courier": pick(COURIERS, [v[1] for v in COURIERS.values()], n),
    })
    df = df.sort_values("order_date").reset_index(drop=True)
    df.insert(0, "order_id", [f"ORD-{100001 + i}" for i in range(n)])

    df["region"] = df["city"].map(lambda c: CITIES[c][0])
    tier = df["city"].map(lambda c: CITIES[c][1])
    festive = df["order_date"].dt.month.isin([10, 11])

    # Price, quantity, discount
    lo = df["category"].map(lambda c: CATEGORIES[c][0])
    hi = df["category"].map(lambda c: CATEGORIES[c][1])
    u = rng.beta(1.6, 4.0, n)  # most items are at the cheaper end
    df["unit_price"] = (lo + u * (hi - lo)).round(-1) - 1
    df["quantity"] = rng.choice([1, 1, 1, 1, 2, 2, 3, 4], n)
    base_disc = rng.choice([0, 0, 5, 10, 15, 20], n)
    df["discount_pct"] = np.where(festive, base_disc + rng.choice([5, 10, 15], n), base_disc)

    # Fulfilment timeline
    ship_days = rng.choice([0, 1, 1, 1, 2, 2, 3], n) + festive.astype(int)
    courier_mean = df["courier"].map(lambda c: COURIERS[c][0])
    transit = (courier_mean
               + (tier == 2) * 1.0
               + (df["region"] == "East") * 0.8
               + festive * 1.0
               + rng.gamma(2.0, 0.55, n) - 1.1)
    transit = np.clip(np.round(transit), 1, None).astype(int)
    df["ship_date"] = df["order_date"] + pd.to_timedelta(ship_days, unit="D")
    df["delivery_date"] = df["ship_date"] + pd.to_timedelta(transit, unit="D")
    sla_days = np.where(tier == 1, 5, 7)
    late = ((df["delivery_date"] - df["order_date"]).dt.days > sla_days).to_numpy()

    # Status
    status = np.full(n, "Delivered", dtype=object)
    cancel_p = np.where(df["payment_mode"] == "COD", 0.07, 0.03)
    cancelled = rng.random(n) < cancel_p
    ret_p = (df["category"].map(lambda c: CATEGORIES[c][2])
             + (df["payment_mode"] == "COD") * 0.06
             + late * 0.04
             + df["courier"].map(lambda c: COURIERS[c][2])).to_numpy()
    returned = (rng.random(n) < ret_p) & ~cancelled
    status[returned] = "Returned"
    status[cancelled] = "Cancelled"
    in_transit = ((df["delivery_date"] > pd.Timestamp("2025-12-31")) & ~cancelled).to_numpy()
    status[in_transit] = "In Transit"
    df["order_status"] = status

    # Return reasons
    reasons = np.full(n, "", dtype=object)
    for i in np.where(df["order_status"] == "Returned")[0]:
        cat, cour = df.at[i, "category"], df.at[i, "courier"]
        opts = {"Damaged in transit": 0.12 + COURIERS[cour][2] * 4,
                "Wrong item delivered": 0.10,
                "Changed mind": 0.16,
                "Late delivery": 0.25 if late[i] else 0.03}
        if cat == "Fashion":
            opts["Size / fit issue"] = 0.55
        if cat in ("Electronics", "Home & Kitchen"):
            opts["Defective product"] = 0.35
        if cat in ("Beauty", "Grocery"):
            opts["Expired / near expiry"] = 0.12
        reasons[i] = pick(opts, list(opts.values()), 1)[0]
    df["return_reason"] = reasons

    # Customer rating (only for completed orders)
    is_ret = (df["order_status"] == "Returned").to_numpy()
    r = 4.4 - late * 1.1 - is_ret * 1.4 + rng.normal(0, 0.7, n)
    rating = np.clip(np.round(r), 1, 5)
    rating = np.where(df["order_status"].isin(["Delivered", "Returned"]), rating, np.nan)
    rating[rng.random(n) < 0.18] = np.nan  # many customers skip the rating
    df["customer_rating"] = rating

    # Cancelled / in-transit orders have no delivery yet
    df.loc[df["order_status"] == "Cancelled", ["ship_date", "delivery_date"]] = pd.NaT
    df.loc[df["order_status"] == "In Transit", "delivery_date"] = pd.NaT
    return df


def make_messy(df):
    """Introduce the problems a real export would have."""
    df = df.copy()
    n = len(df)

    # 1. Dates in three different formats
    def fmt(series):
        out = []
        for d, r in zip(series, rng.random(len(series))):
            if pd.isna(d):
                out.append("")
            elif r < 0.70:
                out.append(d.strftime("%Y-%m-%d"))
            elif r < 0.90:
                out.append(d.strftime("%d/%m/%Y"))
            else:
                out.append(d.strftime("%d-%b-%Y"))
        return out

    for col in ["order_date", "ship_date", "delivery_date"]:
        df[col] = fmt(df[col])

    # 2. Inconsistent city names
    aliases = {"Bengaluru": ["Bangalore", "bangalore", "BENGALURU"],
               "Mumbai": ["Bombay", "mumbai", "MUMBAI "],
               "Delhi": ["New Delhi", "delhi"],
               "Chennai": [" Chennai", "chennai", "CHENNAI"],
               "Hyderabad": ["hyderabad", "Hyderabad "],
               "Kolkata": ["Calcutta", "kolkata"]}
    for i in np.where(rng.random(n) < 0.12)[0]:
        c = df.at[i, "city"]
        if c in aliases:
            df.at[i, "city"] = rng.choice(aliases[c])

    # 3. Missing region (can be recovered from city)
    df.loc[rng.random(n) < 0.06, "region"] = ""

    # 4. Inconsistent payment labels
    pay_alias = {"UPI": ["upi", "UPI ", "Upi"], "COD": ["Cash on Delivery", "cod", "C.O.D"],
                 "Card": ["Credit Card", "Debit Card", "card"], "Net Banking": ["NetBanking", "net banking"],
                 "Wallet": ["Paytm Wallet", "wallet"]}
    for i in np.where(rng.random(n) < 0.15)[0]:
        df.at[i, "payment_mode"] = rng.choice(pay_alias[df.at[i, "payment_mode"]])

    # 5. Prices exported as text with rupee symbol and commas
    df["unit_price"] = df["unit_price"].astype(object)
    for i in np.where(rng.random(n) < 0.08)[0]:
        df.at[i, "unit_price"] = f"₹{df.at[i, 'unit_price']:,.2f}"

    # 6. Invalid quantities (0 or negative - data entry errors)
    bad_q = rng.choice(n, 28, replace=False)
    df.loc[bad_q, "quantity"] = rng.choice([0, -1, -2], len(bad_q))

    # 7. Missing city (cannot be recovered)
    df.loc[rng.choice(n, 22, replace=False), "city"] = ""

    # 8. Delivery date typed before the order date
    bad_d = rng.choice(np.where(df["delivery_date"] != "")[0], 9, replace=False)
    df.loc[bad_d, "delivery_date"] = "2024-12-30"

    # 9. Exact duplicate rows (system exported some orders twice)
    dupes = df.sample(frac=0.025, random_state=7)
    df = pd.concat([df, dupes]).sample(frac=1, random_state=11).reset_index(drop=True)

    # Rating stored as text with blanks
    df["customer_rating"] = df["customer_rating"].map(lambda x: "" if pd.isna(x) else str(int(x)))
    return df


def main():
    clean = build_clean_orders()
    raw = make_messy(clean)
    cols = ["order_id", "order_date", "ship_date", "delivery_date", "customer_id", "city", "region",
            "category", "quantity", "unit_price", "discount_pct", "payment_mode", "courier",
            "order_status", "return_reason", "customer_rating"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw[cols].to_csv(OUT, index=False)
    print(f"[1/3] Raw data written: {OUT.relative_to(ROOT)} ({len(raw):,} rows)")


if __name__ == "__main__":
    main()
