# Rex

Rex is a Flutter app with a FastAPI backend for a personal AI advisor.

## Backend Direction

The backend is prepared for:

- Grok API for chat completions
- Supabase for conversation, message, and long-term memory

Copy `backend/.env.example` to `backend/.env`, fill in the Grok and Supabase values, and run the SQL in `backend/supabase_schema.sql` inside Supabase.

The Supabase schema includes:

- `conversations`: top-level chat threads.
- `messages`: user and assistant transcript entries.
- `long_term_memory`: durable user facts, preferences, and important events.

## Tests

```sh
PYTHONPATH=backend python3 -m pytest -q tests
flutter test
```
