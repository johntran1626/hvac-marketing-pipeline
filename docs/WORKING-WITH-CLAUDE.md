# Working with Claude

This is how I work with Claude Code. Short version: small pieces, one conversation each, and you actually look at what comes back.

## Claude does the pieces. You do the stitching.

Claude Code will one-shot a lot of things. A form, a table, a script, a page. It's good at that.

What it won't do well is a whole project in one go. "Build the booking system" gets you something shaped like a booking system. Your job is to break the problem into bite-sized pieces, hand them over one at a time, and stitch the results together.

A good piece is small enough that you can check it in a few minutes. "Add a zip check to `bookings` and a test that inserts 99999 as anon" is a piece. "Do M2" is not.

## The loop

For every piece:

1. **Scope it.** Say what you want, what it touches, and how you'll know it's done. Point at the files with `@`.
2. **Ask Claude to ask you clarifying questions** before it plans. End your prompt with "Ask me clarifying questions before you plan." Its questions show you what you forgot to say.
3. **Read the plan before you hit enter.** Use plan mode (Shift+Tab, or Alt+M on Windows). If the plan is wrong, fix it now. A rejected plan costs one turn. A wrong build costs twenty.
4. **Let it run to completion.** Don't babysit it mid-run or interrupt every step. Let it finish.
5. **Human QA.** Actually look at the output. Run it. Click through it. Read the diff. Open the live URL. Then write your critique: what's wrong, what's missing, what you want changed.
6. **Continue from there.** Send the critique, or commit and move to the next piece.

Step 5 is the one people skip. "Claude said it works" is not the same as you watching it work.

## One task, one conversation

Don't put everything into one mega conversation. Throw conversations away as you go: one task, one conversation, then `/clear`.

Long threads get more expensive every turn, because every turn re-reads the whole thread. They also get worse at following your instructions. If a thread is going in circles, arguing won't fix it. `/clear` and start again with a better prompt. That's technique, not failure.

## Keep context in files, not in chats

If you throw chats away, the context has to live somewhere. Put it in files:

- **`CLAUDE.md`**: project facts, how to run things, and your rules. Claude reads it at the start of every session. Keep it short. When Claude gets something wrong twice, add a rule. See [CLAUDE-CODE.md](CLAUDE-CODE.md).
- **`notes/<topic>.md`**: running notes you keep as you go. For example `notes/schema.md` (tables, columns, why) or `notes/decisions.md` (what you decided and why). Ask Claude to update them at the end of a task.

Start a new chat by pointing Claude at them: "Read @CLAUDE.md and @notes/schema.md, then add the waitlist table." It picks up where the last chat left off without dragging the whole old thread along.

## How I work on huge jobs

Some of my jobs run tens to hundreds of millions of tokens. I don't do those in one conversation. I run a swarm of subagents, and I size each subagent's task to about 500 to 750k tokens. Past that, hallucinations start climbing.

You'll learn subagent swarms later in the course. For now, the same idea applies at a smaller size: small tasks, fresh context, results written to files.

## Watch your usage

If you're not on the $200 plan, don't use the ultra effort level. It will nuke your usage. Stick to one task and one conversation at a time. More on limits in [CLAUDE-CODE.md](CLAUDE-CODE.md) section 7.

## Struggle through it

Right now it's important that you struggle through this yourself. Break the problem down, write the prompts, read the plans, find the bugs. It will be slow at first. That's the only way to learn it.

---

## Checklist

**Before you hit enter:**
- [ ] `git status` is clean. Commit first.
- [ ] This is one piece, and I can check it in a few minutes.
- [ ] I pointed at the files with `@`.
- [ ] I said what done looks like.
- [ ] I asked it to ask me clarifying questions.
- [ ] I read the plan, and it matches what I asked for.

**After it finishes:**
- [ ] I ran it and watched it work.
- [ ] I read the diff. I can explain every change.
- [ ] No `.env` files or keys in the diff.
- [ ] Every number or fact it wrote traces to a file or URL I can point at.
- [ ] I wrote down what's wrong and sent it back, or committed.
- [ ] I updated `CLAUDE.md` or `notes/` if something is worth keeping.
- [ ] `/clear` before the next task.
