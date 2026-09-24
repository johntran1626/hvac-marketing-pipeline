# How a group works

One fork. One owner. Every change goes through an issue, a branch and a pull request. The rules below exist because of how Vercel Hobby and private forks work. They're not style.

## Roles

| Role | Who | Owns |
|---|---|---|
| **Owner** | One member | The private fork, the Vercel project, the Supabase org and project. Merges every PR |
| **Member** | Everyone, the owner included | Issues, branches, PRs, reviews, their own hours |
| **Hamza** | Instructor, GitHub `HZapperz` | Collaborator on the fork and on Supabase. Checks milestones |

Pick an owner who is reliable and has a free Supabase project slot (pause your calculator project if you need to free one). The owner is the only person who can deploy. Choose accordingly.

---

## Day one: the owner

1. **Fork the starter repo.** Open your project's starter repo on GitHub → **Fork** → Owner: **your personal account**, not an organization (Vercel Hobby can't deploy a private repo owned by an org) → **Create fork**. The fork is private, like the repo it came from.
2. **Enable Actions.** In the fork, open the **Actions** tab and enable workflows. Forks start with Actions off. Project B's worker won't run until you do this.
3. **Invite collaborators.** Fork → **Settings → Collaborators → Add people**. Add every teammate and `HZapperz`. On a personal repo every collaborator gets write access. There's no role to pick.
4. **Create the Supabase project** in your Supabase org (Free). Then **Organization settings → Team → Invite**: every teammate and Hamza (`hamza@zappstudios.us`) as **Developer**. Developer keeps the project off their 2-free-project count. Invites expire after 24 hours, so tell people to accept that day.
5. **Get `web/` onto `main`.** Someone scaffolds the app through the normal loop below: an issue, a branch, `npx create-next-app@latest web` from the repo root, a PR, your merge.
6. **Import the fork on Vercel** once `web/` is on `main`: https://vercel.com/new → import the fork (if it isn't listed, give Vercel's GitHub app access to it) → **Root Directory: `web`** → add the env vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`) → **Deploy**.
7. **Post the live URL** in your group chat and in the fork's **About** box (the gear next to "About" on the fork's main page, Website field). Don't edit the README for it: that file comes from the starter repo.

## Day one: everyone

1. **Accept both invites:** the GitHub one (email, or the fork's page) and the Supabase one (within 24 hours).
2. **Clone the fork.** Same on Windows and macOS:

```bash
git clone https://github.com/<owner>/<fork-name>.git
cd <fork-name>
```

   If git asks for a password: on Windows, Git for Windows opens a browser sign-in. On macOS, install GitHub CLI from https://cli.github.com, run `gh auth login` (GitHub.com, HTTPS, log in with a web browser), then `gh auth setup-git` and clone again.

3. **Once `web/` is on `main`:** create `web/.env.local` with the two `NEXT_PUBLIC_` values (the URL and publishable key from Supabase's **Connect** button), then:

```bash
cd web
npm install
npm run dev
```

---

## The loop: issue → branch → PR → review → merge

| Step | Who | What |
|---|---|---|
| 1 | You | Take an issue, or open one with the **Task** template. Assign yourself |
| 2 | You | Update `main`: `git switch main` then `git pull` |
| 3 | You | Branch, issue number first: `git switch -c 12-booking-form` |
| 4 | You | Work. Commit before each Claude task. Read each diff ([WORKING-WITH-CLAUDE.md](WORKING-WITH-CLAUDE.md)) |
| 5 | You | Push: `git push -u origin 12-booking-form` |
| 6 | You | Open a PR on GitHub. Fill in the template. Write `Closes #12` so the issue closes on merge |
| 7 | A teammate | Review (below). Approve or request changes |
| 8 | **The owner** | Merge with **Create a merge commit**. Not squash. Not rebase |
| 9 | You | Vercel deploys `main`. Open the live URL and check your change |
| 10 | Everyone | `git switch main` then `git pull` |

The git commands are the same on Windows and macOS.

**Why the owner merges with a merge commit:** on Hobby, Vercel only deploys commits whose author is the Hobby owner. A merge commit made by the owner is the owner's commit, so it deploys. Squash or rebase merges can keep the teammate as author, and then the deploy is blocked. Source: https://vercel.com/kb/guide/why-aren-t-commits-triggering-deployments-on-vercel

**Teammates' branches don't get preview deploys** on Hobby, for the same reason. Test locally with `npm run dev`.

**Rules:**
- Nobody pushes to `main` directly. The owner included.
- One issue per PR. Small PRs get real reviews. Big ones get skimmed.
- The author never reviews their own PR. When the owner writes a PR, a teammate reviews it before the owner merges.

### Reviewing a PR

To run someone's branch:

```bash
git fetch
git switch 12-booking-form
```

Then check four things:
1. **It runs.** You ran it and watched it work, not just read it.
2. **The diff.** Every changed file makes sense. No stray files, no leftover scaffold, no debug junk.
3. **The "How I verified it" section.** It says what they ran and what they saw, and you can repeat the check.
4. **No secrets.** No `.env` files, keys or passwords anywhere in the diff.

Leave comments on the lines. "Looks good" on a PR you didn't run isn't a review.

---

## Issues are the task board

- **Every task is an issue** with an owner (the assignee) and a **done-condition**. Use the Task template ([templates/ISSUE_TEMPLATE/task.md](templates/ISSUE_TEMPLATE/task.md)).
- **A done-condition is one sentence someone else can check.** "Done when an insert with zip 99999 as anon fails, and the test is in the repo." Not "done when the form works."
- **Each member owns at least 2 issues per milestone** and authors at least 1 merged PR. `MILESTONES.md` checks this per person.
- **Group issues by milestone:** Issues → **Milestones** → create `M1`, `M2`, `M3` with their due dates, and put each issue in one.
- Close issues through PRs (`Closes #12`), not by hand.

GitHub only uses the templates from `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md` on the default branch. If your fork doesn't have them there, copy them in from `templates/` in the first PR.

## Talk in chat, decide in issues

- **Your group's own chat** is for talk: questions, scheduling, "I'm stuck."
- **Decisions go in the issue.** If you decided something in chat, write it in the issue in one or two lines. Chat scrolls away. Hamza reads issues, not your chat.
- **Announcements** from Hamza come by email only.

## Hours

- **`logs/hours.md`:** everyone's hours, one section per person. Log the day you work, honestly. Template: [templates/hours.md](templates/hours.md).

## Secrets

- **Never commit secrets.** `.env*` goes in `.gitignore`, at the root and in `web/`.
- The **secret key** lives in three places only: Vercel env vars (no `NEXT_PUBLIC_` prefix), GitHub Actions secrets in the fork, and the `.env.local` of whoever needs it locally.
- Never paste a secret into chat, an issue, a PR, a screenshot or your Loom.
- **Leaked one?** Tell the group and Hamza the same day. The owner replaces it in Supabase (**Settings → API Keys**) and everywhere it's used. Git history keeps the old one, so deleting the file isn't enough.

More in [STACK.md](STACK.md).

---

## Heads-up: don't lose the fork

GitHub: "If you remove a person's access to a private repository, any of their forks of that private repository are deleted." Source: https://docs.github.com/en/pull-requests/reference/forks

So:
- **Don't leave the Lab's starter repo**, or remove yourself from it, until you've copied your work.
- **If the owner loses access** to the starter repo, the group's fork is deleted, issues and PRs included. Local clones survive. Issues and PR history don't.

## Pulling updates from the starter repo

Hamza may push fixes to the starter repo. The owner pulls them in:

1. On the fork's GitHub page: **Sync fork** → **Update branch**.
2. Everyone: `git switch main` then `git pull`.

Or from a terminal: `gh repo sync <owner>/<fork-name> -b main`. Source: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork

After a sync, Vercel may skip that deploy, because the new commits are Hamza's, not the owner's. The owner's next merge deploys everything.

Don't edit the starter files in `data/` and `docs/`. Then syncs stay clean.

## If the owner goes quiet

The owner holds Vercel and Supabase. If they're unreachable for 48 hours near a deadline, email Hamza. Don't wait for the deadline to say so.
