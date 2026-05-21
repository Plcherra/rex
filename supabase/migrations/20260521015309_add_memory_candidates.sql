create table if not exists public.memory_candidates (
  id uuid primary key default gen_random_uuid(),
  candidate_type text not null check (
    candidate_type in (
      'long_term_memory',
      'entity',
      'entity_event',
      'personal_rule',
      'plan',
      'plan_milestone',
      'commitment',
      'correction',
      'archive',
      'merge'
    )
  ),
  payload jsonb not null,
  status text not null default 'pending' check (
    status in ('pending', 'approved', 'rejected', 'applied', 'failed')
  ),
  risk_level text not null default 'medium' check (
    risk_level in ('low', 'medium', 'high')
  ),
  decision jsonb,
  reason text,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  approved_by text,
  approved_at timestamptz,
  applied_at timestamptz,
  rejected_at timestamptz,
  applied_record_table text,
  applied_record_id uuid,
  verification jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memory_candidates_status_created_idx
  on public.memory_candidates (status, created_at desc);

create index if not exists memory_candidates_source_status_created_idx
  on public.memory_candidates (source_conversation_id, status, created_at desc);

create index if not exists memory_candidates_type_status_idx
  on public.memory_candidates (candidate_type, status);

create index if not exists memory_candidates_risk_status_idx
  on public.memory_candidates (risk_level, status);

drop trigger if exists set_memory_candidates_updated_at on public.memory_candidates;

create trigger set_memory_candidates_updated_at
before update on public.memory_candidates
for each row
execute function public.set_updated_at();
