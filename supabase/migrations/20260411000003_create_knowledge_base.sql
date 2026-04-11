create table if not exists public.knowledge_base (
    id uuid primary key default gen_random_uuid(),
    location_id text not null,
    slug text not null,
    title text not null,
    content text not null,
    size_bytes integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(location_id, slug)
);

create index if not exists kb_location_idx on public.knowledge_base (location_id);
create index if not exists kb_slug_idx on public.knowledge_base (location_id, slug);
