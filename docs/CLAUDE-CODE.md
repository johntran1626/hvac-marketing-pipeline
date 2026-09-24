# Claude Code: the essentials

Claude Code is Claude with a terminal, your files and git. It reads, writes and runs things on your machine. That makes it fast. It also means it can be wrong on your disk, not just in a chat window.

Install and login are in [SETUP.md](SETUP.md). This page is the reference: commands, modes, limits. How to actually work with it is in [WORKING-WITH-CLAUDE.md](WORKING-WITH-CLAUDE.md). Read that first.

Full docs: https://code.claude.com/docs

---

## 1. First run

1. Open a terminal **inside your repo folder**. Never your home folder, never a folder with uncommitted work you care about.
2. Commit first: `git status` should be clean.
3. Run `claude`.
4. Check the account and model: `/status`.
5. Switch to Sonnet for routine work: `/model sonnet`. (Why: section 7.)
6. Run `/init`. It reads the repo and writes a `CLAUDE.md`. Then **cut it down** (section 2). `/init` writes a lot. Most of it you don't need.

Also works inside VS Code: the Claude Code extension (`anthropic.claude-code`) shows its edits as diffs you can read before you keep them.

## 2. CLAUDE.md

Claude reads `CLAUDE.md` at the start of every session. It's the only thing it remembers between sessions. Source: https://code.claude.com/docs/en/memory

| File | For | In git? |
|---|---|---|
| `./CLAUDE.md` | The project: facts, commands, rules. Shared with your group | Yes |
| `./CLAUDE.local.md` | Your personal notes for this project | No, keep it out |
| `~/.claude/CLAUDE.md` | You, across every project | Not in any repo |

**What goes in:**
- **Facts** it can't see or would guess wrong: the business, the data files, where the app lives (`web/`), the Supabase project, the deadline.
- **Commands** to build, run and test: `cd web && npm run dev`, `npm run build`, how to run the evals.
- **Anti-pattern rules**, written as orders. These do the most work:
  - "If a number isn't in a file I gave you, say unknown. Never estimate."
  - "Use the exact names from the data files. Never invent placeholder names, services or prices."
  - "Never say something works unless you ran it. Say what you ran and paste the output."
  - "Never write an RLS policy with `with check (true)`. Never put the secret key in browser code."

**What stays out:** long explanations, anything that changes daily, secrets. Every line is loaded every session and costs usage. Keep it short. The docs say under about 200 lines. Aim for under 60.

A blank starter is in [templates/CLAUDE.template.md](templates/CLAUDE.template.md) (named so Claude Code does not load it as instructions). Project repos already have a filled-in `CLAUDE.md` at the root.

When Claude gets something wrong twice, add a rule. That's how the file earns its keep.

## 3. Permission modes

Pro sessions **start in auto mode**: a classifier approves actions for you. Fast, and you won't see most of what it does unless you look. Source: https://code.claude.com/docs/en/permission-modes

Switch modes with **Shift+Tab**. On Windows, if Shift+Tab doesn't cycle, use **Alt+M**. The current mode shows under the input box. To start a session in plan mode: `claude --permission-mode plan`.

| Mode | What it does | Use it for |
|---|---|---|
| **plan** | Reads and proposes. Changes nothing | Anything non-trivial. Start here |
| **default** (Manual) | Asks before each edit and command | Anything that touches the database, deploys, secrets or git history |
| **acceptEdits** | Edits files without asking, still asks before commands | Small, well-planned changes in a committed repo |
| **auto** | A classifier approves actions | Small local tasks in a committed repo. Check the diff after |
| **dontAsk** | Denies anything that would prompt | Locked-down scripted runs. Not needed in this course |
| **bypassPermissions** | Skips all checks | **Never.** Containers only |

Git can undo a file edit. It can't undo a dropped table, a deploy or a pushed secret. Match the mode to what can go wrong.

## 4. Plan mode workflow

For anything bigger than a one-line fix:

1. **Commit.** `git status` clean.
2. **Plan mode.** Shift+Tab (Alt+M on Windows) until it says plan mode.
3. **Brief it** the Week 1 way: context, goal, constraints, done-condition. Point at files with `@`.
4. **Read the plan.** Check it against your brief line by line. Is anything missing, extra or generic?
5. **Reject or edit it** if it's wrong. Rejecting a plan is much cheaper than reviewing the diff of a wrong one.
6. **Approve,** then watch.
7. **Read every diff** before you commit.
8. **Run it.** Reading is not running ([WORKING-WITH-CLAUDE.md](WORKING-WITH-CLAUDE.md)).
9. **Commit** with a message that says what changed.

Scope down, not up. "Build the booking system" gets you something shaped like a booking system. "Add a zip check constraint to `bookings` and a test that inserts 99999 as anon" gets you something you can check.

## 5. Commands you'll use

| Command | What it does |
|---|---|
| `@path/to/file` | Points Claude at a specific file. Better than describing it |
| `/init` | Writes a starter `CLAUDE.md` from the repo |
| `/clear` | Starts a fresh conversation. Use it between tasks |
| `/compact [focus]` | Summarizes the conversation to free up context. Add what to keep: `/compact keep the schema decisions` |
| `/context` | Shows what's filling the context window |
| `/model sonnet` | Switches to Sonnet. `/model` alone shows the options |
| `/usage` | Shows your usage (alias `/cost`) |
| `/status` | Account, model, version |
| `/rewind` or `Esc Esc` | Rolls back to an earlier point in the session |
| `!command` | Runs a shell command yourself, e.g. `!git status` |

Source: https://code.claude.com/docs/en/commands

`/rewind` (or `Esc Esc` with an empty input) rolls back edits Claude made with its file tools. It doesn't undo files changed by shell commands, and it can't undo a database change, a deploy or a push. Git is still your real undo. Source: https://code.claude.com/docs/en/checkpointing

A thread that's gone in circles won't recover by arguing. `/clear` and restart with a better brief. Starting over is technique, not failure.

## 6. Git discipline

Two rules. No exceptions.

1. **Commit before every task.** It takes three seconds. When Claude breaks something, `git restore <file>` or `git reset --hard` takes you back.
2. **Read every diff before you commit.** In VS Code: Source Control view. In a terminal: `git diff`. If you can't explain a change, don't commit it.

Also:
- Work on a branch, never on `main`. The group workflow is in [WORKFLOW.md](WORKFLOW.md).
- Before you commit, check `git status` for `.env` files. They never go in git.
- Watch for files Claude added that you didn't ask for. Unused scaffold and stray test files are a common review failure.

## 7. Usage limits: don't hit the wall again

Every one of you hit the limit in Week 1. Here's how it works and how to make it last.

**How the limit works** (https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan):
- Your limit is **shared** between claude.ai chat and Claude Code. Chatting burns the same budget.
- Pro has a **5-hour session window** and a **weekly cap**. Hit the weekly cap on Saturday and you're out for the milestone on Sunday.
- The **default model is Opus 5.5**, the most expensive per turn (https://code.claude.com/docs/en/model-config).

**Habits that make it last:**

| Do | Why |
|---|---|
| `/model sonnet` for routine work | Opus costs more per turn. Save it for hard design problems |
| `/clear` between tasks | Every turn processes the whole conversation so far. Long threads cost more per turn and get worse |
| Small tasks with a done-condition | One checkable piece at a time. Fewer retries |
| `@` the file, don't paste it | Pasting a whole file or CSV into the prompt fills the context |
| Don't let it read big data files whole | Ask it to write a script that computes the number. Cheaper, and the script is your evidence |
| Keep `CLAUDE.md` short | It's loaded every session |
| Plan mode first | A rejected plan costs one turn. A wrong build costs twenty |
| Check `/usage` and `/context` | Know where you are before a long task, not after |
| Plan your week | Don't save all the Claude work for the night before a deadline |

When you hit the limit: the message says when it resets. Use the gap to read diffs, test by hand and update your notes. That work doesn't need Claude.

## 8. Headless: `claude -p` (Project C)

`claude -p` runs one prompt with no chat and prints the answer. You can script it.

```bash
claude -p "<prompt>" --output-format json --model sonnet --allowedTools "WebFetch" --strict-mcp-config
```

- `--output-format json` wraps the answer in JSON. The answer text is in the `result` field. Open one output and look before you write the parser.
- `--model sonnet`: always, for batch work.
- `--allowedTools`: only the tools the job needs. `-p` runs start in Manual mode, and with nobody there to answer, anything not allowed is refused.
- `-p` loads your project's `CLAUDE.md`, so your rules apply to scripted runs too.
- **Always add `--strict-mcp-config`.** Without it, `-p` also loads every MCP server and every claude.ai connector on your account (Gmail, Drive, and so on), even when you limit `--tools`. We tested it: 49 extra tools, including ones that can send email and share files, sitting next to web pages written by strangers, plus about 25,000 extra tokens on every call. With the flag: zero.
- **WebFetch hands the model a summary of the page, not the page.** Summaries can invent details (in testing it made up an email address and cited the contact page for it). For any fact you will cite, fetch the raw page yourself and quote it.
- **Don't add `--bare`.** Bare mode skips your subscription login and needs an API key.

Save one result per business:

**macOS:**
```bash
claude -p "<prompt>" --output-format json --model sonnet --allowedTools "WebFetch" --strict-mcp-config > out/b001.json
```

**Windows PowerShell:**
```powershell
claude -p "<prompt>" --output-format json --model sonnet --allowedTools "WebFetch" --strict-mcp-config | Out-File -Encoding utf8 out\b001.json
```

**The rules:**
- Personal, local use on your own Pro login is currently allowed. **It counts against your plan limits**, same as chat. 100 businesses is 100 runs or more. Test on 3 before you run 100.
- **Anything other people use needs an API key.** So `claude -p` never runs behind your deployed app. Your local run writes results to Supabase. The live site only displays them.
- These terms can change. Hamza re-checks them before M2.

Sources: https://code.claude.com/docs/en/headless · https://code.claude.com/docs/en/legal-and-compliance · https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `claude: command not found` | Open a new terminal. Still missing: https://code.claude.com/docs/en/troubleshoot-install. Once it runs, `claude doctor` checks the rest |
| It edited something you didn't want | `git restore <file>`. This is why you commit first |
| It says "done" and "tested" | Ask what it ran and ask for the output. Then run it yourself |
| The thread is going in circles | `/clear`. Restart with a tighter brief |
| Out of usage | See section 7. Switch to work that doesn't need Claude |

---

## What to bring Thursday

Two things:
1. One plan you rejected or edited, and why. A wrong plan teaches you more about your own brief than a right one.
2. One time Claude was wrong, and how you caught it.
