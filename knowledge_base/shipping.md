# Shipping Policy

## Policy Overview
This policy covers shipping-related queries: tracking, delivery delays, and missing shipments.

### Rule 1: Normal Shipping Window — Wait and Track
If the order has been shipped/dispatched within the last 7 days, it is within the normal delivery window. Advise the customer to wait and track their shipment.
- **Conditions**: order_status is "shipped", days_since_dispatch ≤ 7
- **Action**: WAIT_AND_TRACK
- **Confidence guidance**: High (≥0.85).

### Rule 2: Delayed Shipment — Open Investigation
If the order has been shipped/dispatched more than 7 days ago and has not been delivered (or tracking hasn't updated), open a shipping investigation to locate the package.
- **Conditions**: order_status is "shipped", days_since_dispatch > 7
- **Action**: OPEN_SHIPPING_INVESTIGATION
- **Confidence guidance**: High (≥0.85) when days_since_dispatch clearly exceeds 7.
