create extension if not exists pgcrypto;

create table if not exists public.rooms (
    id uuid primary key default gen_random_uuid(),
    code text not null unique check (code ~ '^[A-Z0-9]{6}$'),
    host_token text not null,
    current_winner_player_id uuid,
    current_round integer not null default 1 check (current_round > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.players (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.rooms(id) on delete cascade,
    name text not null check (char_length(name) between 1 and 32),
    socket_sid text,
    is_host boolean not null default false,
    is_connected boolean not null default false,
    joined_at timestamptz not null default now(),
    last_seen timestamptz not null default now()
);

create table if not exists public.scores (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.rooms(id) on delete cascade,
    player_id uuid not null references public.players(id) on delete cascade,
    wins integer not null default 0 check (wins >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (player_id),
    unique (room_id, player_id)
);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'rooms_current_winner_player_id_fkey'
    ) then
        alter table public.rooms
            add constraint rooms_current_winner_player_id_fkey
            foreign key (current_winner_player_id)
            references public.players(id)
            on delete set null;
    end if;
end;
$$;

create index if not exists idx_rooms_code on public.rooms(code);
create index if not exists idx_players_room_id on public.players(room_id);
create index if not exists idx_players_socket_sid on public.players(socket_sid);
create index if not exists idx_scores_room_id on public.scores(room_id);
create index if not exists idx_scores_player_id on public.scores(player_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_rooms_updated_at on public.rooms;
create trigger set_rooms_updated_at
before update on public.rooms
for each row
execute function public.set_updated_at();

drop trigger if exists set_scores_updated_at on public.scores;
create trigger set_scores_updated_at
before update on public.scores
for each row
execute function public.set_updated_at();

alter table public.rooms enable row level security;
alter table public.players enable row level security;
alter table public.scores enable row level security;

revoke all on public.rooms from anon, authenticated;
revoke all on public.players from anon, authenticated;
revoke all on public.scores from anon, authenticated;
