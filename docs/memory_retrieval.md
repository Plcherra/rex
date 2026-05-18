# Memory Retrieval Notes

Rex currently uses a lightweight relevance scorer for long-term memory recall.

The scorer expands the current user message and each memory into normalized keywords,
adds a few hand-written concept groups such as work, money, relationships,
immigration, and stress, then ranks matching active memories by:

- keyword/concept overlap with the current message
- saved memory importance
- recency based on `last_accessed_at` or `created_at`

Returned memories include `relevance_score` and `relevance_reason` so a future UI can
explain why a memory was recalled.

Current limitations:

- No embeddings yet, so meaning is approximated with keywords and concept groups.
- Matching can miss paraphrases outside the hand-written concept groups.
- Preference memories with high importance may be included even without direct keyword
  overlap because answer-style preferences are usually relevant across turns.
- Recency is based on stored timestamps, but recalled memories are not yet marked as
  accessed after retrieval.
- Structured memory tables now exist for entities, entity events, personal rules,
  plans, plan milestones, and commitments, but retrieval still needs service logic
  before those records are injected into prompts.

Future path:

- Retrieve structured memory before generic fallback memory: known people/entities,
  active rules, active plans, upcoming milestones, and open commitments.
- Link structured records back to source conversations, messages, and generic
  long-term memory so Rex can explain where context came from.
- Add embeddings for every long-term memory row.
- Store vectors in Supabase with `pgvector`.
- Use vector similarity plus metadata filters for semantic retrieval.
- Keep the current keyword/importance/recency score as a fallback and tie-breaker.
- Record recall events so the memory UI can show when and why Rex used a memory.
