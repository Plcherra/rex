# Deepgram Streaming Design

## Goal
Define how Rex should move from the Phase 1 upload/chunk transcription route to real low-latency speech recognition for street and pocket use.

## Current Phase 1 Decision
Start with a backend-proxied prerecorded/chunk endpoint:

```text
Flutter records a short audio segment
-> POST /voice/transcribe
-> FastAPI validates audio
-> FastAPI sends bytes to Deepgram /v1/listen
-> FastAPI returns transcript JSON
```

This keeps the first implementation simple, testable, and secure. Flutter never receives a Deepgram API key, and normal backend tests can fully mock the vendor call.

## Streaming Options

### Option A - Flutter -> FastAPI WebSocket -> Deepgram WebSocket

Flutter streams microphone chunks to FastAPI. FastAPI opens a Deepgram streaming connection, forwards audio chunks, receives interim/final transcripts, and sends transcript events back to Flutter.

Benefits:

- Deepgram API key stays only on the backend.
- FastAPI can attach conversation/session metadata.
- Backend can enforce limits, logging, and future memory metadata.
- Better for founder privacy and observability.

Costs:

- More backend code.
- Requires robust WebSocket lifecycle handling.
- Needs careful timeout, reconnect, and cancellation handling.

### Option B - FastAPI Issues Short-Lived Deepgram Token

FastAPI creates a short-lived Deepgram token. Flutter connects directly to Deepgram streaming with that token.

Benefits:

- Lower backend bandwidth.
- Less backend audio proxy code.
- Potentially lower latency.

Costs:

- More complicated credential/token lifecycle.
- Harder backend observability.
- More client-side vendor coupling.
- More care needed to prevent leaked or over-permissive tokens.

## Recommendation
Use **Option A** for Rex's first production streaming path.

Rex is a private personal assistant with sensitive audio and memory. Keeping Deepgram behind FastAPI is the cleaner default: secrets stay server-side, behavior is easier to test, and the backend can later connect transcript timing, confidence, conversation IDs, and memory extraction without trusting the mobile client.

Short-lived direct Deepgram tokens can be revisited later if backend proxy latency or bandwidth becomes a real problem.

## Event Shape For Future Streaming

Recommended backend-to-Flutter events:

```json
{"event":"listening_started","voice_session_id":"..."}
{"event":"partial_transcript","text":"I need to talk about","confidence":0.81}
{"event":"final_transcript","text":"I need to talk about my budget.","confidence":0.94}
{"event":"thinking","conversation_id":"..."}
{"event":"token","text":"You said last week..."}
{"event":"speech_audio_chunk","content_type":"audio/mpeg","audio_base64":"..."}
{"event":"done","conversation_id":"..."}
{"event":"error","detail":"Cannot reach Deepgram right now."}
```

## Phase 1 Limitation
The current `/voice/transcribe` route is not live streaming. It is intentionally a secure upload/chunk MVP so Rex can prove Deepgram transcription before adding long-running WebSocket sessions and background audio behavior.

## Revision History
- 2026-05-15 - Initial Deepgram streaming architecture decision.
