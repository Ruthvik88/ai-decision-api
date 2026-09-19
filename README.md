# AI Support-Ticket Decision Assistant

An AI-powered support-ticket decision assistant that analyzes customer support tickets and recommends structured, evidence-backed actions using an e-commerce policy knowledge base and Google Gemini. Built with FastAPI, Streamlit, SQLite, JWT authentication, and a local Retrieval-Augmented Generation (RAG) pipeline over the `knowledge_base/` policy docs.

## Architecture

```
Streamlit (Frontend)  ──HTTP──►  FastAPI (Backend)  ──►  SQLite (DB)
                                       │
                                       ├──►  RAG Retrieval (NumPy cosine similarity)
                                       │          └── models/gemini-embedding-001
                                       └──►  gemini-3.5-flash-lite (Decision engine)
```

## Tech Stack

| Layer        | Technology                                  |
|:-------------|:--------------------------------------------|
| Backend      | FastAPI + Uvicorn                            |
| Frontend     | Streamlit                                    |
| Database     | SQLite via SQLAlchemy                        |
| Auth         | JWT (python-jose) + passlib bcrypt           |
| LLM          | Google Gemini (`gemini-3.5-flash-lite`)      |
| Embeddings   | Google Gemini (`models/gemini-embedding-001`)|
| RAG          | Local NumPy cosine similarity (no vector DB) |
| Validation   | Pydantic v2                                  |

## Project Structure

```
├── README.md                  ← Project documentation
├── DEVELOPMENT.md             ← AI development & debugging log
├── requirements.txt
├── .env.example
├── .gitignore
├── knowledge_base/            ← Policy documents (6 .md files)
├── data/                      ← tickets.csv sample data
├── sample_test_cases.json     ← 15 test cases for evaluation
├── src/
│   ├── __init__.py
│   ├── api.py                 ← FastAPI app + all endpoints
│   ├── auth.py                ← JWT + bcrypt auth
│   ├── database.py            ← SQLAlchemy models + engine
│   ├── schemas.py             ← Pydantic request/response schemas
│   ├── retrieval.py           ← RAG: chunking, embedding, top-k retrieval
│   └── decision.py            ← Gemini prompt + validation + fallback
├── streamlit_app.py           ← Streamlit frontend
├── evaluate.py                ← Test suite evaluator
└── tests/                     ← Pytest suite
    ├── test_auth.py
    ├── test_authorization.py
    ├── test_tickets.py
    └── test_retrieval.py
```

## Setup Instructions

### 1. Create Virtual Environment & Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in the required keys:

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Set the following variables in `.env`:
- `GEMINI_API_KEY`: Your Google Gemini API key.
- `JWT_SECRET`: A secret string used for signing JWT tokens.

## How to Run

### Backend (FastAPI)

```bash
uvicorn src.api:app --reload
```
The API server runs at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### Frontend (Streamlit)

In a separate terminal (with virtualenv activated):

```bash
streamlit run streamlit_app.py
```
The Streamlit web dashboard opens at `http://localhost:8501`.

### Automated Tests (Pytest)

```bash
pytest -v
```
Runs unit and integration tests against an in-memory SQLite database with mocked Gemini API calls.

### Evaluation Script

```bash
python evaluate.py
```
Runs the 15 evaluation test cases from `sample_test_cases.json` through the decision pipeline and outputs accuracy metrics.

## Model Choice & Rate Limiting

The decision engine deliberately uses **`gemini-3.5-flash-lite`** rather than a flagship model (such as `gemini-3.6-flash` or Pro variants). This choice was made due to strict free-tier daily quota limits on flagship Gemini models (e.g., 20 requests/day on `gemini-3.6-flash` for new project API keys), which are too restrictive for iterative testing and evaluation runs. `gemini-3.5-flash-lite` provides sufficient daily free-tier quota while still achieving 100% accuracy on the 15 evaluation test cases.

To stay within free-tier requests-per-minute (RPM) limits, `evaluate.py` incorporates a configurable delay between test case calls via the `EVAL_DELAY_SECONDS` environment variable (defaults to `6` seconds).

## Local RAG Approach

The Retrieval-Augmented Generation (RAG) pipeline is lightweight, self-contained, and operates without a hosted vector database:

1. **Chunking**: Policy documents in `knowledge_base/*.md` are parsed and chunked by rule section (`### Rule` headings), prepending document titles and context to each chunk.
2. **Embedding**: Chunks are embedded using Google's `models/gemini-embedding-001` (producing 3072-dimensional vectors).
3. **Local Caching**: Embeddings and chunk metadata are cached locally on disk as `kb_embeddings.npy` and `kb_metadata.json`. If cached files exist and match the knowledge base files, they are reloaded instantly without re-invoking the embedding API.
4. **Retrieval**: When a ticket is submitted, its text is embedded as a query vector and compared against cached chunk embeddings using NumPy cosine similarity to retrieve the top matching policy chunks.