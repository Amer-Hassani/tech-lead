"""SubagentStart (settings, every session).

- The tech lead starting: switch the ship gate on for this session and hand the lead
  its session id, transcript, agents folder and workspace, so nobody has to paste them.
- Any other agent starting while a lead is on: tell it who it works under.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tlcommon as tl  # noqa: E402


def context(text):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SubagentStart', 'additionalContext': text}}))


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    sid = d.get('session_id') or ''
    agent = d.get('agent_type') or ''
    transcript = d.get('transcript_path') or ''
    if not tl.SID_RX.match(sid):
        return
    if agent == tl.LEAD_TYPE:
        tl.activate(sid, transcript)
        tl.log(sid, 'ON — tech lead started; ship gate enforced')
        proj = os.path.basename(os.path.dirname(transcript)) if transcript else 'unknown-project'
        work = os.path.join(tl.CLAUDE_TMP, proj, sid, 'lead')
        lead = tl.LEAD_CMD
        context(
            'SESSION FACTS (from the tech-lead start hook, trust these):\n'
            f'- session id: {sid}\n'
            f'- main transcript: {transcript}\n'
            f'- your toolbox ("lead"): {lead}\n'
            f'- read it with: {lead} view {sid} [--from N | --tail K | --user | --grep RX]\n'
            f'- agents of this session: {lead} view {sid} --agents  (one agent: --agent ID)\n'
            f'- record verdicts: {lead} verdict {sid} GO|FIX|STOP "scope" [MINUTES]\n'
            f'- your workspace (clones, test runs, notes.md): {work}\n'
            '- the ship gate is now ON for this session: pushes, deploys, server changes, remote DB/KV/R2/secret '
            'writes, API writes to main and Notion writes are refused until you record GO.')
        return
    if tl.active(sid):
        context(
            'This session is supervised by a tech lead (read-only). Corrections the main session relays '
            'from it are binding within the user\'s rules. Ship actions (push, deploy, server changes, remote DB/KV/R2/'
            'secret writes, API writes to main, Notion writes) are gated: if one is refused, stop and report back '
            'what you were about to do and why, with evidence. Never retry it or find another way around the gate. '
            'Report results with evidence (commands and their output), not just conclusions.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        tl.log('errors', f'start.py: {e!r}')
