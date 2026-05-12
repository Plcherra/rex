# Action Plan 6 - General File Upload & Contextual Memory

## Goal
Allow the user to upload various simple files (budget CSVs, .txt files with rhymes, notes, documents, etc.) and have them added to the current conversation context or stored as long-term memory.

## Why This Matters (Personal Context)
This phase makes Rex much more useful in real life. The founder can say “I just uploaded my new budget” or “I uploaded a .txt with some rhymes I wrote” and Rex will understand the content, reference it in conversation, and optionally turn it into long-term memory. This closes the loop on practical daily use cases like Clarity CSV budgets, creative writing, meeting notes, immigration documents, etc.

## Key Deliverables
- Improve and generalize the existing file upload flow
- Support common file types and make upload part of natural conversation flow
- Allow the user to upload files and have Rex understand/reference the content
- Basic file content extraction so files can be used in context or turned into memory candidates
- Store file metadata and link it to conversations or long-term memory

## Estimated Time
4-7 focused days (solo founder pace)

## Dependencies
Action Plan 3 (structured memory) and Action Plan 1 (PromptService) should be complete.

## Checklist (10 Actionable Steps)

1. [ ] **Audit current file upload flow and limits**
   - Exact files to create or modify: `backend/app/services/file_service.py`, `backend/app/services/chat_service.py`, `backend/app/routes/chat.py`, `lib/services/chat_api.dart`, `lib/features/chat/domain/chat_attachment.dart`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`
   - What must be implemented: Review the existing upload path for supported extensions, size limits, UTF-8 assumptions, multipart handling, prompt injection, Flutter validation, and test coverage. Identify what can stay backward compatible and what needs to become more generic.
   - Success criteria: The current upload behavior is documented in implementation notes or TODOs, and no runtime behavior changes are made during this audit step.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `docs: audit current file upload flow`
   - Rough time estimate: 1-2 hours

2. [ ] **Design file metadata schema**
   - Exact files to create or modify: `backend/supabase_schema.sql`, optionally `docs/memory_retrieval.md`
   - What must be implemented: Add a `uploaded_files` table or equivalent schema for file ID, conversation ID, source message ID, filename, extension, MIME type, size, content hash, extracted text preview, storage status, memory link status, timestamps, and metadata.
   - Success criteria: File metadata can be linked to conversations, messages, long-term memories, entities, rules, plans, or commitments without changing existing `messages` and `long_term_memory` behavior.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add uploaded file metadata schema`
   - Rough time estimate: 2-4 hours

3. [ ] **Create backend file models and repository methods**
   - Exact files to create or modify: `backend/app/models/file.py`, `backend/app/services/memory_service.py`, optionally `backend/app/services/file_metadata_service.py`
   - What must be implemented: Add Pydantic models and async Supabase helpers for creating, reading, updating, listing, and deactivating uploaded file metadata. Keep actual file content handling separate from metadata persistence.
   - Success criteria: File metadata can be saved and retrieved through testable backend methods without calling real Supabase in tests.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add uploaded file metadata models`
   - Rough time estimate: 3-5 hours

4. [ ] **Generalize backend file validation**
   - Exact files to create or modify: `backend/app/services/file_service.py`, `tests/test_file_service.py`, existing chat route tests
   - What must be implemented: Expand validation into a clean policy that supports safe simple file types such as `.txt`, `.md`, `.csv`, and other intentionally approved document-like formats if chosen. Validate extension, MIME type when available, max size, encoding, empty files, and suspicious binary content.
   - Success criteria: Invalid files are rejected before persistence, backend error messages are normalized and user-friendly, and existing `.txt`, `.md`, and `.csv` flows continue working.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_file_service.py`
   - Suggested git commit message: `feat: generalize backend file validation`
   - Rough time estimate: 3-5 hours

5. [ ] **Add safe content extraction service**
   - Exact files to create or modify: `backend/app/services/file_content_service.py`, `backend/app/services/file_service.py`, `tests/test_file_content_service.py`
   - What must be implemented: Create a service that extracts safe text from supported files, normalizes line endings, trims excessive content, detects likely CSV structure, creates previews, and returns extraction warnings when content is too large or partially skipped.
   - Success criteria: Rex can safely extract useful text from notes, rhymes, markdown, and budget CSVs while enforcing a prompt-safe maximum length.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_file_content_service.py`
   - Suggested git commit message: `feat: add file content extraction service`
   - Rough time estimate: 4-7 hours

6. [ ] **Integrate file metadata and extracted content into chat**
   - Exact files to create or modify: `backend/app/services/chat_service.py`, `backend/app/services/prompt_service.py`, `backend/app/services/file_content_service.py`, `backend/app/services/memory_service.py`, `backend/app/routes/chat.py`
   - What must be implemented: When a file is uploaded with a chat message, validate it, extract text, save metadata, link it to the conversation/message, and pass a compact file context section into `PromptService`.
   - Success criteria: The existing multipart `/chat` flow still works, uploaded file context is visible to Grok, metadata is persisted only after validation succeeds, and failures do not create broken chat history.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: link uploaded files to chat context`
   - Rough time estimate: 5-8 hours

7. [ ] **Add optional file-to-memory candidate extraction**
   - Exact files to create or modify: `backend/app/services/memory_extraction_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/prompt_service.py`, `tests/test_memory_extraction.py`
   - What must be implemented: Extend memory extraction so file content can produce memory candidates when appropriate, while avoiding noisy storage for temporary or irrelevant files. Include source metadata so the memory can point back to the uploaded file and conversation.
   - Success criteria: Important facts from notes, budget summaries, immigration documents, or creative writing context can become long-term memory candidates, but low-value file contents do not flood memory.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_memory_extraction.py`
   - Suggested git commit message: `feat: extract memory candidates from files`
   - Rough time estimate: 4-7 hours

8. [ ] **Improve Flutter upload UX for general files**
   - Exact files to create or modify: `lib/features/chat/domain/chat_attachment.dart`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`, `lib/features/chat/presentation/pages/chat_page.dart`, `lib/services/chat_api.dart`
   - What must be implemented: Update the attachment picker and preview UI to clearly support general simple files, show name/type/size, keep invalid selections visible until removed, and let the user naturally describe what the file is for in the same message.
   - Success criteria: The user can upload a budget CSV, notes file, or rhyme text file with a normal chat message, and the UI clearly communicates validation, upload progress, errors, and removal.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: improve general file upload ux`
   - Rough time estimate: 4-7 hours

9. [ ] **Add backend and Flutter tests for generalized uploads**
   - Exact files to create or modify: `tests/test_chat_routes.py`, `tests/test_file_service.py`, `tests/test_file_content_service.py`, `test/features/chat/`, existing upload tests
   - What must be implemented: Add coverage for valid `.txt`, `.md`, `.csv`, invalid file type, oversized file, non-UTF8 file, empty file, metadata persistence, prompt context injection, Flutter validation, and upload error handling.
   - Success criteria: Tests cover the main success and failure paths without real Grok or Supabase calls, and existing chat/file tests remain passing.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `test: cover generalized file uploads`
   - Rough time estimate: 5-8 hours

10. [ ] **Run full validation and manual contextual file test**
    - Exact files to create or modify: No code changes expected unless validation exposes bugs
    - What must be implemented: Run full backend and Flutter validation, then manually test realistic flows: upload a budget CSV, upload a `.txt` with rhymes, upload notes, ask Rex to summarize/reference each file, and confirm useful memory candidates are created only when appropriate.
    - Success criteria: Backend tests pass, Flutter tests pass, existing chat/memory behavior remains backward compatible, file context is naturally referenced by Rex, and metadata links are saved correctly.
    - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
    - Suggested git commit message: `test: validate contextual file memory flow`
    - Rough time estimate: 3-5 hours

## Revision History
- 2026-05-12 - Action Plan 6 created from Alignment Plan and updated REX_VISION.md
