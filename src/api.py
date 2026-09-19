"""
FastAPI application — all HTTP routes for the AI Decision API.

Endpoints:
  POST /register    — create a new user
  POST /login       — authenticate, return JWT
  GET  /me          — current user info
  POST /tickets     — create ticket + run AI decision
  GET  /tickets     — list current user's tickets
  GET  /tickets/{id} — single ticket (authorization-checked)
"""

import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .database import Decision, Ticket, User, create_tables, get_db
from .decision import generate_decision
from .schemas import (
    DecisionResponse,
    TicketCreate,
    TicketResponse,
    Token,
    UserCreate,
    UserResponse,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
    create_tables()
    logger.info("Database tables created / verified.")
    yield


app = FastAPI(
    title="AI Decision API",
    description="AI-powered support-ticket decision assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Streamlit and any local dev tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch any unhandled exception and return a standard JSON 500 response
    so the API never returns an empty or non-JSON response.
    """
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.exception("Unhandled exception while handling %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user. Password is hashed with bcrypt before storing."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(payload: UserCreate, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(data={"sub": user.email})
    return Token(access_token=token)


@app.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return current_user


# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------

def _decision_model_to_response(decision: Decision) -> DecisionResponse:
    """Convert a Decision ORM object to a DecisionResponse, parsing sources JSON."""
    sources = json.loads(decision.sources) if isinstance(decision.sources, str) else decision.sources
    return DecisionResponse(
        id=decision.id,
        ticket_id=decision.ticket_id,
        action=decision.action,
        confidence=decision.confidence,
        reason=decision.reason,
        sources=sources,
        created_at=decision.created_at,
    )


def _ticket_to_response(ticket: Ticket) -> TicketResponse:
    """Convert a Ticket ORM object to a TicketResponse, including its decision."""
    decision_resp = None
    if ticket.decision:
        decision_resp = _decision_model_to_response(ticket.decision)

    return TicketResponse(
        id=ticket.id,
        user_id=ticket.user_id,
        message=ticket.message,
        order_value_inr=ticket.order_value_inr,
        days_since_delivery=ticket.days_since_delivery,
        days_since_dispatch=ticket.days_since_dispatch,
        product_type=ticket.product_type,
        opened_status=ticket.opened_status,
        order_status=ticket.order_status,
        created_at=ticket.created_at,
        decision=decision_resp,
    )


@app.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a support ticket, run RAG retrieval + Gemini decision,
    validate the output, persist both ticket and decision, and return them.
    """
    # 1. Create the ticket
    ticket = Ticket(
        user_id=current_user.id,
        message=payload.message,
        order_value_inr=payload.order_value_inr,
        days_since_delivery=payload.days_since_delivery,
        days_since_dispatch=payload.days_since_dispatch,
        product_type=payload.product_type,
        opened_status=payload.opened_status,
        order_status=payload.order_status,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # 2. Build structured fields dict for the decision engine
    structured_fields = {
        "order_value_inr": payload.order_value_inr,
        "days_since_delivery": payload.days_since_delivery,
        "days_since_dispatch": payload.days_since_dispatch,
        "product_type": payload.product_type,
        "opened_status": payload.opened_status,
        "order_status": payload.order_status,
    }

    # 3. Generate AI decision
    try:
        decision_output = generate_decision(
            ticket_message=payload.message,
            structured_fields=structured_fields,
        )
    except Exception as e:
        logger.error(f"Decision generation failed: {e}")
        # Fallback decision
        from .schemas import DecisionOutput
        decision_output = DecisionOutput(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.0,
            reason=f"Decision generation encountered an error: {str(e)[:200]}",
            sources=[],
        )

    # 4. Persist the decision
    decision = Decision(
        ticket_id=ticket.id,
        action=decision_output.action,
        reason=decision_output.reason,
        confidence=decision_output.confidence,
        sources=json.dumps(decision_output.sources),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    db.refresh(ticket)

    return _ticket_to_response(ticket)


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tickets belonging to the current user, with their decisions."""
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return [_ticket_to_response(t) for t in tickets]


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single ticket by ID.

    Authorization check: returns 403 if the ticket does not belong to the
    current user, 404 if the ticket does not exist.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    if ticket.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this ticket",
        )
    return _ticket_to_response(ticket)
