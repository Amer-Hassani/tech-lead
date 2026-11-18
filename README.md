# tech-lead

A read-only tech lead for Claude Code.

You keep building in your main session. The tech lead runs as a separate agent: it reads the whole session transcript and the code, checks the builder's claims itself, and answers each checkpoint with **GO**, **FIX** or **STOP**. While it is on, a hook refuses pushes, deploys and other ship actions until it has said GO.

## Install

```
/plugin marketplace add Amer-Hassani/tech-lead
/plugin install tech-lead@tech-lead
```

Restart Claude Code. Update later with `/plugin marketplace update tech-lead`.

Needs Python 3 on your PATH (macOS or Linux).

## Use

Say "run it under the lead", or type `/tech-lead`, at the start of a task. The main session spawns the lead and then checks in with it at:

| Checkpoint | When |
|---|---|
| PLAN | before building |
| SHIP | before any push, deploy, server change, remote DB or Notion write |
| RESULT | after each step, and when an agent reports back |
| DONE | before telling you the work is finished |
| USER | whenever you add or change something |

Each verdict is short: the decision, why, the next steps with what "done" looks like, and anything you need to decide yourself.

## What the ship gate blocks

Only while a lead is on in that session, and until it records GO (a GO opens a window, 30 minutes by default):

- `git push`, merges and releases through `gh` / `glab`, CI variable changes, `npm publish`
- `wrangler` / `cf` deploys, rollbacks, secret changes, KV and R2 writes, remote D1 writes
- `ssh` commands that change a server, `rsync` / `scp` to a server
- `curl` writes to Cloudflare, GitHub, GitLab, Telegram, Facebook, Notion, Resend, Twilio and `*.workers.dev`
- writes through any Notion MCP server

The gate is a guard rail for a supervised session, not a security boundary: a determined shell trick can still get past a regex. If the hook itself fails, it lets the command through.

## How it works

- `agents/tech-lead.md`: the lead. Read-only (no Edit, Write, Agent or MCP tools), low effort, with its own memory folder for what it learns across sessions.
- `skills/tech-lead/SKILL.md`: the protocol the main session follows.
- `hooks/hooks.json`: a `SubagentStart` hook that switches the gate on when the lead starts and hands it the session facts, and a `PreToolUse` hook that is the gate.
- `scripts/lead`: the lead's toolbox. `lead view` renders the transcript (secrets masked), `lead verdict` records GO / FIX / STOP, `lead status` and `lead off` are for the main session.

Gate state and logs live in `~/.claude/tech-lead-data/` (set `TECH_LEAD_HOME` to move them). A lead that has been quiet for 12 hours switches off on its own.

## Model

The lead is set to `model: fable`, `effort: low`. If your account can't use that model, change the `model:` line in `agents/tech-lead.md` (for example to `opus` or `sonnet`).

## Your own rules

Before its first verdict the lead reads `~/.claude/CLAUDE.md`, the project's `CLAUDE.md` and any memory index the session loads. Put your house rules there (branches, release steps, what must never go public) and it will enforce them on top of its defaults.

## License

MIT
