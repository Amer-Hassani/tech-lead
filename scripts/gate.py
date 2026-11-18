"""PreToolUse (settings, every session): the tech-lead ship gate.

Off unless a tech lead is active in this session. When it is, ship actions from the
main session or any agent are refused until the lead has recorded GO. The user's own
permission rules still apply after the gate lets a command through.
Fails open: a bug here must never brick a session.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tlcommon as tl  # noqa: E402


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    tool = d.get('tool_name') or ''
    ti = d.get('tool_input') or {}
    sid = d.get('session_id') or ''
    agent = d.get('agent_type') or ''
    is_lead = agent == tl.LEAD_TYPE

    if tool in ('Write', 'Edit', 'NotebookEdit'):
        p = os.path.realpath(os.path.expanduser(ti.get('file_path') or ti.get('notebook_path') or ''))
        if p.startswith(tl.STATE + os.sep) or p.startswith(tl.LOG_DIR + os.sep):
            tl.deny('Tech-lead state and logs only change through the `lead` command.')
        return

    if tool == 'Bash':
        cmd = ti.get('command') or ''
        if re.search(r'tech-lead-data/(state|log)\b', cmd) or tl.STATE in cmd or tl.LOG_DIR in cmd:
            tl.deny('Tech-lead state and logs only change through the `lead` command. Use `lead status <session>` to read it.')
            return
        if re.search(r'(^|[\s;&|/])lead\s+verdict\b', cmd) and not is_lead:
            tl.deny('Only the tech lead records verdicts. Send it a checkpoint instead.')
            return
        if re.search(r'(^|[\s;&|/])lead\s+off\b', cmd) and agent:
            tl.deny('Only the main session switches the lead off, and only when the user says so.')
            return
        if is_lead:
            tl.touch(sid)
            return
        reason = tl.ship_reason(cmd, d.get('cwd') or '')
        shown = cmd
    elif tool.startswith('mcp__'):
        if is_lead or not tl.MCP_SHIP_RX.search(tool):
            return
        reason, shown = 'Notion write', tool
    else:
        return

    if not reason or not tl.active(sid):
        return
    who = agent or 'main'
    if tl.gate_open(sid):
        tl.log(sid, f'PASS [{who}] {reason}: {shown}')
        return
    v = tl.verdict(sid)
    last = (f"last verdict {v['verdict']} at {tl.hhmm(v['at'])} ({v['scope']})" if v else 'no verdict yet')
    tl.log(sid, f'BLOCK [{who}] {reason}: {shown}')
    tl.deny(
        f"Tech-lead ship gate: this is a {reason} and the lead has not given GO ({last}). "
        + ("Stop here and report back to the main session: what you were about to run, why, and the evidence. "
           "Don't retry it or reach the same result another way." if agent else
           "Send the lead a SHIP checkpoint (exact commands, target, evidence, rollback) and wait for its GO. "
           "Don't retry it or reach the same result another way."))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:  # fail open, but leave a trace
        tl.log('errors', f'gate.py: {e!r}')
