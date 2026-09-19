"""
CRITICAL authorization test: Alice's JWT must NOT be able to fetch Bob's
ticket via GET /tickets/{id}. Asserts 403 is returned.
"""

from unittest.mock import patch
import pytest

from src.schemas import DecisionOutput
from tests.conftest import client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def register_and_login(email: str, password: str = "pass123") -> str:
    """Register a user, login, and return the JWT token."""
    client.post("/register", json={"email": email, "password": password})
    resp = client.post("/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


MOCK_DECISION = DecisionOutput(
    action="NEEDS_MORE_INFORMATION",
    confidence=0.5,
    reason="Mock decision for testing",
    sources=["test.md"],
)


# ---------------------------------------------------------------------------
# Authorization tests
# ---------------------------------------------------------------------------


class TestTicketAuthorization:
    """
    Ensure that users can only access their own tickets.
    This is the critical authorization check.
    """

    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_alice_cannot_access_bobs_ticket(self, mock_decision):
        """
        Alice's JWT must NOT be able to fetch Bob's ticket.
        GET /tickets/{bob's_ticket_id} with Alice's token → 403 Forbidden.
        """
        # Register both users
        alice_token = register_and_login("alice@example.com")
        bob_token = register_and_login("bob@example.com")

        # Bob creates a ticket
        bob_resp = client.post(
            "/tickets",
            json={"message": "Bob's private ticket about a refund"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_resp.status_code == 201
        bob_ticket_id = bob_resp.json()["id"]

        # Alice tries to access Bob's ticket → 403
        alice_resp = client.get(
            f"/tickets/{bob_ticket_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert alice_resp.status_code == 403
        assert "not authorized" in alice_resp.json()["detail"].lower()

    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_user_can_access_own_ticket(self, mock_decision):
        """User should be able to access their own tickets."""
        token = register_and_login("owner@example.com")

        # Create a ticket
        resp = client.post(
            "/tickets",
            json={"message": "My own ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        ticket_id = resp.json()["id"]

        # Access own ticket → 200
        resp = client.get(
            f"/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == ticket_id

    def test_nonexistent_ticket_returns_404(self):
        """Accessing a non-existent ticket should return 404."""
        token = register_and_login("user404@example.com")
        resp = client.get(
            "/tickets/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @patch("src.api.generate_decision", return_value=MOCK_DECISION)
    def test_alice_list_only_shows_own_tickets(self, mock_decision):
        """GET /tickets should only return the current user's tickets."""
        alice_token = register_and_login("alice_list@example.com")
        bob_token = register_and_login("bob_list@example.com")

        # Both create tickets
        client.post(
            "/tickets",
            json={"message": "Alice's ticket"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        client.post(
            "/tickets",
            json={"message": "Bob's ticket"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )

        # Alice's ticket list should only contain her ticket
        resp = client.get(
            "/tickets",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        tickets = resp.json()
        assert len(tickets) == 1
        assert tickets[0]["message"] == "Alice's ticket"
