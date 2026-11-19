-- =====================================================================
-- Order Operations Analysis - SQL queries (SQLite)
-- Table: orders  (loaded from data/clean/orders_clean.csv)
-- Each query starts with "-- name: <query_name>". scripts/03_sql_analysis.py
-- runs them in order and saves each result to outputs/sql_results/<name>.csv
-- =====================================================================


-- name: 01_overall_kpis
-- Headline numbers for the whole year
SELECT
    COUNT(*)                                                    AS total_orders,
    COUNT(DISTINCT customer_id)                                 AS unique_customers,
    ROUND(SUM(net_revenue), 0)                                  AS net_revenue_inr,
    ROUND(SUM(net_revenue) / SUM(order_status = 'Delivered'), 0) AS avg_order_value_inr,
    ROUND(AVG(days_to_deliver), 2)                              AS avg_days_to_deliver,
    ROUND(100.0 * AVG(sla_breached), 1)                         AS sla_breach_pct,
    ROUND(100.0 * AVG(order_status = 'Returned'), 1)            AS return_rate_pct,
    ROUND(100.0 * AVG(order_status = 'Cancelled'), 1)           AS cancel_rate_pct,
    ROUND(AVG(customer_rating), 2)                              AS avg_rating
FROM orders;


-- name: 02_monthly_trend
-- Volume, revenue and delivery performance by month
SELECT
    order_month,
    COUNT(*)                              AS orders,
    ROUND(SUM(net_revenue), 0)            AS net_revenue_inr,
    ROUND(AVG(days_to_deliver), 2)        AS avg_days_to_deliver,
    ROUND(100.0 * AVG(sla_breached), 1)   AS sla_breach_pct,
    ROUND(100.0 * AVG(is_returned), 1)    AS return_rate_pct
FROM orders
GROUP BY order_month
ORDER BY order_month;


-- name: 03_courier_scorecard
-- Which delivery partner performs best? (delivered + returned shipments only)
SELECT
    courier,
    COUNT(*)                                                       AS shipments,
    ROUND(AVG(days_to_deliver), 2)                                 AS avg_days_to_deliver,
    ROUND(100.0 * AVG(sla_breached), 1)                            AS sla_breach_pct,
    ROUND(100.0 * AVG(is_returned), 1)                             AS return_rate_pct,
    SUM(return_reason = 'Damaged in transit')                      AS damaged_in_transit,
    ROUND(100.0 * AVG(COALESCE(return_reason, '') = 'Damaged in transit'), 1) AS damaged_pct,
    ROUND(AVG(customer_rating), 2)                                 AS avg_rating,
    RANK() OVER (ORDER BY AVG(sla_breached))                       AS sla_rank
FROM orders
WHERE days_to_deliver IS NOT NULL
GROUP BY courier
ORDER BY sla_rank;


-- name: 04_category_performance
-- Revenue and returns by product category
SELECT
    category,
    COUNT(*)                                  AS orders,
    ROUND(SUM(net_revenue), 0)                AS net_revenue_inr,
    ROUND(100.0 * SUM(net_revenue) / (SELECT SUM(net_revenue) FROM orders), 1) AS revenue_share_pct,
    ROUND(100.0 * AVG(is_returned), 1)        AS return_rate_pct,
    ROUND(AVG(customer_rating), 2)            AS avg_rating
FROM orders
GROUP BY category
ORDER BY net_revenue_inr DESC;


-- name: 05_top_return_reason_by_category
-- The single most common return reason in each category
WITH reason_counts AS (
    SELECT category, return_reason, COUNT(*) AS returns,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY COUNT(*) DESC) AS rn,
           SUM(COUNT(*)) OVER (PARTITION BY category)                     AS category_returns
    FROM orders
    WHERE order_status = 'Returned'
    GROUP BY category, return_reason
)
SELECT category, return_reason AS top_reason, returns,
       ROUND(100.0 * returns / category_returns, 1) AS share_of_category_returns_pct
FROM reason_counts
WHERE rn = 1
ORDER BY returns DESC;


-- name: 06_return_reasons
-- Overall return reasons
SELECT
    return_reason,
    COUNT(*)                                                                  AS returns,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                        AS share_pct
FROM orders
WHERE order_status = 'Returned'
GROUP BY return_reason
ORDER BY returns DESC;


-- name: 07_city_performance
-- City-level operations view, ranked by revenue
SELECT
    city,
    region,
    CASE city_tier WHEN 1 THEN 'Tier 1' ELSE 'Tier 2' END AS tier,
    COUNT(*)                                   AS orders,
    ROUND(SUM(net_revenue), 0)                 AS net_revenue_inr,
    ROUND(AVG(days_to_deliver), 2)             AS avg_days_to_deliver,
    ROUND(100.0 * AVG(sla_breached), 1)        AS sla_breach_pct,
    RANK() OVER (ORDER BY SUM(net_revenue) DESC) AS revenue_rank
FROM orders
GROUP BY city, region, city_tier
ORDER BY revenue_rank;


-- name: 08_payment_mode_risk
-- Cash on Delivery vs prepaid: cancellations and returns
SELECT
    payment_mode,
    COUNT(*)                                            AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS order_share_pct,
    ROUND(100.0 * AVG(order_status = 'Cancelled'), 1)   AS cancel_rate_pct,
    ROUND(100.0 * AVG(order_status = 'Returned'), 1)    AS return_rate_pct
FROM orders
GROUP BY payment_mode
ORDER BY orders DESC;


-- name: 09_sla_vs_rating
-- Does a late delivery hurt the customer rating?
SELECT
    CASE sla_breached WHEN 1 THEN 'Late (SLA breached)' ELSE 'On time' END AS delivery,
    COUNT(*)                          AS orders,
    COUNT(customer_rating)            AS rated_orders,
    ROUND(AVG(customer_rating), 2)    AS avg_rating,
    ROUND(100.0 * AVG(customer_rating <= 2), 1) AS low_rating_pct,
    ROUND(100.0 * AVG(is_returned), 1) AS return_rate_pct
FROM orders
WHERE sla_breached IS NOT NULL
GROUP BY sla_breached;


-- name: 10_festive_vs_regular
-- Festive season (Oct-Nov) load vs the rest of the year
SELECT
    CASE festive_season WHEN 1 THEN 'Festive (Oct-Nov)' ELSE 'Regular (other months)' END AS period,
    COUNT(DISTINCT order_month)                      AS months,
    ROUND(1.0 * COUNT(*) / COUNT(DISTINCT order_month), 0) AS orders_per_month,
    ROUND(AVG(days_to_ship), 2)                      AS avg_days_to_ship,
    ROUND(AVG(days_to_deliver), 2)                   AS avg_days_to_deliver,
    ROUND(100.0 * AVG(sla_breached), 1)              AS sla_breach_pct
FROM orders
GROUP BY festive_season;


-- name: 11_courier_by_region_breach
-- SLA breach % for every courier in every region (for routing decisions)
SELECT
    region,
    courier,
    COUNT(*)                            AS shipments,
    ROUND(100.0 * AVG(sla_breached), 1) AS sla_breach_pct
FROM orders
WHERE sla_breached IS NOT NULL
GROUP BY region, courier
ORDER BY region, sla_breach_pct;


-- name: 12_repeat_customers
-- How many customers ordered more than once?
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders
    FROM orders
    GROUP BY customer_id
)
SELECT
    CASE WHEN orders = 1 THEN '1 order'
         WHEN orders = 2 THEN '2 orders'
         WHEN orders BETWEEN 3 AND 4 THEN '3-4 orders'
         ELSE '5+ orders' END                       AS bucket,
    COUNT(*)                                        AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
FROM per_customer
GROUP BY bucket
ORDER BY MIN(orders);
