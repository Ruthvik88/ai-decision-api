# Returns Policy

## Policy Overview
This policy covers general product return requests. The decision depends on the product type, whether the item has been opened/used, and how many days have passed since delivery.

### Rule 1: Return Within Window — Unopened Item
If the customer wants to return a non-food item that is still unopened/sealed AND it was delivered within the last 15 days, approve the return.
- **Conditions**: product_type is NOT "food", opened_status is "unopened" or "sealed", days_since_delivery ≤ 15
- **Action**: APPROVE_RETURN
- **Confidence guidance**: High (≥0.9).

### Rule 2: Reject Opened Item Return
If the customer has already opened or used the item (opened_status is "opened" or "used"), the return cannot be accepted under the standard return policy. The customer may be directed to the defective products policy if there is a defect.
- **Conditions**: opened_status is "opened" or "used", no defect reported
- **Action**: REJECT_OPENED_ITEM
- **Confidence guidance**: High (≥0.85).

### Rule 3: Reject Food Item Return
Food and perishable items cannot be returned due to health and safety regulations, regardless of whether they are opened or unopened.
- **Conditions**: product_type is "food" or "perishable"
- **Action**: REJECT_FOOD_RETURN
- **Confidence guidance**: High (≥0.9).

### Rule 4: Return Outside Window
If the item was delivered more than 15 days ago, it is outside the return window and cannot be accepted.
- **Conditions**: days_since_delivery > 15
- **Action**: REJECT_OUTSIDE_WINDOW
- **Confidence guidance**: High (≥0.85).
