# Cloud Voice Contract

## Goal
Define the Rex voice contracts for both the final streaming call architecture and the fallback upload-per-turn cloud voice path.

## Target Streaming Pipeline

```text
iPhone microphone
-> Flutter streams audio frames continuously
-> FastAPI WebSocket voice session
-> Deepgram live streaming transcription
-> FastAPI emits partial/final transcript events
-> Final transcript enters ChatService / PromptService / Grok / Supabase memory
-> Grok streams response tokens
-> Backend chunks response into speakable phrases/sentences
-> Google TTS generates audio chunks
-> FastAPI streams audio chunks back to Flutter
-> Flutter plays chunks while the session stays open
```

## Fallback Upload Pipeline

```text
Flutter audio capture
-> POST /voice/turn
-> Deepgram STT
-> ChatService / PromptService / Grok / Supabase memory
-> Google TTS
-> Flutter audio playback
```

This fallback is working and should remain available for debugging, vendor outage fallback, and non-streaming regression tests. It is not the final street/pocket call architecture.

## Streaming Request Contract

Endpoint:

```text
WebSocket /voice/stream
```

Client-to-server events:

- `session.start`: starts a voice session with optional `conversation_id`, audio format, and client metadata.
- `audio.chunk`: sends a small base64 or binary microphone frame.
- `audio.end_utterance`: optional manual endpoint marker when Flutter detects end of speech.
- `user.interrupt`: cancels the current assistant response and queued TTS work.
- `session.end`: ends the call and closes the backend session cleanly.

Server-to-client events:

- `session.started`: confirms the backend session is ready.
- `transcript.partial`: live Deepgram transcript text for UI feedback.
- `transcript.final`: final utterance text that will enter ChatService.
- `assistant.token`: streamed Grok token/text delta.
- `assistant.audio_chunk`: Google TTS audio chunk for playback queue.
- `assistant.done`: final message metadata and conversation ID.
- `error`: normalized error object safe to show in the Flutter UI.

Streaming audio requirements:

- Flutter sends short microphone frames continuously while listening.
- FastAPI forwards frames to Deepgram live STT without exposing the Deepgram key.
- Backend chunks Grok text into speakable phrases/sentences for Google TTS.
- Flutter queues and plays returned audio chunks in order.
- Raw audio is not stored by default.

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
