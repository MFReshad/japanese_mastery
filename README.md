# Japanese Mastery

A simple Japanese vocabulary and kanji mastery/practice system for book-based study data.

## Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Alembic
- Database: Neon PostgreSQL only for the app
- Dev: Docker Compose starts frontend and backend only

## Run

1. Copy `.env.example` to `.env` and set your Neon `DATABASE_URL`.
2. Start the app:

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

The backend runs `alembic upgrade head` and seeds one clearly marked demo book if it does not exist.

## Import JSON

Preview:

```bash
DATABASE_URL="postgresql://..." python scripts/import_json.py data/imports --dry-run
```

Commit:

```bash
DATABASE_URL="postgresql://..." python scripts/import_json.py data/imports --commit
```

Supported files:

- `books.json`
- `chapters.json`
- `vocabulary.json`
- `vocabulary_sources.json`
- `kanji.json`
- `kanji_sources.json`

The importer runs in a transaction, matches vocabulary by expression plus reading, matches kanji by character, and reports inserted, updated, skipped, conflicts, and errors.

## Useful Backend Commands

```bash
cd backend
alembic upgrade head
pytest
```

Tests use an isolated in-memory SQLite database with an explicit test-only override. The application runtime rejects SQLite and requires PostgreSQL.
