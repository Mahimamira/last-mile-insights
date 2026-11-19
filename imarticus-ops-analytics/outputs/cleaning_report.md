# Data cleaning report

Raw rows: **6,150**  ->  Clean rows: **5,941** (209 removed, 3.4%)

| # | Step | Rows before | Rows after | Note |
|---|---|---:|---:|---|
| 1 | Remove exact duplicate rows | 6,150 | 6,000 | Same order exported twice by the source system |
| 2 | Standardise city and payment labels | 6,000 | 6,000 | e.g. 'bangalore' / 'BENGALURU' -> Bengaluru, 'Cash on Delivery' / 'cod' -> COD |
| 3 | Drop rows with missing city | 6,000 | 5,978 | City is needed for region and delivery SLA |
| 4 | Fill missing region from city | 5,978 | 5,978 | 336 blank regions recovered |
| 5 | Convert prices, numbers and dates | 5,978 | 5,978 | Removed ₹ and commas from prices; parsed 3 date formats into one |
| 6 | Drop rows with quantity <= 0 | 5,978 | 5,950 | Data-entry errors |
| 7 | Drop rows where delivery date is before order date | 5,950 | 5,941 | Impossible timeline |
| 8 | Check order_id is unique | 5,941 | 5,941 | 0 duplicate IDs remaining |
| 9 | Add derived columns | 5,941 | 5,941 | order_month, net_revenue, days_to_ship, days_to_deliver, sla_days, sla_breached, is_returned ... |

## Missing values kept on purpose

- `customer_rating` is blank when the customer did not rate. It is **not** filled in, because a made-up rating would bias the average.
- `ship_date` / `delivery_date` are blank for cancelled and in-transit orders.

Missing ratings: 1,303 (21.9% of orders)
