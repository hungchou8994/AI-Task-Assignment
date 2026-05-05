# Candidate Task Brief: Task Comments

> **For:** Junior full-stack engineer candidate
> **Estimated effort:** 2–3 days
> **Repository:** AI Task Management Platform

---

## Background

Our platform helps teams capture and manage tasks, including tasks extracted from unstructured sources by an AI agent. While we already track an automated activity log for each task (status changes, edits, etc.), **there is currently no way for team members to actually talk to each other on a task** — to ask questions, leave context, request clarification, or coordinate handoffs.

Your job is to add **Task Comments** to the platform.

---

## What we want

A simple, reliable comment thread attached to every task. Anyone who can see the task should be able to read its comments. Anyone who is a member of the task's workspace should be able to add a comment. People should be able to edit and delete the comments they wrote. Workspace admins should be able to delete other people's comments when needed (e.g. to remove inappropriate content).

The feature should feel native to the rest of the product — meaning it should look, behave, and be coded in a way that's consistent with what's already there.

---

## Functional scope

### Must-have

- A user opens a task and sees its existing comments, ordered chronologically (oldest or newest first — your call, but be consistent).
- A user can write a new comment and post it. The new comment appears immediately.
- The author of a comment can edit it. After editing, the UI should make it clear the comment was edited.
- The author of a comment can delete it. A workspace admin or owner can also delete any comment in their workspace.
- Each comment shows: who wrote it, when, and the content.
- The feature is available in all UI languages the product currently supports.
- Permission rules are enforced on the server, not just hidden in the UI.

### Nice-to-have

- Pagination or "load more" when a task has many comments.
- Relative timestamps that update ("2 minutes ago", "yesterday").
- Mentioning a teammate with `@` and autocomplete from workspace members.
- Linking comments into the existing task activity timeline so the audit log reflects "X commented on this task".
- Markdown or basic rich text in the comment body.
- Optimistic UI: comment appears instantly before the server confirms.

You are **not** expected to finish all of these. We would much rather see the must-haves done well than every nice-to-have done in a rush.

---

## Working agreement

This is how we want you to work on the task. Please follow these rules — they're as important to us as the feature itself.

### Branch & PR

1. Create a **new branch** off `main`. Use a descriptive name, e.g. `feature/task-comments`. Do not commit directly to `main`.
2. When you're ready, open a **pull request from your branch into `main`**.
3. The PR description should include:
   - A short summary of what you built.
   - The **completion checklist** below, with each item marked done / partially done / not done.
   - Anything you decided to skip and why.
   - Anything you'd do differently if you had more time.
   - How to test the feature locally (commands + click path).
   - **A demo link.** A deployed/production URL is nice-to-have; a localhost setup is fine, but in that case you must also include a **link to a video walkthrough** (Loom, YouTube unlisted, Google Drive, etc.) showing the feature working end-to-end. We will also ask you to demo the feature live in a single interview session, so make sure your local environment is reproducible.

### Commits

- Make **small, focused commits**. Each commit should represent one logical step ("add comment model and migration", "add list comments endpoint", "wire up comment list in task detail page", etc.).
- Write **clear commit messages**: a short imperative subject line, and a body if the change needs explanation.
- Avoid commits like "wip", "fix", "more changes", "asdf". We will read your git log as part of the evaluation.
- Do not squash everything into one commit at the end. We want to see how you broke the work down.

### Working with AI

- **You are explicitly allowed (and encouraged) to use AI assistants** — Claude, ChatGPT, Cursor, Copilot, etc. — to help you build this feature. We use these tools every day; pretending you don't is not what we're testing.
- What we **do** test is whether you can drive an AI well: review what it gives you, reject what's wrong, and ship code you actually understand. If we ask in the interview "why did you do it this way?" and the answer is "the AI told me to", that's a red flag.
- **Disclose AI co-authorship in your commits.** When a commit was meaningfully co-written with an AI, add a `Co-Authored-By` trailer in the commit message, e.g.:

  ```
  Add comment list endpoint

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

  (Adjust the name/email to whichever assistant you actually used. Most modern AI coding tools insert this automatically — don't strip it out.)
- You don't need to attribute every keystroke. Use your judgment: if the AI substantively shaped the code, credit it. If you used it only for a small lookup, you don't need to.

### Decisions

- **You decide the technical approach.** Data model, API shape, validation, frontend component structure, where to put files, how to handle errors, how to test — all your call.
- Read the existing codebase first. If there's already a pattern for something similar, follow it. If you choose to deviate, mention it in the PR description and explain why.
- If something is genuinely ambiguous, make a reasonable choice and write down the assumption in the PR. Do not block on asking questions for low-stakes decisions.

### Quality

- The code should run. The tests, if any exist, should pass.
- The feature should work end-to-end in a browser before you mark anything done. "It compiles" is not "it works".
- Be honest in the checklist. If something is half-finished or has a known bug, say so. We trust honesty more than polish.

---

## Completion checklist (copy this into your PR)

Mark each item: `[x]` done · `[~]` partial · `[ ]` not done. Add a one-line note where useful.

**Core**
- [ ] Users can view comments on a task
- [ ] Users can post a new comment
- [ ] Authors can edit their own comments
- [ ] Authors can delete their own comments
- [ ] Workspace admins/owners can delete any comment in their workspace
- [ ] Edited comments are visually distinguishable from unedited ones
- [ ] Permission rules enforced on the server (not just hidden in UI)
- [ ] Feature works in all supported UI languages
- [ ] Empty state, loading state, and error state are handled

**Engineering hygiene**
- [ ] Worked on a feature branch, not `main`
- [ ] Commit history is small, focused, and readable
- [ ] Commits that were co-written with an AI assistant are credited via `Co-Authored-By`
- [ ] PR description explains what was done and what was skipped
- [ ] Manually verified end-to-end in a browser (screenshots or recording attached)
- [ ] Demo link included: production URL **or** localhost + video walkthrough
- [ ] Database changes (if any) are reversible
- [ ] No obviously broken code, console errors, or unhandled promise rejections

**Stretch (optional)**
- [ ] Pagination / load more
- [ ] Relative timestamps
- [ ] `@mention` with autocomplete
- [ ] Comments appear in the task activity timeline
- [ ] Markdown or rich text
- [ ] Optimistic UI

---

## How we'll evaluate

We care about, roughly in this order:

1. **Does it work?** Can a person actually use the feature without hitting bugs?
2. **Is it safe?** Are permissions enforced where they need to be? Can user A do something to user B's data they shouldn't?
3. **Does it fit the codebase?** Did you read what's already there and write code in the same style, or did you invent your own conventions next to existing ones?
4. **Is the git history readable?** Can we follow how you built it from your commits?
5. **Did you communicate well?** Is the PR description honest and clear about what's done, what's not, and why?
6. **Is the code clean?** Naming, structure, no dead code, no debug logs left behind.

We do **not** require: 100% test coverage, perfect design, every nice-to-have shipped, or fancy abstractions. A small, working, honestly-described feature beats an ambitious half-broken one.

---

## Getting started

1. Fork or clone the repository.
2. Follow the README to get the app running locally.
3. Spend the first hour reading the code — especially how tasks, activity events, and existing API routes are wired up. You'll save time later.
4. Create your branch and start.

## Interview demo

After you submit the PR, we will schedule a single interview session in which you will:

- Walk us through the feature live (deployed URL or your local environment — whichever you used).
- Show us a few of your commits and explain how you broke the work down.
- Talk about how you used AI in the process: what you asked for, what you accepted, what you rejected, and why.
- Answer questions about decisions you made (data shape, permissions, edge cases).

Make sure your local setup is reproducible on your own machine on demo day. "It worked on my laptop yesterday" is the most common preventable failure here.

Good luck. We're looking forward to seeing your PR.
