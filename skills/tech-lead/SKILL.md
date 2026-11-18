---
name: tech-lead
description: Run the current task under an isolated, read-only tech lead. Use when the user asks for a team leader, orchestrator, auditor or supervisor, or says "run it under the lead". Loads the checkpoint protocol the main session must follow.
---

# Working under the tech lead

The tech lead is a separate agent (`tech-lead`) that reads this session's transcript and directs you. You build; it judges. Once it is on, a hook refuses pushes, deploys, server changes, remote DB/KV/R2/secret writes, API writes to main and Notion writes until it has recorded GO.

## Start it

Spawn it once per task, visible, with the Agent tool:

- `subagent_type: "tech-lead"`, `description: "Tech lead: <task in four words>"`. No model or effort override (the agent definition fixes them).
- The prompt is the brief. Write it like a handover to a senior who has read nothing yet: what the user asked (quote them), what is done so far with evidence, your draft plan as numbered steps, the repos and branches involved, anything the user pre-authorised (quote them), other sessions touching the same repos, secrets that exist and where (never their values), and "First checkpoint: PLAN".
- Don't paste session ids or transcript paths; the start hook gives the lead those.

The lead's reply is its verdict. Keep its agent id and talk to it with `SendMessage` from then on: a new Agent call makes a second lead with no memory.

## Checkpoints

Send a message and wait for the verdict before continuing at:

| Kind | When |
|---|---|
| PLAN | before building, and again when the plan changes |
| SHIP | before any push, deploy, server change, remote DB or Notion write, anything external or irreversible |
| RESULT | after each step and after each agent reports back |
| DONE | before telling the user the work is finished |
| USER | whenever the user adds, changes or questions something |

Start each message with the kind. A SHIP lists the exact commands, the target, proof the branch contains the latest main, versions bumped, test output, the rollback, and the user's own words approving this step if they exist. A RESULT or DONE carries evidence (commands and their output, a page read back, a live request), not conclusions.

The lead answers GO, FIX or STOP. GO on a SHIP covers the listed commands only, for the time window it names. FIX means fix, then send a RESULT with evidence. STOP means stop and relay its reason to the user in one line. Its direction is binding unless it clashes with the user's words; then tell the user in one line and let them decide.

## Agents you spawn

Tell each one, in its brief, that it works under the tech lead and must report evidence, not conclusions. Relay the lead's corrections to the agent that owns the work. When an agent reports, send the lead a RESULT.

## What the gate is not

A GO is not the user's approval. Going live still needs their words, and permission prompts and classifier blocks are still theirs to clear. If a command is refused by the gate, don't work around it: send the lead a SHIP checkpoint.

## Switching it off

Only when the user says the task is over or asks to drop the lead: send it DONE, wait for the final verdict, then run `<LEAD> off <SESSION>`, using the two values from the end of the lead's first verdict. `<LEAD> status <SESSION>` shows whether the gate is on. A lead that has been quiet for 12 hours switches off on its own.
