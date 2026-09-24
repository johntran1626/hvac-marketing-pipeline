# Setup

**Due Sun Sep 27, 11:59pm CT.** Proof is a live URL, not a screenshot.

You're setting up the same stack your group project runs on: GitHub, Vercel, Supabase, Claude Code, Node and VS Code. Then you build one tiny app that uses all of it. If the hello build works, your machine and your accounts are ready for M1.

Most of this is installs and waiting. Do it in order.

## Checklist

| # | Step | Done when |
|---|---|---|
| 1 | GitHub account | You replied to Hamza's email with your username |
| 2 | Git | `git --version` prints a version |
| 3 | Node.js LTS | `node --version` prints `v22.x` or `v24.x` |
| 4 | VS Code + Claude Code extension | The Claude Code icon shows in VS Code |
| 5 | Claude Pro + Claude Code | `claude --version` works, `claude doctor` is clean, you're logged in |
| 6 | Vercel | Hobby account, signed up with GitHub |
| 7 | Supabase | Account, signed up with GitHub |
| 8 | The hello build | A live URL shows a row from your Supabase table |
| 9 | Reply | Your GitHub username and your live URL are in Hamza's inbox |

---

## 1. GitHub

1. Sign up at https://github.com/signup. Pick a username you'd put on a resume.
2. **Reply to Hamza's email with your username now.** Don't wait for the rest. He invites you to your project's private starter repo.
3. When the invite arrives, accept it. Your group forks that repo. See [WORKFLOW.md](WORKFLOW.md).

## 2. Git

**Windows:** install Git for Windows from https://git-scm.com/downloads/win. Keep the default options. Claude Code uses its Bash, and you need git for everything in this course.

**macOS:** run `git --version`. If git isn't installed, macOS offers to install the Command Line Tools. Say yes. Or run `xcode-select --install`.

Then tell git who you are. Use an email that's on your GitHub account (see https://github.com/settings/emails, the `noreply` address there works too). Vercel decides who made a commit from this email, and on Hobby that decides whether it deploys.

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Same commands on Windows and macOS.

## 3. Node.js LTS

1. Go to https://nodejs.org and download the **LTS** installer. As of Sep 24, 2026 that's 24.x. 22.x is also LTS and also fine.
2. Run the installer with the defaults. Windows: `.msi`. macOS: `.pkg`.
3. Open a **new** terminal and check:

```bash
node --version
npm --version
```

`node --version` should print `v22.x` or `v24.x`.

## 4. VS Code

1. Install from https://code.visualstudio.com.
2. Install the Claude Code extension: open Extensions (Windows `Ctrl+Shift+X`, macOS `Cmd+Shift+X`), search **Claude Code**, publisher **Anthropic**, Install. Or from a terminal:

```bash
code --install-extension anthropic.claude-code
```

On macOS, `code` works in the terminal only after you run **Shell Command: Install 'code' command in PATH** from the VS Code command palette (`Cmd+Shift+P`).

You'll review a lot of diffs. VS Code shows them better than a terminal.

## 5. Claude Pro and Claude Code

**Claude Pro** is $20/mo. The free plan doesn't include Claude Code. Upgrade at https://claude.ai. Source: https://code.claude.com/docs/en/setup

**Install Claude Code.** The native installer auto-updates.

**macOS:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows PowerShell:**
```powershell
irm https://claude.ai/install.ps1 | iex
```

**Windows CMD:**
```bat
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

Windows: install Git for Windows first (step 2). WSL is not required.

Open a **new** terminal and check:

```bash
claude --version
claude doctor
```

`claude doctor` checks your install. Fix anything it flags before you move on.

**Log in.** Go into any folder and run `claude`. It opens a browser. Sign in with the Claude account that has Pro, and pick the subscription option, not the Console / API billing one. Inside Claude Code, `/status` shows which account you're on.

Then read [CLAUDE-CODE.md](CLAUDE-CODE.md) before you use it for real.

## 6. Vercel

1. Go to https://vercel.com/signup.
2. Pick **Hobby**. Hobby is free and for non-commercial personal use only (https://vercel.com/docs/limits/fair-use-guidelines).
3. Choose **Continue with GitHub**.

## 7. Supabase

1. Go to https://supabase.com/dashboard and choose **Continue with GitHub**.
2. If it asks you to create an organization: your name, type Personal, plan **Free**.

Know this now: **you get 2 active free projects**, counted across every organization where you're Owner or Admin. Paused projects don't count. Free projects **pause after about a week of low activity**. You can restore them from the dashboard. Details in [STACK.md](STACK.md).

The hello project below uses one of your two slots. After Hamza confirms your hello URL, you can pause or delete it to free the slot.

---

## 8. The hello build

Goal: a Next.js page on Vercel that reads one row from a Supabase table, live, on every request.

This is the same move as M1's `/health` page. Get it working once here, alone, where nothing else can break.

### 8a. Supabase: a table with one row

1. In the Supabase dashboard: **New project**. Name `hello`. Generate a database password and save it in your password manager. Pick a US region. Create it and wait until it's ready.
2. Left sidebar: **Table Editor** → **New table**.
   - Name: `hello`
   - Keep **Enable Row Level Security (RLS)** checked.
   - Keep the `id` column it gives you (int8, primary key).
   - **Add column:** name `message`, type `text`.
   - **Save.**
3. Open the `hello` table → **Insert** → **Insert row**. Set `message` to `Hello from <your name>`. **Save.**
4. RLS is on and there's no policy yet, so nobody can read the row. That's correct. Now allow reads. Left sidebar: **SQL Editor**, paste, **Run**:

```sql
grant select on public.hello to anon;

create policy "anon can read hello"
  on public.hello for select
  to anon
  using (true);
```

`using (true)` on a **select** policy means anyone with your publishable key can read every row. Fine for a hello message. Never for customer data. [STACK.md](STACK.md) shows what a real policy looks like.

<details>
<summary>Prefer SQL for all of 8a? Paste this instead of steps 2 to 4.</summary>

```sql
create table public.hello (
  id bigint generated always as identity primary key,
  message text not null,
  created_at timestamptz not null default now()
);

insert into public.hello (message) values ('Hello from <your name>');

alter table public.hello enable row level security;

grant select on public.hello to anon;

create policy "anon can read hello"
  on public.hello for select
  to anon
  using (true);
```

</details>

5. Get your URL and key. Click **Connect** at the top of the project and choose Next.js. Copy two values:
   - the project URL, `https://<project-ref>.supabase.co`
   - the **publishable** key, `sb_publishable_...`

   The key also lives under **Settings → API Keys**. If your dashboard only shows a legacy `anon` key, use that. Same place in the code. Supabase is deprecating the legacy `anon` and `service_role` keys by the end of 2026 (https://supabase.com/docs/guides/api/api-keys).

**Never** use the `secret` key (`sb_secret_...`) or the legacy `service_role` key here. Those skip RLS. They never go in browser code, never in a `NEXT_PUBLIC_` variable, never in git.

### 8b. Next.js: a page that reads the row

Make a folder for course code and go into it.

**macOS:**
```bash
mkdir -p ~/code && cd ~/code
```

**Windows PowerShell:**
```powershell
New-Item -ItemType Directory -Force "$HOME\code" | Out-Null; cd "$HOME\code"
```

Windows: keep code out of OneDrive-synced folders (Desktop, Documents). `C:\Users\<you>\code` is good.

Create the app and add the Supabase client. Same commands on both:

```bash
npx create-next-app@latest hello
cd hello
npm install @supabase/supabase-js
```

`create-next-app` asks questions. If it offers the **recommended defaults**, take them. If it asks one by one: TypeScript **Yes**, Tailwind CSS **Yes**, App Router **Yes**, `src/` directory **No**. Anything else: press Enter for the default.

Heads-up: the first time you run `npm run dev`, Next.js 16 may create `AGENTS.md` and `CLAUDE.md` in your project (or add its own rules to an existing `CLAUDE.md`). That is Next.js, not Claude. Keep them: they tell Claude Code to read the Next.js docs that ship with your installed version instead of guessing from memory.

Open the folder in VS Code:

```bash
code .
```

**Create `.env.local`** in the `hello` folder (next to `package.json`):

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Open `.gitignore` and check it has a line `.env*`. If it doesn't, add it. Env files never go in git.

**Replace everything in `app/page.tsx`** (it's `src/app/page.tsx` if you said yes to `src/`):

```tsx
import { createClient } from "@supabase/supabase-js";

// Read the row on every request. Without this line, Next.js may build the page once and never ask again.
export const dynamic = "force-dynamic";

export default async function Home() {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  );

  const { data, error } = await supabase
    .from("hello")
    .select("id, message")
    .limit(1);

  if (error) {
    return <main className="p-8">Supabase error: {error.message}</main>;
  }
  if (!data || data.length === 0) {
    return (
      <main className="p-8">
        No row visible. Check that the row exists and that anon has a read policy.
      </main>
    );
  }

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">{data[0].message}</h1>
      <p>Row {data[0].id}, read from Supabase on this request.</p>
    </main>
  );
}
```

This is a server component: it runs on the server, not in the browser. Supabase's own quickstart uses the same two env var names (https://supabase.com/docs/guides/getting-started/quickstarts/nextjs).

**Run it locally:**

```bash
npm run dev
```

Open http://localhost:3000. You should see your message.

**Now check it's live, not luck.** Change the message in the Supabase Table Editor. Refresh the page. The text changes. That's a tier 1 check: you ran it and watched the result ([VERIFY.md](VERIFY.md)).

Stop the dev server with `Ctrl+C`.

### 8c. Vercel: deploy it

Install the Vercel CLI and start a deploy. Same commands on both:

```bash
npm i -g vercel
vercel
```

If `npm i -g` fails with a permissions error, skip it and type `npx vercel` everywhere this page says `vercel`.

Answer the prompts:
- Log in if asked: **Continue with GitHub**.
- Set up and deploy: **yes**.
- Scope: your personal account.
- Link to existing project: **no**.
- Project name: `hello`.
- Code directory: `./` (press Enter).
- Modify settings: **no**. It detects Next.js.

This first deploy is a **preview**. It will show an error when you open it, because Vercel doesn't have your env vars yet. Expected.

Add the two env vars to production. Each command asks for the value: paste it.

```bash
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY production
```

If it asks **Make it sensitive?**, either answer works for these two. They're public values.

Deploy to production:

```bash
vercel --prod
```

It prints your production URL. **Open it in a private / incognito window.** You should see your message, and nothing should ask you to log in. Change the row in Supabase again and refresh: the live page changes too.

Env vars are read at build time for `NEXT_PUBLIC_` names. If you add or change one, run `vercel --prod` again.

Docs: https://vercel.com/docs/cli/env

---

## 9. What to reply with

Reply to Hamza's email thread:

```
GitHub: <your-username>
Hello URL: https://<your-project>.vercel.app
```

Before you send it, open the URL in a private window one more time. A URL that only works when you're logged in doesn't count.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `claude`, `node`, `git` or `vercel` "not recognized" / "command not found" right after installing | Open a **new** terminal. Installers update `PATH` for new terminals only. Still broken: https://code.claude.com/docs/en/troubleshoot-install |
| `'&&' is not a valid statement separator` | You ran the CMD installer in PowerShell. Use the `irm ... \| iex` command. |
| PowerShell: `... .ps1 cannot be loaded because running scripts is disabled on this system` (often on `npx`, `npm` or `vercel`) | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, open a new terminal. |
| `npm i -g vercel` fails with `EACCES` (macOS) | Don't use `sudo`. Use `npx vercel` instead of `vercel`. |
| `npm install` fails with `EPERM` or locked files (Windows) | The project is inside a OneDrive folder. Move it to `C:\Users\<you>\code` and reinstall. |
| `claude doctor` complains about Git or Bash (Windows) | Install Git for Windows (step 2), then open a new terminal. |
| Page says `supabaseUrl is required` | Env vars missing. Locally: `.env.local` must sit next to `package.json`, and you restart `npm run dev` after editing it. On Vercel: run the two `vercel env add` commands, then `vercel --prod`. |
| Page says `No row visible` | RLS is hiding the row, or the row isn't there. Check the row in Table Editor. Re-run the policy SQL in 8a step 4. |
| Page says `Supabase error: permission denied for table hello` | Run `grant select on public.hello to anon;` in the SQL Editor. |
| Page shows a Supabase error about the API key | Wrong or truncated key in `.env.local` or on Vercel. Copy it again from **Connect**. Check you didn't paste the secret key. |
| Works locally, broken on Vercel | You added env vars after the deploy. Run `vercel --prod` again. |
| The live URL asks you to log in to Vercel | You copied a deployment-specific URL. Use the production domain shown in the Vercel dashboard under your project's **Domains**. Check it in a private window. |
| You changed the row but the page shows the old message | `export const dynamic = "force-dynamic";` is missing from `page.tsx`. Add it and redeploy. |
| Supabase says the project is paused | Open it in the dashboard and restore it. Free projects pause after about a week of low activity. |
| Supabase won't let you create a project | You already have 2 active free projects. Pause or delete one. Paused projects don't count. |

Stuck for more than 30 minutes on one row? Reply to Hamza's email with the exact error text and the command you ran. Paste the text, not a photo of your screen.
