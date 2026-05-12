# Rex

Rex is a Flutter + FastAPI personal AI assistant with long-term memory.

Current stack:

- Frontend: Flutter mobile app
- Backend: FastAPI
- AI: Grok API through the backend only
- Database: Supabase for conversations, messages, and long-term memory
- Memory: short-term transcript memory plus long-term facts, preferences, and events

Rex no longer uses Ollama, local models, or SQLite.

## Architecture

```text
Flutter app
  -> FastAPI backend
    -> Grok API for chat responses and memory extraction
    -> Supabase REST API for conversations, messages, and long-term memory
```

The Flutter app never stores Grok or Supabase service-role secrets. It only calls the FastAPI backend.

## Environment

Backend settings are read from `.env` by `backend/app/config.py`.

Create a backend environment file:

```sh
cp backend/.env.example backend/.env
```

Required backend values:

```env
APP_ENVIRONMENT=development
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
GROK_API_KEY=
GROK_MODEL=
GROK_BASE_URL=https://api.x.ai/v1
GROK_TIMEOUT_SECONDS=120

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_CONVERSATIONS_TABLE=conversations
SUPABASE_MESSAGES_TABLE=messages
SUPABASE_LONG_TERM_MEMORY_TABLE=long_term_memory
```

Flutter backend URL is passed at build/run time:

```sh
flutter run --dart-define=REX_BACKEND_URL=http://localhost:8000
```

For a physical phone, use your machine's LAN IP instead of `localhost`, for example:

```sh
flutter run --dart-define=REX_BACKEND_URL=http://192.168.1.25:8000
```

## Supabase Setup

Run [backend/supabase_schema.sql](backend/supabase_schema.sql) in the Supabase SQL editor.

The schema creates:

- `conversations`: top-level chat threads
- `messages`: user and assistant transcript entries
- `long_term_memory`: durable facts, preferences, and important events

The backend uses the Supabase service-role key, so keep it server-side only.

## Backend

Install dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run the backend:

```sh
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```sh
curl http://localhost:8000/
```

Chat request:

```sh
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Rex"}'
```

Streaming chat request:

```sh
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Rex","stream":true}'
```

## Flutter

Install packages:

```sh
flutter pub get
```

Run the app:

```sh
flutter run --dart-define=REX_BACKEND_URL=http://localhost:8000
```

Main screens currently implemented:

- Chat screen with streaming responses
- Conversation list and switching
- Long-term memory list/edit/deactivate screen
- File upload flow for `.txt`, `.md`, and `.csv`

## Tests

Backend:

```sh
PYTHONPATH=backend python3 -m pytest -q tests
```

Flutter:

```sh
flutter analyze
flutter test
```

Current expected status after Phase 5.2:

- Backend tests: 44 passing
- Flutter tests: 38 passing

## Notes

- Do not commit real `.env` files or secrets.
- Use `backend/.env.example` as the source for backend environment variable names.
- Use `--dart-define=REX_BACKEND_URL=...` to point Flutter at the correct backend.
- Supabase SQL must be applied before real chat memory can work.
- Deployment notes are in [docs/deployment.md](docs/deployment.md).
