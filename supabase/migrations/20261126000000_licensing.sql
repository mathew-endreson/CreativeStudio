-- BluxTech Studio licensing: Supabase Auth identifies the user, one license row per user, one row per activated device.
-- The desktop app never writes these tables: the `license` Edge Function calls the functions below with the service
-- role, and sales grant licenses with grant_license() (SQL editor or scripts/grant.mjs).

create table public.licenses (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  email       text not null default '',
  status      text not null check (status in ('trial', 'active', 'expired', 'suspended')),
  plan        text not null default 'trial',
  expires_at  timestamptz,                       -- null = no end
  max_devices int  not null default 1 check (max_devices >= 0),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table public.license_devices (
  user_id     uuid not null references public.licenses (user_id) on delete cascade,
  device_id   text not null,
  name        text not null default 'PC',
  app_version text not null default '',
  first_seen  timestamptz not null default now(),
  last_seen   timestamptz not null default now(),
  primary key (user_id, device_id)
);

-- A signed-in user may read their own license and devices; nobody writes through the API.
alter table public.licenses enable row level security;
alter table public.license_devices enable row level security;
create policy "read own license" on public.licenses for select to authenticated using (user_id = (select auth.uid()));
create policy "read own devices" on public.license_devices for select to authenticated using (user_id = (select auth.uid()));
revoke insert, update, delete on public.licenses, public.license_devices from anon, authenticated;

-- ---------------------------------------------------------------- helpers

create function public.license_status(lic public.licenses) returns text
language sql stable set search_path = '' as $$
  select case when lic.status in ('trial', 'active') and lic.expires_at is not null and lic.expires_at < now()
              then 'expired' else lic.status end
$$;

-- What the Edge Function hands back to the app (times in milliseconds).
create function public.license_answer(p_user uuid) returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object(
    'status', public.license_status(l),
    'plan', l.plan,
    'expiresAt', (extract(epoch from l.expires_at) * 1000)::bigint,
    'maxDevices', l.max_devices,
    'devices', coalesce((select jsonb_agg(jsonb_build_object('id', d.device_id, 'name', d.name,
                                                             'lastSeen', (extract(epoch from d.last_seen) * 1000)::bigint)
                                          order by d.first_seen)
                         from public.license_devices d where d.user_id = l.user_id), '[]'::jsonb))
  from public.licenses l where l.user_id = p_user
$$;

-- ---------------------------------------------------------------- called by the Edge Function (service role)
-- Errors carry the app's error code in HINT: permission-denied, failed-precondition, resource-exhausted.

-- After sign-in: creates a trial for a new account, registers the device within the limit, refreshes last_seen.
create function public.activate_device(p_user uuid, p_email text, p_device text, p_name text, p_version text,
                                       p_trial_days int, p_trial_devices int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  lic public.licenses;
  st text;
  used int;
begin
  insert into public.licenses (user_id, email, status, plan, expires_at, max_devices)
  values (p_user, coalesce(p_email, ''), case when p_trial_days > 0 then 'trial' else 'expired' end, 'trial',
          now() + make_interval(days => greatest(p_trial_days, 0)), p_trial_devices)
  on conflict (user_id) do nothing;

  select * into lic from public.licenses where user_id = p_user for update;   -- serializes activations per user
  st := public.license_status(lic);
  if st = 'suspended' then raise exception 'This license is suspended.' using hint = 'permission-denied'; end if;
  if st = 'expired' then raise exception 'This license has expired.' using hint = 'failed-precondition'; end if;

  if not exists (select 1 from public.license_devices where user_id = p_user and device_id = p_device) then
    select count(*) into used from public.license_devices where user_id = p_user;
    if used >= lic.max_devices then
      raise exception 'This license allows % device(s). Deactivate one first.', lic.max_devices using hint = 'resource-exhausted';
    end if;
  end if;

  insert into public.license_devices (user_id, device_id, name, app_version)
  values (p_user, p_device, p_name, p_version)
  on conflict (user_id, device_id) do update set name = excluded.name, app_version = excluded.app_version, last_seen = now();
  update public.licenses set updated_at = now() where user_id = p_user;
  return public.license_answer(p_user);
end
$$;

-- A re-check from a device that is already registered (after the app's offline grace period).
create function public.check_device(p_user uuid, p_device text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select 1 from public.licenses where user_id = p_user) then
    raise exception 'No license for this account.' using hint = 'permission-denied';
  end if;
  update public.license_devices set last_seen = now() where user_id = p_user and device_id = p_device;
  if not found then raise exception 'This device is not activated.' using hint = 'failed-precondition'; end if;
  return public.license_answer(p_user);
end
$$;

-- Free a device slot.
create function public.deactivate_device(p_user uuid, p_device text) returns void
language sql security definer set search_path = '' as $$
  delete from public.license_devices where user_id = p_user and device_id = p_device;
  update public.licenses set updated_at = now() where user_id = p_user;
$$;

-- ---------------------------------------------------------------- sales (SQL editor, or scripts/grant.mjs)
--   select grant_license('user@example.com', p_plan => 'pro', p_days => 365, p_devices => 2);
--   select grant_license('user@example.com', p_status => 'suspended');
-- Giving a plan or days without a status makes the license active.
create function public.grant_license(p_email text, p_plan text default null, p_days int default null,
                                     p_devices int default null, p_status text default null)
returns public.licenses
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid;
  mail text;
  st text := coalesce(p_status, case when p_plan is not null or p_days is not null then 'active' end);
  lic public.licenses;
begin
  select u.id, u.email into uid, mail from auth.users u where lower(u.email) = lower(p_email);
  if uid is null then raise exception 'No account with the email %: the customer signs up in the app first.', p_email; end if;
  insert into public.licenses as l (user_id, email, status, plan, max_devices, expires_at)
  values (uid, coalesce(mail, p_email), coalesce(st, 'active'), coalesce(p_plan, 'pro'), coalesce(p_devices, 1),
          case when p_days is not null then now() + make_interval(days => p_days) end)
  on conflict (user_id) do update set
    email       = excluded.email,
    status      = coalesce(st, l.status),
    plan        = coalesce(p_plan, l.plan),
    max_devices = coalesce(p_devices, l.max_devices),
    expires_at  = case when p_days is not null then now() + make_interval(days => p_days) else l.expires_at end,
    updated_at  = now()
  returning * into lic;
  return lic;
end
$$;

-- Only the service role (the Edge Function, scripts/grant.mjs) and the SQL editor may call these.
revoke execute on function public.activate_device, public.check_device, public.deactivate_device, public.grant_license,
                           public.license_answer, public.license_status
  from public, anon, authenticated;
grant execute on function public.activate_device, public.check_device, public.deactivate_device, public.grant_license,
                          public.license_answer, public.license_status
  to service_role;
