"""
Decision engine: builds a prompt from retrieved knowledge-base chunks and
the incoming ticket, calls Gemini, validates the response against
DecisionOutput, retries once on failure, and falls back to
NEEDS_MORE_INFORMATION.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .retrieval import LocalVectorStore, RetrievalResult, get_vector_store
from .schemas import DecisionOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def _get_gemini_model():
    """Return a configured GenerativeModel instance."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    genai.configure(api_key=api_key)
    # gemini-3.5-flash-lite: stable, free-tier eligible model with a generous daily quota.
    return genai.GenerativeModel("gemini-3.5-flash-lite")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an AI support-ticket decision assistant for an e-commerce platform.
Your job is to analyse a customer support ticket and recommend a structured
decision based ONLY on the company policy documents provided below.

IMPORTANT RULES:
1. You must respond with ONLY a JSON object — no markdown, no explanation
   outside the JSON.
2. The JSON must conform to this exact schema:
   {{
     "action": "<one of the allowed actions>",
     "confidence": <float between 0.0 and 1.0>,
     "reason": "<short explanation citing the specific policy rule applied>",
     "sources": ["<list of knowledge_base filenames actually used>"]
   }}
3. Allowed actions (use EXACTLY one of these strings):
   APPROVE_REFUND_OR_REPLACEMENT, APPROVE_REPLACEMENT, APPROVE_RETURN,
   CANCEL_AND_REFUND, CANNOT_CANCEL_AFTER_DISPATCH, NEEDS_MORE_INFORMATION,
   OFFER_REPLACEMENT_OR_REFUND, OPEN_SHIPPING_INVESTIGATION, REJECT_FOOD_RETURN,
   REJECT_OPENED_ITEM, REJECT_OUTSIDE_WINDOW, REPLACE_CORRECT_ITEM,
   REQUEST_DEFECT_EVIDENCE, REQUEST_PHOTOS, WAIT_AND_TRACK
4. Base your decision ONLY on the provided policy text. Do NOT invent rules.
5. If the ticket does not provide enough information to confidently apply a
   policy rule, you MUST return action "NEEDS_MORE_INFORMATION".
6. In "sources", list ONLY the filenames of the policy documents you actually
   used to make your decision.
7. The "confidence" should reflect how well the ticket information matches the
   policy rule. Use a high confidence (>0.8) only when all required details
   are present and the policy rule is clearly applicable.
"""


def _build_prompt(
    ticket_message: str,
    structured_fields: Dict[str, Any],
    retrieved_chunks: List[RetrievalResult],
) -> str:
    """Assemble the full prompt for Gemini from ticket + retrieved policy chunks."""

    # Policy context
    policy_sections = []
    for i, r in enumerate(retrieved_chunks, 1):
        policy_sections.append(
            f"--- Policy Document: {r.chunk.source} (relevance: {r.score:.3f}) ---\n"
            f"{r.chunk.text}\n"
        )
    policy_text = "\n".join(policy_sections)

    # Ticket details
    fields_text = ""
    if structured_fields:
        field_lines = []
        for key, value in structured_fields.items():
            if value is not None:
                field_lines.append(f"  - {key}: {value}")
        if field_lines:
            fields_text = "\nStructured ticket fields:\n" + "\n".join(field_lines)

    prompt = (
        f"=== COMPANY POLICY DOCUMENTS ===\n\n{policy_text}\n\n"
        f"=== CUSTOMER SUPPORT TICKET ===\n"
        f"Message: {ticket_message}\n"
        f"{fields_text}\n\n"
        f"Based on the policy documents above, provide your decision as a JSON object."
    )
    return prompt


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) if present."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _parse_gemini_response(raw_text: str) -> DecisionOutput:
    """
    Parse Gemini's raw text response into a validated DecisionOutput.
    Raises ValueError/ValidationError on failure.
    """
    cleaned = _strip_markdown_fences(raw_text)
    data = json.loads(cleaned)
    return DecisionOutput.model_validate(data)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_decision(
    ticket_message: str,
    structured_fields: Optional[Dict[str, Any]] = None,
    vector_store: Optional[LocalVectorStore] = None,
    k: int = 4,
) -> DecisionOutput:
    """
    Run the full decision pipeline:
    1. Retrieve top-k policy chunks relevant to the ticket.
    2. Build a prompt with the chunks and ticket details.
    3. Call Gemini and validate the response.
    4. Retry once on failure, then fall back to NEEDS_MORE_INFORMATION.
    """
    if structured_fields is None:
        structured_fields = {}

    # Retrieve relevant policy chunks
    store = vector_store or get_vector_store()

    # Build query from message + relevant structured fields
    query_parts = [ticket_message]
    if structured_fields.get("product_type"):
        query_parts.append(f"product type: {structured_fields['product_type']}")
    if structured_fields.get("order_status"):
        query_parts.append(f"order status: {structured_fields['order_status']}")
    if structured_fields.get("opened_status"):
        query_parts.append(f"opened status: {structured_fields['opened_status']}")
    query = " | ".join(query_parts)

    retrieved = store.retrieve(query, k=k)

    # Build prompt
    prompt = _build_prompt(ticket_message, structured_fields, retrieved)

    # Call Gemini (with retry)
    model = _get_gemini_model()
    last_error: Optional[Exception] = None

    for attempt in range(2):  # max 2 attempts
        try:
            # Try using response_mime_type for structured output
            try:
                response = model.generate_content(
                    [
                        {"role": "user", "parts": [SYSTEM_PROMPT + "\n\n" + prompt]},
                    ],
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )
            except Exception:
                # Fallback: no response_mime_type
                response = model.generate_content(
                    [
                        {"role": "user", "parts": [SYSTEM_PROMPT + "\n\n" + prompt]},
                    ],
                    generation_config={"temperature": 0.1},
                )

            raw_text = response.text
            logger.info(f"Gemini response (attempt {attempt + 1}): {raw_text[:200]}...")

            decision = _parse_gemini_response(raw_text)

            # Ensure sources only reference files that were actually retrieved
            retrieved_sources = list(set(r.chunk.source for r in retrieved))
            decision.sources = [s for s in decision.sources if s in retrieved_sources]
            if not decision.sources:
                decision.sources = retrieved_sources[:2]

            return decision

        except Exception as e:
            last_error = e
            logger.warning(
                f"Gemini attempt {attempt + 1} failed: {e}. "
                f"{'Retrying...' if attempt == 0 else 'Falling back.'}"
            )

    # Fallback: return a safe NEEDS_MORE_INFORMATION decision
    logger.error(f"Both Gemini attempts failed. Last error: {last_error}")
    retrieved_sources = list(set(r.chunk.source for r in retrieved))
    return DecisionOutput(
        action="NEEDS_MORE_INFORMATION",
        confidence=0.0,
        reason=f"Unable to generate a confident decision. Error: {str(last_error)[:200]}",
        sources=retrieved_sources[:2],
    )
