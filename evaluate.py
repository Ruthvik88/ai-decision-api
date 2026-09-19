"""
Evaluation script: runs sample_test_cases.json through the decision logic
and compares actual actions to expected actions.

Usage:
    python evaluate.py

This calls the decision function directly (does not require the API server
to be running). It loads the knowledge base, builds/loads the vector index,
and runs each test case through the same generate_decision() function used
by the POST /tickets endpoint.
"""

import json
import os
import sys
import time

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

# Force UTF-8 for console output (Windows cp1252 can't encode Unicode chars
# that Gemini may include in its responses or that appear in log messages).
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

# Configurable delay between test cases to stay under Gemini's RPM limit.
# gemini-2.5-flash free tier ≈ 10 RPM; each case may use up to 2 calls (retry).
EVAL_DELAY_SECONDS = int(os.getenv("EVAL_DELAY_SECONDS", "6"))

from src.decision import generate_decision
from src.retrieval import get_vector_store


def main():
    # Load test cases
    test_cases_path = os.path.join(os.path.dirname(__file__), "sample_test_cases.json")
    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    if not test_cases:
        print("No test cases found in sample_test_cases.json")
        sys.exit(1)

    # Pre-build the vector store so it's shared across test cases
    print("Building/loading knowledge base index...")
    store = get_vector_store()
    print(f"Index loaded with {len(store.chunks)} chunks.\n")

    correct = 0
    total = len(test_cases)

    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    for tc in test_cases:
        test_id = tc.get("test_id", "?")
        ticket_message = tc["ticket_message"]
        expected_action = tc["expected_action"]

        # Build structured fields (exclude null values)
        structured_fields = {}
        for field in [
            "order_value_inr",
            "days_since_delivery",
            "days_since_dispatch",
            "product_type",
            "opened_status",
            "order_status",
        ]:
            val = tc.get(field)
            if val is not None:
                structured_fields[field] = val

        # Run the decision engine
        try:
            decision = generate_decision(
                ticket_message=ticket_message,
                structured_fields=structured_fields,
                vector_store=store,
            )
            actual_action = decision.action
        except Exception as e:
            actual_action = f"ERROR: {e}"

        # Compare
        is_correct = actual_action == expected_action
        if is_correct:
            correct += 1

        status = "Correct" if is_correct else "Incorrect"
        # Truncate message for display
        msg_preview = ticket_message[:50] + ("..." if len(ticket_message) > 50 else "")
        print(
            f"Test Case {test_id}: [{msg_preview}] "
            f"-> Expected: {expected_action}, Got: {actual_action} "
            f"-> {status}"
        )

        # Throttle requests to stay within Gemini rate limits
        time.sleep(EVAL_DELAY_SECONDS)

    print("=" * 70)
    accuracy = (correct / total) * 100 if total > 0 else 0
    print(f"\nAccuracy: {correct}/{total} ({accuracy:.1f}%)")


if __name__ == "__main__":
    main()
