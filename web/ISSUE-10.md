# Issue #10: web app and Supabase

From `web/`, run `npm ci`. Keep these values in ignored `web/.env.local`:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SUPABASE_HEALTH_TABLE=
```

Use the team's HTTPS Supabase project URL and `sb_publishable_...` key.
Never put a secret/service-role key in these variables. Public variables can be
included in browser bundles; rebuild after changing them. No credentials belong
in git, terminal output, screenshots, or review evidence.

Leave `SUPABASE_HEALTH_TABLE` unset until Issue #7 confirms a real table in the
`public` schema containing real HVAC data, with the intended SELECT grants and
RLS access for the publishable client's anonymous role. Set the unqualified
table name only; do not create a test table, seed fake rows, use privileged keys,
or relax policies to make this check pass. If the team's access model requires
authentication or another schema, coordinate that integration after Issue #7.

## Verification

```sh
npm run lint
npm run build
npx tsc --noEmit
npm run start
```

Open `/` and `/health` on localhost:3000. For development use `npm run dev`.
`/health` is a JSON route: HTTP 200 with `ok: true` means its uncached SELECT
returned one row. HTTP 503 means missing configuration, a failed read, or no
visible rows (including rows hidden by RLS). No rows or raw errors are returned.
The query is limited to one row and has a 10-second abort signal.

A successful build, reachable Supabase API, empty result, or mocked response is
not proof of the required database read. Final acceptance remains blocked until
the configured table belongs to the team's HVAC project and a real row is read.
Record the date, approved table name, and `/health` HTTP status/result after that
verification. Do not include keys or row contents. Deployment/PR work is separate.

The client currently performs anonymous reads only, with session persistence and
refresh disabled. It is not an authenticated SSR client. It deliberately accepts
modern publishable keys only, not legacy JWT keys.

## Local verification recorded 2026-10-02

- `npm ci`: installed the locked dependencies; audit reported 0 vulnerabilities.
  Existing ESLint 9 emitted a support/deprecation warning; dependencies unchanged.
- `npm run lint`, `npm run build`, `npx tsc --noEmit`, and `git diff --check`:
  exit 0. Build lists `/health` as dynamic.
- Production server on 127.0.0.1:3110: `/` returned HTTP 200 HTML. Two requests
  to `/health` returned HTTP 503, `Cache-Control: no-store`, and
  `{"ok":false,"status":"blocked","message":"Configure a real HVAC table after Issue #7 is ready."}`.
- Direct client checks accepted the existing public configuration and rejected
  missing URL/key, malformed or HTTP URL, secret key, and legacy JWT input.
  These checks do not prove the credentials work against the team database.
- `git check-ignore -v web/.env.local`: matched `web/.gitignore`.
  No environment files tracked. Credential-pattern scan of reviewable files
  and reachable branch history found no matches (not an exhaustive secret audit).
- Real database read: **NOT RUN / BLOCKED**. No approved HVAC table configured;
  Issue #7 schema/data readiness and read permissions were not independently
  verified. No database writes, fake rows, or schema changes were performed.

The installed Next.js package did not contain the `node_modules/next/dist/docs/`
directory referenced by `AGENTS.md`; current official route-handler and
environment-variable documentation was consulted instead:
[Next.js routes](https://nextjs.org/docs/app/api-reference/file-conventions/route),
[Next.js environment](https://nextjs.org/docs/app/guides/environment-variables),
[Supabase client](https://supabase.com/docs/reference/javascript/initializing),
[Supabase keys](https://supabase.com/docs/guides/getting-started/api-keys).
