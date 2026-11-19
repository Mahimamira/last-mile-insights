# Key findings and recommendations

_All numbers are produced by `sql/analysis_queries.sql` on the cleaned data (5,941 orders, Jan-Dec 2025)._

## Headline numbers

- **Net revenue:** ₹2.01 Cr from 5,941 orders and 2,864 customers
- **Average order value (delivered orders):** ₹4,067
- **Average delivery time:** 5.05 days from order
- **Late deliveries (SLA breach):** 27.0%
- **Return rate:** 11.3%  |  **Cancellation rate:** 4.1%
- **Average customer rating:** 3.89 / 5

## Findings

1. **Festive season breaks the delivery promise.** In Oct-Nov the business handled 729 orders a month vs 448 normally. Late deliveries jumped from 15.5% to 61.3%, and time-to-ship went from 1.42 to 2.42 days - the warehouse could not keep up.
2. **Courier choice makes a big difference.** BlueDart breaches the SLA on 12.1% of shipments; India Post on 63.2% (6.79 days on average vs 4.2). Damage in transit is a separate problem: Ecom Express has the highest damage rate (3.6% of shipments come back damaged) vs 1.8% for BlueDart.
3. **Late delivery costs ratings.** On-time orders average 4.19 stars; late ones average 3.07. 23.2% of late orders get a 1-2 star rating vs 2.8% of on-time orders.
4. **Cash on Delivery is the riskiest payment mode.** COD orders are cancelled 7.7% of the time (prepaid: 2.9%) and returned 15.0% of the time (prepaid: 10.0%).
5. **Fashion drives returns.** Fashion has a 20.4% return rate - the highest of any category - and 'Size / fit issue' explains 50.7% of those returns. Electronics is the biggest revenue category (67.4% of revenue).
6. **The top return reason overall is 'Damaged in transit'** (22.2% of returns).
7. **Kolkata has the worst delivery record** (51.2% late, 5.61 days on average).

## Recommendations

1. **Move volume away from India Post.** Use it only where no other partner serves the pincode. Shifting its shipments to BlueDart / the next-best partner should cut late deliveries noticeably. Ask Ecom Express for better packaging or a damage SLA.
2. **Plan festive capacity in advance.** Add temporary packing staff and a second shift from late September, and show a longer delivery promise at checkout during sale weeks.
3. **Nudge COD buyers to prepay.** A small prepaid discount or a COD handling fee, plus an order confirmation call/WhatsApp for high-value COD orders.
4. **Fix Fashion sizing.** Add a size chart and 'fits true to size' feedback on product pages.
5. **Track these weekly:** SLA breach % by courier, time-to-ship, return rate by category and COD cancellation rate. The dashboard in `docs/` does this.
