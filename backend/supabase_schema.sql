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

create index if not exists long_term_memory_active_importance_idx
  on public.long_term_memory (active, importance desc, last_accessed_at desc);

create index if not exists long_term_memory_source_conversation_idx
  on public.long_term_memory (source_conversation_id);

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
