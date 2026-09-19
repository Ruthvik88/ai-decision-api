"""
Streamlit frontend for the AI Decision API.

Pages (via sidebar):
  - Login / Register
  - New Decision
  - History

All data access is via HTTP requests to the FastAPI backend.
JWT is stored in st.session_state.
"""

import json

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "jwt" not in st.session_state:
    st.session_state.jwt = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def auth_headers() -> dict:
    """Return the Authorization header dict if logged in."""
    if st.session_state.jwt:
        return {"Authorization": f"Bearer {st.session_state.jwt}"}
    return {}


def api_post(endpoint: str, data: dict, auth: bool = False) -> requests.Response:
    headers = auth_headers() if auth else {}
    return requests.post(f"{API_BASE}{endpoint}", json=data, headers=headers)


def api_get(endpoint: str) -> requests.Response:
    return requests.get(f"{API_BASE}{endpoint}", headers=auth_headers())


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Decision API",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🤖 AI Decision API")

if st.session_state.jwt:
    st.sidebar.success(f"Logged in as **{st.session_state.user_email}**")
    if st.sidebar.button("Logout"):
        st.session_state.jwt = None
        st.session_state.user_email = None
        st.rerun()
    page = st.sidebar.radio("Navigate", ["New Decision", "History"])
else:
    page = st.sidebar.radio("Navigate", ["Login", "Register"])

# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

if page == "Login":
    st.title("🔐 Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if not email or not password:
                st.error("Please fill in both fields.")
            else:
                try:
                    resp = api_post("/login", {"email": email, "password": password})
                    if resp.status_code == 200:
                        token_data = resp.json()
                        st.session_state.jwt = token_data["access_token"]
                        st.session_state.user_email = email
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        try:
                            detail = resp.json().get("detail", "Login failed")
                        except ValueError:
                            detail = resp.text or f"Login failed with status {resp.status_code} and no response body"
                        st.error(f"Login failed: {detail}")
                except requests.ConnectionError:
                    st.error("Cannot connect to the API server. Is the backend running?")

# ---------------------------------------------------------------------------
# Register page
# ---------------------------------------------------------------------------

elif page == "Register":
    st.title("📝 Register")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if not email or not password:
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    resp = api_post("/register", {"email": email, "password": password})
                    if resp.status_code == 201:
                        st.success("Registration successful! Please login.")
                    else:
                        try:
                            detail = resp.json().get("detail", "Registration failed")
                        except ValueError:
                            detail = resp.text or f"Registration failed with status {resp.status_code} and no response body"
                        st.error(f"Registration failed: {detail}")
                except requests.ConnectionError:
                    st.error("Cannot connect to the API server. Is the backend running?")

# ---------------------------------------------------------------------------
# New Decision page
# ---------------------------------------------------------------------------

elif page == "New Decision":
    st.title("🎫 Submit a Support Ticket")
    st.markdown("Describe your issue and optionally provide structured details.")

    with st.form("ticket_form"):
        message = st.text_area(
            "Ticket Message",
            placeholder="e.g. I received a damaged product...",
            height=120,
        )

        st.markdown("**Optional Structured Fields**")
        col1, col2, col3 = st.columns(3)
        with col1:
            order_value = st.number_input(
                "Order Value (INR)", min_value=0.0, value=0.0, step=100.0
            )
            product_type = st.selectbox(
                "Product Type",
                [None, "electronics", "clothing", "food", "home_appliance", "accessories", "grocery"],
            )
        with col2:
            days_delivery = st.number_input(
                "Days Since Delivery", min_value=-1, value=-1, step=1,
                help="Set to -1 if not applicable",
            )
            opened_status = st.selectbox(
                "Opened Status",
                [None, "unopened", "opened", "sealed", "used"],
            )
        with col3:
            days_dispatch = st.number_input(
                "Days Since Dispatch", min_value=-1, value=-1, step=1,
                help="Set to -1 if not applicable",
            )
            order_status = st.selectbox(
                "Order Status",
                [None, "processing", "confirmed", "shipped", "in_transit", "delivered"],
            )

        submitted = st.form_submit_button("🚀 Get AI Decision", type="primary")

    if submitted:
        if not message.strip():
            st.error("Please enter a ticket message.")
        else:
            payload = {"message": message}
            if order_value > 0:
                payload["order_value_inr"] = order_value
            if days_delivery >= 0:
                payload["days_since_delivery"] = int(days_delivery)
            if days_dispatch >= 0:
                payload["days_since_dispatch"] = int(days_dispatch)
            if product_type:
                payload["product_type"] = product_type
            if opened_status:
                payload["opened_status"] = opened_status
            if order_status:
                payload["order_status"] = order_status

            with st.spinner("Analyzing ticket with AI..."):
                try:
                    resp = api_post("/tickets", payload, auth=True)
                    if resp.status_code == 201:
                        result = resp.json()
                        decision = result.get("decision", {})

                        st.success("Decision generated!")
                        st.divider()

                        # Display decision
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            st.subheader("📋 Decision")
                            st.markdown(f"**Action:** `{decision.get('action', 'N/A')}`")
                            st.markdown(f"**Reason:** {decision.get('reason', 'N/A')}")
                            st.markdown(f"**Sources:** {', '.join(decision.get('sources', []))}")
                        with col_b:
                            confidence = decision.get("confidence", 0)
                            st.metric("Confidence", f"{confidence:.0%}")

                    elif resp.status_code == 401:
                        st.error("Session expired. Please login again.")
                        st.session_state.jwt = None
                        st.rerun()
                    else:
                        detail = resp.json().get("detail", "Unknown error")
                        st.error(f"Error: {detail}")
                except requests.ConnectionError:
                    st.error("Cannot connect to the API server. Is the backend running?")

# ---------------------------------------------------------------------------
# History page
# ---------------------------------------------------------------------------

elif page == "History":
    st.title("📜 Ticket History")

    try:
        resp = api_get("/tickets")
        if resp.status_code == 200:
            tickets = resp.json()
            if not tickets:
                st.info("No tickets submitted yet.")
            else:
                for ticket in tickets:
                    decision = ticket.get("decision", {})
                    action = decision.get("action", "N/A") if decision else "N/A"
                    confidence = decision.get("confidence", 0) if decision else 0

                    with st.expander(
                        f"🎫 Ticket #{ticket['id']} — {action} ({confidence:.0%})",
                        expanded=False,
                    ):
                        st.markdown(f"**Message:** {ticket['message']}")

                        # Show structured fields if present
                        fields = []
                        if ticket.get("order_value_inr"):
                            fields.append(f"Order Value: ₹{ticket['order_value_inr']}")
                        if ticket.get("days_since_delivery") is not None:
                            fields.append(f"Days Since Delivery: {ticket['days_since_delivery']}")
                        if ticket.get("days_since_dispatch") is not None:
                            fields.append(f"Days Since Dispatch: {ticket['days_since_dispatch']}")
                        if ticket.get("product_type"):
                            fields.append(f"Product Type: {ticket['product_type']}")
                        if ticket.get("opened_status"):
                            fields.append(f"Opened Status: {ticket['opened_status']}")
                        if ticket.get("order_status"):
                            fields.append(f"Order Status: {ticket['order_status']}")
                        if fields:
                            st.markdown("**Details:** " + " | ".join(fields))

                        if decision:
                            st.divider()
                            st.markdown(f"**Action:** `{decision.get('action', 'N/A')}`")
                            st.markdown(f"**Confidence:** {decision.get('confidence', 0):.0%}")
                            st.markdown(f"**Reason:** {decision.get('reason', 'N/A')}")
                            st.markdown(
                                f"**Sources:** {', '.join(decision.get('sources', []))}"
                            )

                        st.caption(f"Created: {ticket.get('created_at', 'N/A')}")

        elif resp.status_code == 401:
            st.error("Session expired. Please login again.")
            st.session_state.jwt = None
            st.rerun()
        else:
            st.error("Failed to load tickets.")
    except requests.ConnectionError:
        st.error("Cannot connect to the API server. Is the backend running?")
