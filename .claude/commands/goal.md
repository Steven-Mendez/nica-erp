---
name: "Goal"
description: Drive a multi-step goal to completion across sessions. Persists task lists in `.claude/goals/<slug>.md` and resumes where you left off.
category: Workflow
tags: [workflow, planning, persistence]
---

Drive a goal to completion. State lives in `.claude/goals/<slug>.md` so the
command survives `/clear` and new sessions.

**Input**: The argument after `/goal` is either:
- A goal slug that already exists (e.g., `/goal pre-sprint-04`) → resume it.
- A short description of a new goal (e.g., `/goal close tailwind v4`) → create it.
- Nothing → list existing goals via **AskUserQuestion** and let the user pick or start a new one.

---

## Steps

### 1. Select or create the goal

```bash
ls .claude/goals/ 2>/dev/null
```

- **No arg**: if the directory exists and has files, use **AskUserQuestion** to
  list the slugs (one option each, plus "Create new goal"). If empty or
  missing, prompt for a description.
- **Arg matches an existing file**: read it. Announce `Resuming goal: <slug>`.
- **Arg is a new description**: derive a kebab-case slug (≤ 4 words), confirm
  it with **AskUserQuestion** if it might collide, then create
  `.claude/goals/<slug>.md` from the template below.

### 2. Goal file template (only when creating)

```markdown
# <Title — match the slug, capitalised>

## Why
<one paragraph: the problem this goal closes and why now>

## Definition of done
- <bullet 1 — concrete, checkable>
- <bullet 2>

## Tasks
- [ ] 1. <task — verb-first, one outcome>
- [ ] 2. <task>

## Notes
<empty — append findings, decisions, links as you work>
```

Write it with the **Write** tool. Then summarise it back to the user in 2-3
sentences and ask (via **AskUserQuestion**) whether to start now or just save
the file.

### 3. Drive execution

For an existing goal:

1. **Read the file** with **Read**. List the open `- [ ]` tasks back to the
   user with their numbers.
2. **Pick the next task**: by default, the first open one. If the user named a
   number or hinted at a different one, use that. If multiple unrelated tasks
   are open, ask via **AskUserQuestion** which to take.
3. **Announce**: `Working on: <N>. <task text>`.
4. **Do the work** using normal tools. Honour the project's rules
   (CLAUDE.md, memory, OpenSpec workflow). If the task is big enough to
   warrant a TaskCreate breakdown, do it.
5. **Mark `[x]`** in the goal file via **Edit** as soon as the task is done —
   do not batch.
6. **Append a one-line note** under `## Notes` describing what changed (PR
   number, file path, commit SHA if you made one). Keep it terse.
7. **Loop**: ask the user via **AskUserQuestion** whether to continue with the
   next task, pause, or pick a different one. If the user typed `/goal` again
   in the same turn implying "keep going", just continue.

### 4. Closure

When every task is `[x]`:

1. Update `## Notes` with a final summary (≤ 5 lines).
2. Show the diff with `git status` so the user sees the spread of changes.
3. **Move the file** to `.claude/goals/done/<slug>.md` (create the directory
   if missing) so resumes don't pick it up.
4. Tell the user: `Goal closed. Archived to .claude/goals/done/<slug>.md.`

---

## Rules

- **One source of truth.** The markdown file is canonical. If you used
  `TaskCreate` for in-session breakdowns, mirror the completion back to the
  goal file before ending the turn.
- **Never invent tasks.** If the user adds scope verbally, append it as a new
  numbered task in the file before working on it.
- **Don't auto-commit.** Goal execution may produce many small edits;
  committing is the user's call unless the goal explicitly lists "commit" as a
  task.
- **No AWS work unless the user opts in.** This project has no verified AWS
  account at the moment (see CLAUDE.md / memory). Treat any AWS-touching task
  as blocked and surface it before attempting.
- **Reference the file path in every status update** so the user can audit
  `.claude/goals/<slug>.md` directly.
