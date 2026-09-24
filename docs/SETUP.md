# Setup

**Due Sun Sep 27, 11:59pm CT.** Proof is a live URL, not a screenshot.

You're setting up the same stack your group project runs on: GitHub, Vercel, Supabase, Claude Code, Node and VS Code. Then you build one small app that uses all of it: the calculator from Thursday's live build, on your own accounts. If your calculator works, your machine and your accounts are ready for M1.

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
| 8 | The calculator build | Your own calculator URL is live, saves every calculation to Supabase and shows the last 10 |
| 9 | Reply | Your GitHub username and your calculator URL are in Hamza's inbox |

---

## 1. GitHub

1. Sign up at https://github.com/signup. Pick a username you'd put on a resume.
2. **Reply to Hamza's email with your username now.** Don't wait for the rest. Groups and projects go out by Sunday night, with an invite to your project's private starter repo.
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

The calculator project below uses one of your two slots. After Hamza confirms your calculator URL, you can pause or delete it to free the slot.

---

## 8. The calculator build

Goal: a calculator on a live URL that saves every calculation to a Supabase table and shows the last 10. It's the same build Hamza did live on Thursday. Now you do it yourself, alone, where nothing else can break.

Claude writes the app. Your job is the loop from [WORKING-WITH-CLAUDE.md](WORKING-WITH-CLAUDE.md): scope it, answer its questions, read the plan, let it run, then check the result yourself.

### 8a. Supabase: the `calcs` table

1. In the Supabase dashboard: **New project**. Name `calculator`. Generate a database password and save it in your password manager. Pick a US region. Create it and wait until it's ready.
2. Left sidebar: **SQL Editor**. Paste this and **Run**:

```sql
create table public.calcs (id bigint generated always as identity primary key,
  expression text not null check (char_length(expression) between 1 and 100),
  result text not null check (char_length(result) <= 50),
  created_at timestamptz not null default now());
alter table public.calcs enable row level security;
grant select, insert on public.calcs to anon;
create policy "read calcs" on public.calcs for select to anon using (true);
create policy "add calcs" on public.calcs for insert to anon
  with check (char_length(expression) <= 100 and char_length(result) <= 50);
```

   What that does:
   - **RLS is on.** With no policy, nobody could read or write the table.
   - **Anyone with your publishable key can read and add rows.** That's the point of a public calculator.
   - **The insert policy checks something.** An expression over 100 characters or a result over 50 is rejected. It's not `with check (true)`. [STACK.md](STACK.md) explains why that matters.
   - **There's no update or delete policy,** so nobody can change or wipe the history from the browser.

3. Open **Table Editor** → `calcs`. It's empty, and it shows RLS enabled.
4. Get your URL and key. Click **Connect** at the top of the project and choose Next.js. Copy two values:
   - the project URL, `https://<project-ref>.supabase.co`
   - the **publishable** key, `sb_publishable_...`

   The key also lives under **Settings → API Keys**. If your dashboard only shows a legacy `anon` key, use that. Same place in the code. Supabase is deprecating the legacy `anon` and `service_role` keys by the end of 2026 (https://supabase.com/docs/guides/api/api-keys).

**Never** use the `secret` key (`sb_secret_...`) or the legacy `service_role` key here. Those skip RLS. They never go in browser code, never in a `NEXT_PUBLIC_` variable, never in git.

### 8b. Scaffold the app

Make a folder for course code and go into it.

**macOS:**
```bash
mkdir -p ~/code/calculator && cd ~/code/calculator
```

**Windows PowerShell:**
```powershell
New-Item -ItemType Directory -Force "$HOME\code\calculator" | Out-Null; cd "$HOME\code\calculator"
```

Windows: keep code out of OneDrive-synced folders (Desktop, Documents). `C:\Users\<you>\code` is good.

Create the app. Same commands on both:

```bash
npx create-next-app@latest web --yes
cd web
```

`--yes` takes the recommended defaults (TypeScript, Tailwind, App Router), so it asks no questions. It takes about a minute. It ends with "Initialized a git repository" and "Success!": you already have a repo and a first commit.

Heads-up: the first time you run `npm run dev`, Next.js 16 may create `AGENTS.md` and `CLAUDE.md` in your project (or add its own rules to an existing `CLAUDE.md`). That is Next.js, not Claude. Keep them: they tell Claude Code to read the Next.js docs that ship with your installed version instead of guessing from memory.

### 8c. Claude Code: `/init`, then commit

In the `web` folder:

```bash
claude
```

1. The first time in a new folder it asks if you trust the files. Yes.
2. Type `/init`. Claude reads the project and writes `CLAUDE.md`. Open it and read it. Every future session reads this file first, so it should be short and true.
3. Commit it. The `!` runs a shell command from inside Claude:

```
! git add -A
! git commit -m "Add CLAUDE.md"
```

Commit before every task. If the next step goes wrong, git gets you back to right here.

### 8d. Plan mode: Claude builds the calculator

Press **Shift+Tab** until the line under the input box says plan mode (on Windows, **Alt+M** if Shift+Tab doesn't switch). Paste:

```
Build a calculator on the home page: number and operator buttons plus keyboard input, clear and backspace, no eval(). After each = save {expression, result} to the Supabase table `calcs` using @supabase/supabase-js with NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, and show the last 10 calculations under it, newest first. Ask me clarifying questions before you plan.
```

**Answer its questions.** They show you what the prompt left open: decimals, what happens on divide by zero, whether pressing `=` twice saves twice. Decide. There's no wrong answer, but it should be your answer, not its guess.

**Read the plan before you approve it.** Check it against the prompt, line by line:
- It installs `@supabase/supabase-js`.
- It uses both env var names exactly.
- It doesn't use `eval()` or `new Function()`.
- It saves after each `=`, to `calcs`, with `expression` and `result`.
- It shows the last 10, newest first.
- It doesn't touch anything you didn't ask about.

If something's off, say so and let it re-plan. Then approve, and **let it run to completion.** It will ask before it runs commands like `npm install`. Read each one, then allow it.

When it's done, look at what changed:

```
! git diff --stat
```

Open the files it wrote in VS Code (`code .` from the `web` folder) and skim them.

### 8e. `.env.local`, then run it locally

Create `.env.local` in the `web` folder (next to `package.json`):

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Open `.gitignore` and check it has a line `.env*`. If it doesn't, add it. Env files never go in git.

Run it:

```bash
npm run dev
```

Open http://localhost:3000. Now do the human QA. Claude saying it works isn't the check. This is:
- Do a few calculations with the buttons, then with the keyboard. The history shows them, newest first.
- Open **Table Editor** → `calcs` in Supabase. Your rows are there.
- Refresh the page. The history is still there, because it's read from Supabase, not kept in the page.
- Try the edges: `7 / 0`, `0.1 + 0.2`, backspace on an empty display, `=` twice. Decide if you like what it does.

Anything wrong? Write down what you saw and what you expected, and send that to Claude. Run it again. When you're happy, stop the dev server with `Ctrl+C` and commit:

```bash
git add -A
git commit -m "Calculator with Supabase history"
```

### 8f. Vercel: deploy it

Install the Vercel CLI and start a deploy. Same commands on both, from the `web` folder:

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
- Project name: `calculator` (or `calculator-<your-name>` if that's taken).
- Code directory: `./` (press Enter).
- Modify settings: **no**. It detects Next.js.

This first deploy is a **preview**. The history won't load, because Vercel doesn't have your env vars yet. Expected.

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

It prints your production URL. **Open it in a private / incognito window.** Nothing should ask you to log in. Do a calculation. It shows in the history, and the row shows up in Supabase. Refresh: it's still there.

Env vars are read at build time for `NEXT_PUBLIC_` names. If you add or change one, run `vercel --prod` again.

Docs: https://vercel.com/docs/cli/env

---

## 9. What to reply with

Reply to Hamza's email thread by **Sun Sep 27, 11:59pm CT**:

```
GitHub: <your-username>
Calculator URL: https://<your-project>.vercel.app
```

Before you send it, open the URL in a private window and do one calculation. A URL that only works when you're logged in doesn't count.

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
| History stays empty, or saving fails with no message | Open the browser console (F12) and read the error. Then check the rows below. |
| `Could not find the table 'public.calcs'` or `relation "public.calcs" does not exist` | The table isn't in the project your URL points at. Run the SQL in 8a in that project. |
| `permission denied for table calcs` | Run `grant select, insert on public.calcs to anon;` in the SQL Editor. |
| `new row violates row-level security policy for table "calcs"` | The expression was over 100 characters or the result over 50. That's the policy working: ask Claude to cap the input length. Or the policies are missing: re-run the SQL in 8a. |
| Page shows a Supabase error about the API key | Wrong or truncated key in `.env.local` or on Vercel. Copy it again from **Connect**. Check you didn't paste the secret key. |
| Works locally, broken on Vercel | You added env vars after the deploy. Run `vercel --prod` again. |
| The live URL asks you to log in to Vercel | You copied a deployment-specific URL. Use the production domain shown in the Vercel dashboard under your project's **Domains**. Check it in a private window. |
| Supabase says the project is paused | Open it in the dashboard and restore it. Free projects pause after about a week of low activity. |
| Supabase won't let you create a project | You already have 2 active free projects. Pause or delete one. Paused projects don't count. |

Stuck for more than 30 minutes on one row? Reply to Hamza's email with the exact error text and the command you ran. Paste the text, not a photo of your screen.
