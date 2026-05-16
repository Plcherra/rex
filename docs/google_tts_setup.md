# Google TTS Setup

## Goal
Configure Google Cloud Text-to-Speech for Rex without shipping Google credentials in Flutter.

## Recommended Auth Method
Use a Google Cloud service account JSON file and set:

```env
GOOGLE_APPLICATION_CREDENTIALS=/opt/rex/secrets/google-tts-service-account.json
GOOGLE_TTS_PROJECT_ID=your-google-cloud-project-id
```

This is the preferred VPS setup because the JSON file can live outside the repo, file permissions can be locked down, and the `.env` only stores a path.

## Alternative Auth Method
For local development or environments where file mounts are awkward, put the full service-account JSON in:

```env
GOOGLE_TTS_CREDENTIALS_JSON='{"type":"service_account",...}'
GOOGLE_TTS_PROJECT_ID=your-google-cloud-project-id
```

Do not commit this value. Keep it only in ignored environment files or secret managers.

## Required Google Cloud Setup
1. Enable the Cloud Text-to-Speech API in the Google Cloud project.
2. Create a service account for Rex backend voice synthesis.
3. Grant the service account enough permission to call Cloud Text-to-Speech. For a private MVP, project-level Text-to-Speech access is acceptable; tighten IAM later if Google exposes a narrower role in your project.
4. Download the service-account JSON key.
5. Store the JSON key outside the repo and point `GOOGLE_APPLICATION_CREDENTIALS` to it.

## Backend Behavior
Rex uses the Google Cloud Text-to-Speech REST endpoint:

```text
POST https://texttospeech.googleapis.com/v1/text:synthesize
```

The backend exchanges the service-account credentials for an OAuth access token, sends the text, voice, language, speaking rate, pitch, and encoding to Google, then returns base64 audio to Flutter.

## MVP Defaults
```env
GOOGLE_TTS_VOICE_NAME=en-US-Neural2-J
GOOGLE_TTS_LANGUAGE_CODE=en-US
GOOGLE_TTS_AUDIO_ENCODING=MP3
GOOGLE_TTS_SPEAKING_RATE=1.0
GOOGLE_TTS_PITCH=0.0
GOOGLE_TTS_TIMEOUT_SECONDS=60
```

`MP3` maps to `audio/mpeg` for Flutter playback.

## Local Smoke Test
After setting `.env`, run the backend and call:

```sh
curl -X POST http://127.0.0.1:8000/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Rex voice playback is configured."}'
```

The response should include:

```json
{
  "audio_content_type": "audio/mpeg",
  "audio_base64": "..."
}
```

## Revision History
- 2026-05-15 - Initial Google TTS backend setup guide.
