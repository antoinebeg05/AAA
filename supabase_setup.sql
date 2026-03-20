-- ─────────────────────────────────────────────
-- Biogenie — Setup Supabase
-- À coller dans : Supabase > SQL Editor > New query
-- ─────────────────────────────────────────────

-- Table CRM principale
create table if not exists crm (
  terrain_id          text primary key,
  contact_nom         text default '',
  contact_tel         text default '',
  contact_email       text default '',
  contact_entreprise  text default '',
  dossier_status      text default '',
  note                text default '',
  is_archived         boolean default false,
  is_treated          boolean default false,
  reminder_date       date,
  reminder_sent       boolean default false,
  updated_at          timestamptz default now()
);

-- Historique des notes
create table if not exists crm_historique (
  id          bigserial primary key,
  terrain_id  text not null,
  note        text not null,
  created_at  timestamptz default now()
);

-- Changements de statut détectés automatiquement
create table if not exists gtc_changes (
  id              bigserial primary key,
  terrain_id      text not null,
  adresse         text default '',
  municipalite    text default '',
  ancien_statut   text default '',
  nouveau_statut  text not null,
  detecte_le      timestamptz default now()
);

-- Accès public en lecture/écriture (dashboard frontend)
alter table crm enable row level security;
alter table crm_historique enable row level security;
alter table gtc_changes enable row level security;

create policy "Public" on crm
  for all to anon using (true) with check (true);

create policy "Public" on crm_historique
  for all to anon using (true) with check (true);

create policy "Public" on gtc_changes
  for all to anon using (true) with check (true);

-- Ajouter les colonnes si tu as déjà la table crm existante (ignorer les erreurs si déjà présentes)
alter table crm add column if not exists reminder_date date;
alter table crm add column if not exists reminder_sent boolean default false;

-- ── NOUVELLES COLONNES — Propriétaire + Plan réhabilitation ──
alter table crm add column if not exists prop_nom         text default '';
alter table crm add column if not exists prop_tel         text default '';
alter table crm add column if not exists prop_email       text default '';
alter table crm add column if not exists prop_source      text default '';
alter table crm add column if not exists plan_type        text default '';
alter table crm add column if not exists plan_date        date;
alter table crm add column if not exists plan_responsable text default '';
alter table crm add column if not exists plan_notes       text default '';
