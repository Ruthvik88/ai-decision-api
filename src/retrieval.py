"""
Local RAG retrieval: chunk knowledge-base documents, embed with Gemini
text-embedding-004, store embeddings as .npy + metadata as .json, and
retrieve top-k chunks via NumPy cosine similarity.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A chunk of text from the knowledge base with its source filename."""
    text: str
    source: str  # filename, e.g. "returns.md"


@dataclass
class RetrievalResult:
    """A retrieved chunk with its similarity score."""
    chunk: Chunk
    score: float


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent

def load_knowledge_base(kb_dir: str = "knowledge_base") -> List[Chunk]:
    """
    Read every .md file in *kb_dir* and split into chunks.

    Each top-level section (starting with '## ' or '### ') becomes a chunk.
    This keeps policy rules self-contained. If a file has no sub-headings,
    the whole file is treated as one chunk.
    """
    chunks: List[Chunk] = []
    
    p = Path(kb_dir)
    kb_path = p if p.is_absolute() else PROJECT_ROOT / p
    
    print(f"DEBUG: load_knowledge_base is reading from absolute path: {kb_path.absolute()}")

    md_files = sorted(kb_path.glob("*.md"))
    valid_md_files = 0

    for md_file in md_files:
        # Skip macOS resource forks
        if md_file.name.startswith("._"):
            continue

        valid_md_files += 1
        text = md_file.read_text(encoding="utf-8")
        filename = md_file.name

        # Split on "### Rule" headings to get per-rule chunks
        sections = _split_into_sections(text)
        if sections:
            for section in sections:
                section = section.strip()
                if len(section) > 30:  # skip trivially short fragments
                    chunks.append(Chunk(text=section, source=filename))
        else:
            # No sections found — use the whole file
            chunks.append(Chunk(text=text.strip(), source=filename))

    print(f"DEBUG: Found {valid_md_files} real .md files (ignored {len(md_files) - valid_md_files} macOS resource forks).")
    print(f"DEBUG: Created {len(chunks)} chunks.")
    return chunks


def _split_into_sections(text: str) -> List[str]:
    """
    Split markdown text into sections delineated by '### Rule' headings.
    Each section includes its heading and all content up to the next heading
    of equal or higher level. Also prepends the document title (# heading)
    and overview (## Policy Overview) to each chunk for context.
    """
    lines = text.split("\n")
    header_lines: List[str] = []
    sections: List[str] = []
    current_section_lines: List[str] = []

    # Collect header (everything before first ### Rule)
    in_header = True
    for line in lines:
        if line.strip().startswith("### Rule"):
            if in_header:
                # First rule heading — save everything before it as the header
                in_header = False
                header_lines = current_section_lines[:]
                current_section_lines = [line]
            else:
                # Subsequent rule heading — finalize previous section
                section_text = "\n".join(header_lines + ["", "---", ""] + current_section_lines)
                sections.append(section_text)
                current_section_lines = [line]
        else:
            current_section_lines.append(line)

    # Don't forget the last section
    if current_section_lines and not in_header:
        section_text = "\n".join(header_lines + ["", "---", ""] + current_section_lines)
        sections.append(section_text)

    return sections


# ---------------------------------------------------------------------------
# Embedding via Gemini
# ---------------------------------------------------------------------------

def _get_embed_model():
    """Lazy-import and return the google.generativeai embedding function."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    genai.configure(api_key=api_key)
    return genai


def embed_texts(texts: List[str], task_type: str = "retrieval_document") -> np.ndarray:
    """
    Embed a list of texts using Gemini gemini-embedding-001.
    Returns an (N, D) numpy array of float32 embeddings.
    """
    genai = _get_embed_model()
    model_name = "models/gemini-embedding-001"

    # Try batch call first
    result = genai.embed_content(
        model=model_name,
        content=texts,
        task_type=task_type,
    )
    emb = np.array(result["embedding"], dtype=np.float32)

    # If the API returned a 1-D vector (single embedding) despite multiple
    # inputs, fall back to embedding one text at a time.
    if emb.ndim == 1 and len(texts) > 1:
        print(f"DEBUG embed_texts: batch call returned 1-D array for {len(texts)} texts, falling back to per-text embedding")
        vectors = [emb]  # reuse the first result
        for t in texts[1:]:
            r = genai.embed_content(
                model=model_name,
                content=t,
                task_type=task_type,
            )
            vectors.append(np.array(r["embedding"], dtype=np.float32))
        emb = np.stack(vectors)  # (N, D)
    elif emb.ndim == 1 and len(texts) == 1:
        emb = emb.reshape(1, -1)  # (1, D)

    print(f"DEBUG embed_texts: embedded {len(texts)} texts → shape {emb.shape}")
    assert emb.shape[0] == len(texts), (
        f"Embedding count mismatch: expected {len(texts)}, got {emb.shape[0]}"
    )
    return emb


# ---------------------------------------------------------------------------
# Index: build / load / save
# ---------------------------------------------------------------------------

_INDEX_EMBEDDINGS_FILE = "kb_embeddings.npy"
_INDEX_METADATA_FILE = "kb_metadata.json"


class LocalVectorStore:
    """
    A simple local vector store backed by NumPy arrays.
    Embeddings are cached to disk so we don't re-embed on every restart.
    """

    def __init__(
        self,
        kb_dir: str = "knowledge_base",
        cache_dir: str = ".",
    ):
        self.kb_dir = kb_dir
        
        p = Path(cache_dir)
        self.cache_dir = str(p if p.is_absolute() else PROJECT_ROOT / p)
        
        self.chunks: List[Chunk] = []
        self.embeddings: np.ndarray = np.array([])

    def build_or_load(self) -> "LocalVectorStore":
        """Build the index from scratch or load from cache."""
        emb_path = os.path.join(self.cache_dir, _INDEX_EMBEDDINGS_FILE)
        meta_path = os.path.join(self.cache_dir, _INDEX_METADATA_FILE)

        if os.path.exists(emb_path) and os.path.exists(meta_path):
            self._load_from_cache(emb_path, meta_path)
        else:
            self._build_index()
            self._save_to_cache(emb_path, meta_path)

        return self

    def _build_index(self):
        """Chunk the knowledge base and embed all chunks."""
        self.chunks = load_knowledge_base(self.kb_dir)
        if not self.chunks:
            raise RuntimeError(f"No chunks found in {self.kb_dir}")
        texts = [c.text for c in self.chunks]
        self.embeddings = embed_texts(texts, task_type="retrieval_document")

    def _save_to_cache(self, emb_path: str, meta_path: str):
        np.save(emb_path, self.embeddings)
        metadata = [{"text": c.text, "source": c.source} for c in self.chunks]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _load_from_cache(self, emb_path: str, meta_path: str):
        self.embeddings = np.load(emb_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        self.chunks = [Chunk(text=m["text"], source=m["source"]) for m in metadata]

    def retrieve(self, query: str, k: int = 3) -> List[RetrievalResult]:
        """
        Embed the query and return the top-k most similar chunks
        using cosine similarity.
        """
        query_emb = embed_texts([query], task_type="retrieval_query")  # (1, D)

        # Cosine similarity: dot(a, b) / (||a|| * ||b||)
        norms_index = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms_query = np.linalg.norm(query_emb, axis=1, keepdims=True)

        # Avoid division by zero
        norms_index = np.maximum(norms_index, 1e-10)
        norms_query = np.maximum(norms_query, 1e-10)

        normed_index = self.embeddings / norms_index
        normed_query = query_emb / norms_query

        similarities = (normed_index @ normed_query.T).flatten()  # (N,)

        top_k_indices = np.argsort(similarities)[::-1][:k]

        results = []
        for idx in top_k_indices:
            results.append(
                RetrievalResult(
                    chunk=self.chunks[idx],
                    score=float(similarities[idx]),
                )
            )
        return results


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_store: LocalVectorStore | None = None


def get_vector_store(kb_dir: str = "knowledge_base", cache_dir: str = ".") -> LocalVectorStore:
    """Return the singleton vector store, building/loading it on first call."""
    global _store
    if _store is None:
        _store = LocalVectorStore(kb_dir=kb_dir, cache_dir=cache_dir).build_or_load()
    return _store


def reset_vector_store():
    """Reset the singleton (useful for testing)."""
    global _store
    _store = None
