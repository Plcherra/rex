# Cloud Voice Contract

## Goal
Define the first production voice contract for Rex before implementing Deepgram STT and Google TTS.

## Pipeline

```text
Flutter audio capture
-> POST /voice/turn
-> Deepgram STT
-> ChatService / PromptService / Grok / Supabase memory
-> Google TTS
-> Flutter audio playback
```

## MVP Request Contract

Endpoint:

```text
POST /voice/turn
Content-Type: multipart/form-data
```

Fields:

- `audio`: required audio file/blob.
- `conversation_id`: optional existing conversation ID.
- `input_mime_type`: optional explicit audio MIME type when the upload library does not provide one.

Recommended first upload formats:

- Preferred iOS/mobile: `audio/mp4` or `audio/aac` from `.m4a`.
- Test/dev fallback: `audio/wav`.

Limits:

- Maximum recording duration: 120 seconds for MVP.
- Maximum upload size: 10 MB for MVP.
- Empty or near-silent audio should return a clear validation error.
- Raw audio should not be stored by default.

## MVP Response Contract

Recommended first response:

```json
{
  "conversation_id": "uuid",
  "transcript": "what the user said",
  "transcript_confidence": 0.94,
  "response_text": "what Rex said",
  "audio_content_type": "audio/mpeg",
  "audio_base64": "...",
  "voice_metadata": {
    "stt": {},
    "tts": {},
    "record": {}
  }
}
```

Recommended first playback format:

- Google TTS output: `MP3`
- Response content type in JSON: `audio/mpeg`

Why JSON + base64 for MVP:

- Easy to test in Flutter.
- Easy to mock in backend route tests.
- Avoids managing temporary object storage before the voice loop works.

Future upgrade:

- Return streaming audio bytes or a short-lived Supabase Storage URL when responses become longer or latency becomes a problem.

Supporting MVP endpoints:

- `POST /voice/transcribe`: audio upload to Deepgram transcript JSON.
- `POST /voice/synthesize`: text to Google TTS base64 audio JSON.
- `POST /voice/turn`: full non-streaming voice turn, using JSON + base64 audio for MVP.

## Backend Responsibilities

FastAPI must:

- Own Deepgram and Google credentials.
- Validate upload size and content type.
- Send audio to Deepgram with the correct MIME type.
- Pass the transcript into the existing `ChatService`.
- Preserve existing conversation and memory behavior.
- Generate Google TTS audio from Rex's final text.
- Return transcript, response text, audio metadata, and playable audio.
- Store only useful voice metadata in Supabase, not raw audio by default.

## Flutter Responsibilities

Flutter must:

- Capture audio in a supported format.
- Send audio to FastAPI, not directly to Deepgram.
- Show clear states: recording, uploading, transcribing, thinking, generatingSpeech, speaking, failed.
- Play returned Google TTS audio.
- Keep local `speech_to_text` and `flutter_tts` only as fallback/dev tools.

## Supabase Metadata

Recommended future table: `voice_turns`.

Fields:

- `id`
- `conversation_id`
- `user_message_id`
- `assistant_message_id`
- `transcript_confidence`
- `audio_duration_seconds`
- `input_mime_type`
- `output_audio_encoding`
- `stt_vendor`
- `tts_vendor`
- `created_at`

Do not store raw audio unless there is an explicit debugging or product reason.

## Failure Contract

Common failures should map to clear user-facing messages:

- Backend not running: "Could not reach Rex."
- Deepgram missing config: "Voice transcription is not configured."
- Google TTS missing config: "Voice playback is not configured."
- Grok capacity: show the xAI capacity message.
- Empty audio: "I did not catch any audio."
- Upload too large: "Voice recording is too long."

## Revision History
- 2026-05-15 - Initial cloud voice contract for Deepgram + Grok + Google TTS.
