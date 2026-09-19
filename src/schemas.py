"""
Pydantic request / response schemas and the validated AI decision output model.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Ticket schemas
# ---------------------------------------------------------------------------

ActionType = Literal[
    "APPROVE_REFUND_OR_REPLACEMENT",
    "APPROVE_REPLACEMENT",
    "APPROVE_RETURN",
    "CANCEL_AND_REFUND",
    "CANNOT_CANCEL_AFTER_DISPATCH",
    "NEEDS_MORE_INFORMATION",
    "OFFER_REPLACEMENT_OR_REFUND",
    "OPEN_SHIPPING_INVESTIGATION",
    "REJECT_FOOD_RETURN",
    "REJECT_OPENED_ITEM",
    "REJECT_OUTSIDE_WINDOW",
    "REPLACE_CORRECT_ITEM",
    "REQUEST_DEFECT_EVIDENCE",
    "REQUEST_PHOTOS",
    "WAIT_AND_TRACK",
]


class TicketCreate(BaseModel):
    """Request body for creating a new support ticket."""
    message: str
    order_value_inr: Optional[float] = None
    days_since_delivery: Optional[int] = None
    days_since_dispatch: Optional[int] = None
    product_type: Optional[str] = None
    opened_status: Optional[str] = None
    order_status: Optional[str] = None


class DecisionOutput(BaseModel):
    """
    Validated schema for the AI decision.  Gemini's JSON response MUST
    conform to this schema or the call is retried / falls back.
    """
    action: ActionType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    sources: List[str]


class DecisionResponse(BaseModel):
    id: int
    ticket_id: int
    action: str
    confidence: float
    reason: str
    sources: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: int
    user_id: int
    message: str
    order_value_inr: Optional[float] = None
    days_since_delivery: Optional[int] = None
    days_since_dispatch: Optional[int] = None
    product_type: Optional[str] = None
    opened_status: Optional[str] = None
    order_status: Optional[str] = None
    created_at: datetime
    decision: Optional[DecisionResponse] = None

    model_config = {"from_attributes": True}
