# Rex Deployment

This document covers the backend deployment path for a VPS using Python virtualenv, `systemd`, and Nginx or Caddy.

## Deployment Choice

Rex uses a plain VPS deployment for the initial production path.

A setup with Python virtualenv, `systemd`, and Nginx or Caddy is enough, light, and simple while Rex is still moving fast.

Recommended setup:

- Use a Python virtualenv for backend dependencies.
- Use `systemd` to keep Uvicorn running.
- Put Nginx or Caddy in front of Uvicorn for HTTPS.

## Required Environment

Your root `.env` can contain the backend values as long as the backend process runs from the project root with `PYTHONPATH=backend`.

Required:

```env
APP_ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=

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
SUPABASE_VOICE_TURNS_TABLE=voice_turns

DEEPGRAM_API_KEY=
DEEPGRAM_MODEL=nova-3
DEEPGRAM_LANGUAGE=en-US
DEEPGRAM_BASE_URL=https://api.deepgram.com/v1
DEEPGRAM_TIMEOUT_SECONDS=60

GOOGLE_TTS_PROJECT_ID=
GOOGLE_TTS_CREDENTIALS_JSON=
GOOGLE_APPLICATION_CREDENTIALS=
GOOGLE_TTS_BASE_URL=https://texttospeech.googleapis.com/v1
GOOGLE_TTS_VOICE_NAME=en-US-Neural2-J
GOOGLE_TTS_LANGUAGE_CODE=en-US
GOOGLE_TTS_AUDIO_ENCODING=MP3
GOOGLE_TTS_SPEAKING_RATE=1.0
GOOGLE_TTS_PITCH=0.0
GOOGLE_TTS_TIMEOUT_SECONDS=60
```

Notes:

- `SUPABASE_SERVICE_ROLE_KEY` is used by the FastAPI backend and must never be shipped in Flutter.
- `SUPABASE_ANON_KEY` is documented for future client-side Supabase use, but the current backend does not require it.
- `DEEPGRAM_API_KEY` and Google TTS credentials are used by the FastAPI backend and must never be shipped in Flutter.
- Prefer `GOOGLE_APPLICATION_CREDENTIALS` on the VPS when using a service-account JSON file. Use `GOOGLE_TTS_CREDENTIALS_JSON` only when environment-managed JSON is operationally simpler.
- Google TTS setup details are in `docs/google_tts_setup.md`.
- Native mobile apps do not rely on browser CORS, but CORS matters for Flutter Web and browser-based testing.
- In production, set `CORS_ALLOWED_ORIGINS` to exact HTTPS origins if you expose a web client. Do not use `*` with credentials.

## Supabase

Run the SQL in `backend/supabase_schema.sql` in the Supabase SQL editor before sending real chat traffic.

Tables:

- `conversations`
- `messages`
- `long_term_memory`
- `voice_turns`

## VPS Deployment

From the server:

```sh
cd /opt/rex
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run once manually:

```sh
cd /opt/rex
set -a
. ./.env
set +a
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use this `systemd` unit as a starting point:

```ini
[Unit]
Description=Rex FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/rex
EnvironmentFile=/opt/rex/.env
Environment=PYTHONPATH=/opt/rex/backend
ExecStart=/opt/rex/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Install it:

```sh
sudo cp rex.service /etc/systemd/system/rex.service
sudo systemctl daemon-reload
sudo systemctl enable rex
sudo systemctl start rex
sudo systemctl status rex
```

## Reverse Proxy and HTTPS

Put Nginx or Caddy in front of Uvicorn.

Example Nginx location block:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Important for streaming responses.
    proxy_buffering off;
    proxy_cache off;
}
```

Use HTTPS in production. Mobile networking is more reliable with a real HTTPS backend URL.

## Flutter Backend URLs

Local simulator:

```sh
flutter run --dart-define=REX_BACKEND_URL=http://localhost:8000
```

Physical phone on the same Wi-Fi:

```sh
flutter run --dart-define=REX_BACKEND_URL=http://YOUR_LAN_IP:8000
```

Production:

```sh
flutter run --dart-define=REX_BACKEND_URL=https://api.your-domain.com
```

Build production app artifacts with the same `--dart-define` value.

## Smoke Tests

Backend health:

```sh
curl https://api.your-domain.com/
```

Backend readiness:

```sh
curl https://api.your-domain.com/ready
```

Non-streaming chat:

```sh
curl -X POST https://api.your-domain.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Rex"}'
```

Streaming chat:

```sh
curl -N -X POST https://api.your-domain.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Rex","stream":true}'
```

## Production Checklist

- `.env` exists on the server and is not committed.
- `GROK_API_KEY`, `GROK_MODEL`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` are set.
- `DEEPGRAM_API_KEY`, `GOOGLE_TTS_PROJECT_ID`, and one Google credential method are set before enabling cloud voice.
- Supabase SQL schema has been applied.
- Backend service starts through `systemd`.
- Reverse proxy has HTTPS enabled.
- Streaming responses are not buffered by the reverse proxy.
- Flutter is built with the production `REX_BACKEND_URL`.
