alter table public.commitments
  add column if not exists milestone_id uuid
  references public.plan_milestones(id) on delete set null;

create index if not exists commitments_milestone_idx
  on public.commitments (milestone_id);
