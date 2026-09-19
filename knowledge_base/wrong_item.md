# Wrong Item Policy

## Policy Overview
This policy covers cases where the customer received a different item than what they ordered.

### Rule 1: Wrong Item Received
If the customer received a completely different item than what they ordered (wrong product, wrong colour, wrong size that doesn't match the order), send the correct item as a replacement. The customer should return the wrong item using a prepaid shipping label.
- **Conditions**: order_status is "delivered", customer describes receiving an item different from what they ordered
- **Action**: REPLACE_CORRECT_ITEM
- **Confidence guidance**: High (≥0.85) when the customer clearly describes the discrepancy between what was ordered and what was received.
