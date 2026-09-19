# Defective Products Policy

## Policy Overview
This policy covers products that are not physically damaged but exhibit manufacturing defects or malfunction after delivery (e.g., motor doesn't work, screen flickers, software crashes). This is distinct from damaged goods (visibly broken on arrival).

### Rule 1: Defective Product With Evidence (Within 15 Days)
If the product is confirmed defective AND the customer has evidence (video, photos, error logs) AND it was delivered within the last 15 days, approve an immediate replacement.
- **Conditions**: order_status is "delivered", days_since_delivery ≤ 15, customer provides/mentions evidence of defect
- **Action**: APPROVE_REPLACEMENT
- **Confidence guidance**: High (≥0.85) when evidence is confirmed.

### Rule 2: Defective Product Without Evidence
If the customer reports a possible defect but is unsure or has not provided evidence, request defect evidence (photos, videos, or detailed description of the malfunction) before processing.
- **Conditions**: order_status is "delivered", customer describes issue but no clear evidence
- **Action**: REQUEST_DEFECT_EVIDENCE
- **Confidence guidance**: Medium (0.7–0.85).

### Rule 3: Defective Product (15–30 Days After Delivery)
If the product is reported defective between 15 and 30 days after delivery and evidence is available, offer a replacement or refund at the customer's choice.
- **Conditions**: 15 < days_since_delivery ≤ 30, evidence available
- **Action**: OFFER_REPLACEMENT_OR_REFUND
- **Confidence guidance**: Medium-High (0.75–0.85).

### Rule 4: Defective Product Beyond 30 Days
If the defect is reported more than 30 days after delivery, the item is outside the defect reporting window.
- **Conditions**: days_since_delivery > 30
- **Action**: REJECT_OUTSIDE_WINDOW
- **Confidence guidance**: High (≥0.85).
