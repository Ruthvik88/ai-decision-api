"""
Tests for ticket creation, decision persistence, and retrieval.
"""

import json

from unittest.mock import patch
import pytest

from src.schemas import DecisionOutput
from tests.conftest import client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def register_and_login(email: str = "test@example.com", password: str = "pass123") -> str:
    client.post("/register", json={"email": email, "password": password})
    resp = client.post("/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


MOCK_DECISION = DecisionOutput(
    action="CANCEL_AND_REFUND",
    confidence=0.92,
    reason="Order is still processing, cancellation policy Rule 1 applies.",
    sources=["cancellations.md"],
)


# ---------------------------------------------------------------------------
# Ticket tests
# ---------------------------------------------------------------------------


class TestTicketCreation:
    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_create_ticket_returns_decision(self, mock_decision):
        """Creating a ticket should return the ticket + AI decision."""
        token = register_and_login()
        resp = client.post(
            "/tickets",
            json={
                "message": "I want to cancel my order, it hasn't shipped yet.",
                "order_status": "processing",
                "order_value_inr": 1200,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()

        # Ticket fields
        assert data["message"] == "I want to cancel my order, it hasn't shipped yet."
        assert data["order_status"] == "processing"
        assert data["order_value_inr"] == 1200

        # Decision must be present
        decision = data["decision"]
        assert decision is not None
        assert decision["action"] == "CANCEL_AND_REFUND"
        assert decision["confidence"] == 0.92
        assert "cancellations.md" in decision["sources"]
        assert len(decision["reason"]) > 0

    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_decision_is_persisted(self, mock_decision):
        """The decision should be persisted and retrievable via GET."""
        token = register_and_login("persist@example.com")

        # Create ticket
        create_resp = client.post(
            "/tickets",
            json={"message": "Cancel my order please"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ticket_id = create_resp.json()["id"]

        # Retrieve it
        get_resp = client.get(
            f"/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == ticket_id
        assert data["decision"]["action"] == "CANCEL_AND_REFUND"

    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_list_tickets(self, mock_decision):
        """GET /tickets should list all of the user's tickets."""
        token = register_and_login("list@example.com")

        # Create two tickets
        client.post(
            "/tickets",
            json={"message": "First ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/tickets",
            json={"message": "Second ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = client.get(
            "/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        tickets = resp.json()
        assert len(tickets) == 2

    def test_create_ticket_requires_auth(self):
        """POST /tickets without a token should return 401."""
        resp = client.post("/tickets", json={"message": "No auth"})
        assert resp.status_code == 401


class TestDecisionSchema:
    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_decision_has_all_fields(self, mock_decision):
        """Decision response should have action, confidence, reason, sources."""
        token = register_and_login("schema@example.com")
        resp = client.post(
            "/tickets",
            json={"message": "Test decision schema"},
            headers={"Authorization": f"Bearer {token}"},
        )
        decision = resp.json()["decision"]
        assert "action" in decision
        assert "confidence" in decision
        assert "reason" in decision
        assert "sources" in decision
        assert isinstance(decision["sources"], list)
        assert 0.0 <= decision["confidence"] <= 1.0
