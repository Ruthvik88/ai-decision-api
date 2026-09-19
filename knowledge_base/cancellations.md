# Cancellation Policy

## Policy Overview
This policy covers order cancellation requests. The decision depends on whether the order has been dispatched.

### Rule 1: Cancel Before Dispatch
If the order status is "processing" or "pending" (i.e., it has NOT been shipped/dispatched yet), the customer is entitled to a full cancellation and refund, regardless of order value or product type.
- **Action**: CANCEL_AND_REFUND
- **Confidence guidance**: High (≥0.9) when order_status is clearly "processing" or "pending".

### Rule 2: Cannot Cancel After Dispatch
If the order status is "shipped" or "dispatched" (i.e., the order has already been handed to the courier), the order cannot be cancelled. The customer must wait for delivery and then initiate a return if needed.
- **Action**: CANNOT_CANCEL_AFTER_DISPATCH
- **Confidence guidance**: High (≥0.9) when order_status is "shipped" and days_since_dispatch is provided.
