create extension if not exists pgcrypto;

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  title text,
  timestamp timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  timestamp timestamptz not null default now()
);

create index if not exists messages_conversation_timestamp_idx
  on public.messages (conversation_id, timestamp desc);

create table if not exists public.long_term_memory (
  id uuid primary key default gen_random_uuid(),
  memory_type text not null check (
    memory_type in ('fact', 'preference', 'event')
  ),
  content text not null,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  importance integer not null default 3 check (importance between 1 and 5),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now()
);

alter table public.long_term_memory
  add column if not exists superseded_by uuid references public.long_term_memory(id) on delete set null,
  add column if not exists confidence numeric not null default 0.75 check (confidence between 0 and 1),
  add column if not exists correction_group text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists long_term_memory_active_importance_idx
  on public.long_term_memory (active, importance desc, last_accessed_at desc);

create index if not exists long_term_memory_source_conversation_idx
  on public.long_term_memory (source_conversation_id);

create index if not exists long_term_memory_correction_group_idx
  on public.long_term_memory (correction_group)
  where correction_group is not null;

create table if not exists public.memory_corrections (
  id uuid primary key default gen_random_uuid(),
  correction_type text not null check (
    correction_type in (
      'entity_name',
      'entity_relationship',
      'plan_detail',
      'rule_detail',
      'commitment_detail',
      'location',
      'preference',
      'other'
    )
  ),
  old_value text,
  new_value text not null,
  target_table text,
  target_id uuid,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  applied boolean not null default false,
  confidence numeric not null default 0.9 check (confidence between 0 and 1),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists memory_corrections_target_idx
  on public.memory_corrections (target_table, target_id);

create index if not exists memory_corrections_created_idx
  on public.memory_corrections (created_at desc);

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

create table if not exists public.entities (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null check (
    entity_type in (
      'person',
      'place',
      'organization',
      'job',
      'project',
      'object',
      'topic',
      'other'
    )
  ),
  display_name text not null,
  normalized_name text not null,
  aliases text[] not null default '{}'::text[],
  relationship text,
  summary text,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  importance integer not null default 3 check (importance between 1 and 5),
  status text not null default 'active' check (
    status in ('active', 'inactive', 'archived')
  ),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists entities_active_normalized_name_idx
  on public.entities (entity_type, normalized_name)
  where active = true;

create index if not exists entities_active_importance_idx
  on public.entities (active, importance desc, last_seen_at desc);

create index if not exists entities_source_conversation_idx
  on public.entities (source_conversation_id);

comment on column public.entities.metadata is
  'Entity normalization metadata. Supported keys include canonical_entity_id, alias_source, obsolete_aliases, obsolete_names, removed_wrong_aliases, and correction_confidence.';

create table if not exists public.entity_events (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid not null references public.entities(id) on delete cascade,
  event_type text not null default 'note' check (
    event_type in (
      'note',
      'interaction',
      'relationship_update',
      'preference',
      'commitment',
      'conflict',
      'milestone',
      'other'
    )
  ),
  title text,
  content text not null,
  occurred_at timestamptz,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  importance integer not null default 3 check (importance between 1 and 5),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists entity_events_entity_created_idx
  on public.entity_events (entity_id, created_at desc);

create index if not exists entity_events_active_importance_idx
  on public.entity_events (active, importance desc, created_at desc);

create table if not exists public.personal_rules (
  id uuid primary key default gen_random_uuid(),
  rule_type text not null check (
    rule_type in (
      'finance',
      'transport',
      'food_delivery',
      'coffee',
      'rent',
      'health',
      'dating',
      'work',
      'immigration',
      'personal',
      'other'
    )
  ),
  title text not null,
  rule_text text not null,
  trigger_keywords text[] not null default '{}'::text[],
  enforcement_style text not null default 'gentle_direct' check (
    enforcement_style in ('gentle_direct', 'strict', 'reminder_only')
  ),
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  priority integer not null default 3 check (priority between 1 and 5),
  status text not null default 'active' check (
    status in ('active', 'paused', 'broken', 'archived')
  ),
  active boolean not null default true,
  starts_at timestamptz,
  ends_at timestamptz,
  last_checked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists personal_rules_active_priority_idx
  on public.personal_rules (active, priority desc, updated_at desc);

create index if not exists personal_rules_rule_type_idx
  on public.personal_rules (rule_type, active);

create table if not exists public.plans (
  id uuid primary key default gen_random_uuid(),
  plan_type text not null check (
    plan_type in (
      'finance',
      'immigration',
      'career',
      'health',
      'dating',
      'housing',
      'creative',
      'personal',
      'other'
    )
  ),
  title text not null,
  description text,
  desired_outcome text,
  primary_entity_id uuid references public.entities(id) on delete set null,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  priority integer not null default 3 check (priority between 1 and 5),
  status text not null default 'active' check (
    status in ('active', 'paused', 'completed', 'abandoned', 'archived')
  ),
  active boolean not null default true,
  start_date date,
  target_date date,
  completed_at timestamptz,
  last_reviewed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.plans
  add column if not exists primary_entity_id uuid references public.entities(id) on delete set null;

create index if not exists plans_active_priority_idx
  on public.plans (active, priority desc, updated_at desc);

create index if not exists plans_primary_entity_idx
  on public.plans (primary_entity_id);

create index if not exists plans_status_target_date_idx
  on public.plans (status, target_date);

create table if not exists public.plan_milestones (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.plans(id) on delete cascade,
  title text not null,
  description text,
  milestone_type text not null default 'checkpoint' check (
    milestone_type in ('goal', 'deadline', 'checkpoint', 'task', 'other')
  ),
  target_date date,
  completed_at timestamptz,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  priority integer not null default 3 check (priority between 1 and 5),
  status text not null default 'open' check (
    status in ('open', 'in_progress', 'completed', 'missed', 'canceled')
  ),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists plan_milestones_plan_target_idx
  on public.plan_milestones (plan_id, target_date);

create index if not exists plan_milestones_active_status_idx
  on public.plan_milestones (active, status, target_date);

create table if not exists public.commitments (
  id uuid primary key default gen_random_uuid(),
  commitment_type text not null check (
    commitment_type in (
      'task',
      'habit',
      'promise',
      'money',
      'health',
      'relationship',
      'work',
      'immigration',
      'deadline',
      'other'
    )
  ),
  title text not null,
  commitment_text text not null,
  plan_id uuid references public.plans(id) on delete set null,
  milestone_id uuid references public.plan_milestones(id) on delete set null,
  entity_id uuid references public.entities(id) on delete set null,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  source_memory_id uuid references public.long_term_memory(id) on delete set null,
  priority integer not null default 3 check (priority between 1 and 5),
  status text not null default 'open' check (
    status in ('open', 'in_progress', 'completed', 'missed', 'canceled', 'archived')
  ),
  active boolean not null default true,
  due_at timestamptz,
  completed_at timestamptz,
  last_checked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists commitments_active_due_idx
  on public.commitments (active, status, due_at);

create index if not exists commitments_plan_idx
  on public.commitments (plan_id);

create index if not exists commitments_milestone_idx
  on public.commitments (milestone_id);

create index if not exists commitments_entity_idx
  on public.commitments (entity_id);

create table if not exists public.voice_turns (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_message_id uuid references public.messages(id) on delete set null,
  assistant_message_id uuid references public.messages(id) on delete set null,
  transcript_confidence numeric,
  audio_duration_seconds numeric,
  input_mime_type text,
  output_audio_encoding text,
  stt_vendor text not null default 'deepgram',
  tts_vendor text not null default 'google_tts',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists voice_turns_conversation_created_idx
  on public.voice_turns (conversation_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_long_term_memory_updated_at on public.long_term_memory;

create trigger set_long_term_memory_updated_at
before update on public.long_term_memory
for each row
execute function public.set_updated_at();

drop trigger if exists set_entities_updated_at on public.entities;

drop trigger if exists set_memory_candidates_updated_at on public.memory_candidates;

create trigger set_memory_candidates_updated_at
before update on public.memory_candidates
for each row
execute function public.set_updated_at();

create trigger set_entities_updated_at
before update on public.entities
for each row
execute function public.set_updated_at();

drop trigger if exists set_entity_events_updated_at on public.entity_events;

create trigger set_entity_events_updated_at
before update on public.entity_events
for each row
execute function public.set_updated_at();

drop trigger if exists set_personal_rules_updated_at on public.personal_rules;

create trigger set_personal_rules_updated_at
before update on public.personal_rules
for each row
execute function public.set_updated_at();

drop trigger if exists set_plans_updated_at on public.plans;

create trigger set_plans_updated_at
before update on public.plans
for each row
execute function public.set_updated_at();

drop trigger if exists set_plan_milestones_updated_at on public.plan_milestones;

create trigger set_plan_milestones_updated_at
before update on public.plan_milestones
for each row
execute function public.set_updated_at();

drop trigger if exists set_commitments_updated_at on public.commitments;

create trigger set_commitments_updated_at
before update on public.commitments
for each row
execute function public.set_updated_at();
