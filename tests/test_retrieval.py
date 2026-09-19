"""
Tests for the retrieval module: chunking, embedding, and top-k retrieval.

Note: embedding/retrieval tests that call the Gemini API are marked with
@pytest.mark.skipif to skip when GEMINI_API_KEY is not set.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from src.retrieval import (
    Chunk,
    LocalVectorStore,
    RetrievalResult,
    load_knowledge_base,
    _split_into_sections,
)


# ---------------------------------------------------------------------------
# Chunking tests (no API needed)
# ---------------------------------------------------------------------------


class TestChunking:
    def test_load_knowledge_base_returns_chunks(self):
        """Should load chunks from the knowledge_base directory."""
        chunks = load_knowledge_base("knowledge_base")
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunks_have_source_filenames(self):
        """Each chunk should reference its source .md filename."""
        chunks = load_knowledge_base("knowledge_base")
        sources = set(c.source for c in chunks)
        # We expect at least these policy files
        expected_files = {
            "cancellations.md",
            "damaged_goods.md",
            "defective_products.md",
            "returns.md",
            "shipping.md",
            "wrong_item.md",
        }
        assert expected_files.issubset(sources), (
            f"Missing sources. Found: {sources}, Expected at least: {expected_files}"
        )

    def test_chunks_are_nonempty(self):
        """No chunk should be trivially short."""
        chunks = load_knowledge_base("knowledge_base")
        for chunk in chunks:
            assert len(chunk.text.strip()) > 30, f"Short chunk: {chunk.text[:50]}"

    def test_skip_macos_resource_forks(self):
        """Chunks should not come from ._ files."""
        chunks = load_knowledge_base("knowledge_base")
        for chunk in chunks:
            assert not chunk.source.startswith("._"), (
                f"Resource fork loaded: {chunk.source}"
            )

    def test_split_into_sections(self):
        """Test that markdown is split on ### Rule headings."""
        text = """# Test Policy

## Policy Overview
Overview text here.

## Rules

### Rule 1: First Rule
First rule content here with enough characters to pass the minimum length filter.

### Rule 2: Second Rule
Second rule content here with enough characters to pass the minimum length filter.
"""
        sections = _split_into_sections(text)
        assert len(sections) == 2
        assert "Rule 1" in sections[0]
        assert "Rule 2" in sections[1]
        # Both sections should include the header context
        assert "Test Policy" in sections[0]
        assert "Test Policy" in sections[1]


# ---------------------------------------------------------------------------
# Retrieval tests (mocked embeddings)
# ---------------------------------------------------------------------------


class TestRetrievalWithMocks:
    def test_cosine_similarity_retrieval(self):
        """Test that top-k retrieval returns the most similar chunks."""
        store = LocalVectorStore.__new__(LocalVectorStore)

        # Create mock chunks
        store.chunks = [
            Chunk(text="cancellation policy text", source="cancellations.md"),
            Chunk(text="return policy text", source="returns.md"),
            Chunk(text="shipping policy text", source="shipping.md"),
        ]

        # Create embeddings where chunk 0 is most similar to the query
        store.embeddings = np.array([
            [1.0, 0.0, 0.0],  # cancellations
            [0.0, 1.0, 0.0],  # returns
            [0.0, 0.0, 1.0],  # shipping
        ], dtype=np.float32)

        # Mock embed_texts to return a query embedding similar to cancellations
        with patch("src.retrieval.embed_texts") as mock_embed:
            mock_embed.return_value = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)
            results = store.retrieve("cancel my order", k=2)

        assert len(results) == 2
        assert results[0].chunk.source == "cancellations.md"
        assert results[0].score > results[1].score

    def test_retrieve_correct_source_for_shipping_query(self):
        """The retrieval should return shipping.md for a shipping-related query."""
        store = LocalVectorStore.__new__(LocalVectorStore)

        store.chunks = [
            Chunk(text="cancel order rules", source="cancellations.md"),
            Chunk(text="return item rules", source="returns.md"),
            Chunk(text="package delivery tracking delays", source="shipping.md"),
            Chunk(text="wrong item received replacement", source="wrong_item.md"),
        ]

        store.embeddings = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)

        with patch("src.retrieval.embed_texts") as mock_embed:
            # Query embedding close to shipping
            mock_embed.return_value = np.array(
                [[0.0, 0.05, 0.9, 0.05]], dtype=np.float32
            )
            results = store.retrieve("my package hasn't arrived", k=1)

        assert len(results) == 1
        assert results[0].chunk.source == "shipping.md"


# ---------------------------------------------------------------------------
# Integration test (requires GEMINI_API_KEY)
# ---------------------------------------------------------------------------

HAS_API_KEY = bool(os.getenv("GEMINI_API_KEY"))


@pytest.mark.skipif(not HAS_API_KEY, reason="GEMINI_API_KEY not set")
class TestRetrievalIntegration:
    def test_build_index_and_retrieve(self):
        """Build a real index and retrieve relevant chunks for a query."""
        store = LocalVectorStore(
            kb_dir="knowledge_base",
            cache_dir=".",
        ).build_or_load()

        results = store.retrieve("I want to cancel my order", k=3)
        assert len(results) == 3
        # The top result should be from cancellations.md
        sources = [r.chunk.source for r in results]
        assert "cancellations.md" in sources, (
            f"Expected cancellations.md in top results, got: {sources}"
        )
