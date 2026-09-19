# Damaged Goods Policy

## Policy Overview
This policy covers items that arrive physically damaged during shipping (crushed packaging, broken product, visible damage upon delivery). This is distinct from defective products (which appear undamaged but malfunction).

### Rule 1: Damaged Item With Photo Evidence
If an item was delivered damaged AND the customer has already provided or mentions having photographic/video evidence of the damage, approve an immediate refund or replacement at the customer's choice. This applies regardless of order value or product type (except food items, which fall under the returns policy).
- **Conditions**: order_status is "delivered", days_since_delivery ≤ 7, customer mentions photos/evidence taken
- **Action**: APPROVE_REFUND_OR_REPLACEMENT
- **Confidence guidance**: High (≥0.85) when photos are confirmed available.

### Rule 2: Damaged Item Without Photo Evidence
If an item was delivered damaged BUT the customer has NOT provided or mentioned having photographic evidence, request photos before processing. This is required for insurance claims and quality control.
- **Conditions**: order_status is "delivered", days_since_delivery ≤ 7, no mention of photos/evidence
- **Action**: REQUEST_PHOTOS
- **Confidence guidance**: High (≥0.85) when damage is described but no evidence mentioned.

### Rule 3: Damage Reported Too Late
If the customer reports damage more than 7 days after delivery, the claim may be rejected as outside the damage reporting window.
- **Conditions**: days_since_delivery > 7
- **Action**: REJECT_OUTSIDE_WINDOW
- **Confidence guidance**: Medium (0.7–0.85).
