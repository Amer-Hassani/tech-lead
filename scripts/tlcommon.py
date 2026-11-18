"""Shared paths, state and command patterns for the tech-lead hooks and the `lead` CLI.

Everything here is a guard rail for trusted, supervised sessions, not a security
boundary: a determined shell trick can still get past a regex.
"""
import json
import os
import re
import time

HOME = os.path.expanduser('~')
BASE = os.path.realpath(os.environ.get('TECH_LEAD_HOME') or os.path.join(HOME, '.claude', 'tech-lead-data'))
STATE = os.path.join(BASE, 'state')
ACTIVE_DIR = os.path.join(STATE, 'active')
VERDICT_DIR = os.path.join(STATE, 'verdict')
LOG_DIR = os.path.join(BASE, 'log')
LEAD_CMD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lead')
CLAUDE_TMP = os.path.join('/private/tmp' if os.uname().sysname == 'Darwin' else '/tmp', f'claude-{os.getuid()}')
LEAD_TYPE = 'tech-lead'
ACTIVE_HOURS = 12
SID_RX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

SEG = r'[^\n;&|]*'  # stays inside one shell segment

# Ship actions: anything that changes what's live or what lives outside this machine.
SHIP_PATTERNS = [
    (r'\bgit\b' + SEG + r'\spush\b', 'git push'),
    (r'\b(wrangler|cf)\b' + SEG + r'\b(deploy|publish|rollback)', 'deploy / rollback'),
    (r'\b(wrangler|cf)\b' + SEG + r'\bsecrets?\b' + SEG + r'\b(put|create|update|delete|bulk)\b', 'secret change'),
    (r'\b(wrangler|cf)\b' + SEG + r'\b(kv|r2)\b' + SEG + r'\b(put|delete|create)\b', 'KV / R2 write'),
    (r'\b(glab\s+(mr\s+merge|release\s+create|variable\s+(set|update|delete))|gh\s+(pr\s+merge|release\s+create))\b', 'merge / release / CI variable'),
    (r'\bnpm\s+publish\b', 'npm publish'),
    (r'\b(rsync|scp)\b' + SEG + r'\s[\w.-]+@[\w.-]+:', 'copy to a server'),
]
SHIP_RX = [(re.compile(p, re.I), label) for p, label in SHIP_PATTERNS]

SQL_WRITE = re.compile(r'\b(insert|update|delete|drop|alter|create|replace|truncate)\b', re.I)
D1_RX = re.compile(r'\b(wrangler|cf)\b' + SEG + r'\bd1\b' + SEG + r'\b(execute|query)\b', re.I)
SSH_RX = re.compile(r'\bssh\b', re.I)
SSH_MUTATE = re.compile(
    r'\b(docker(\s+compose)?\s+(up|down|restart|stop|start|rm|run|build|pull|kill|exec|cp)'
    r'|systemctl\s+(restart|stop|start|reload|enable|disable)|reboot|shutdown'
    r'|apt(-get)?\s+(install|remove|purge|upgrade)|crontab\s+-[er]'
    r'|rm|mv|cp|tee|kill|pkill|chmod|chown|truncate|sed\s+-i)\b|>', re.I)
HTTP_WRITE = re.compile(r'(\s(-X|--request)\s*["\']?(POST|PUT|PATCH|DELETE)|\s(-d|--data\S*|-F|--form|--json|-T|--upload-file)\s)', re.I)
CURL_SHIP_HOSTS = re.compile(r'(api\.cloudflare\.com|gitlab\.com/api|api\.github\.com|api\.telegram\.org|graph\.facebook\.com|api\.notion\.com|api\.resend\.com|api\.twilio\.com'
                             r'|\.workers\.dev|/api/admin/)', re.I)
# MCP writes into a workspace someone else reads (Notion pages, calendars), on any Notion MCP server.
MCP_SHIP_RX = re.compile(r'^mcp__.+__notion-(create|update|delete|move|duplicate|restore|upload|calendar-(create|update|cancel))', re.I)
GLAB_API_RX = re.compile(r'\b(glab|gh)\s+api\b', re.I)
API_WRITE = re.compile(r'(\s(-X|--method)\s*["\']?(POST|PUT|PATCH|DELETE)|\s(-f|-F|--field|--raw-field|--input)\s)', re.I)


def ship_reason(cmd, cwd=''):
    """Return a short label when `cmd` is a ship action, else None."""
    for rx, label in SHIP_RX:
        if rx.search(cmd):
            return label
    if D1_RX.search(cmd) and SQL_WRITE.search(cmd) and (re.search(r'\bcf\b', cmd) or '--remote' in cmd):
        return 'remote D1 write'
    if SSH_RX.search(cmd) and SSH_MUTATE.search(cmd.split('ssh', 1)[1]):
        return 'server change over ssh'
    if re.search(r'\bcurl\b', cmd) and HTTP_WRITE.search(' ' + cmd + ' ') and CURL_SHIP_HOSTS.search(cmd):
        return 'API write (curl)'
    if GLAB_API_RX.search(cmd) and API_WRITE.search(' ' + cmd + ' '):
        if re.search(r'\bmain\b|merge_requests/\d+/merge', cmd) or _input_targets_main(cmd, cwd):
            return 'GitLab/GitHub API write to main'
    return None


def _input_targets_main(cmd, cwd):
    m = re.search(r'--input\s+["\']?([^\s"\']+)', cmd)
    if not m or m.group(1) == '-':
        return False
    path = os.path.expanduser(m.group(1))
    if not os.path.isabs(path):
        path = os.path.join(cwd or os.getcwd(), path)
    try:
        if os.path.getsize(path) > 5_000_000:
            return False
        with open(path, errors='ignore') as f:
            body = f.read()
    except OSError:
        return False
    return bool(re.search(r'"(branch|ref|target_branch)"\s*:\s*"main"', body))


# ---- state -------------------------------------------------------------

def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def active(sid):
    rec = _read(os.path.join(ACTIVE_DIR, sid + '.json')) if sid else None
    if not rec:
        return None
    if time.time() - rec.get('last_seen', 0) > ACTIVE_HOURS * 3600:
        return None
    return rec


def activate(sid, transcript):
    path = os.path.join(ACTIVE_DIR, sid + '.json')
    rec = _read(path) or {'sid': sid, 'started': time.time()}
    rec.update(transcript=transcript, last_seen=time.time())
    _write(path, rec)
    return rec


def touch(sid):
    rec = _read(os.path.join(ACTIVE_DIR, sid + '.json'))
    if rec and time.time() - rec.get('last_seen', 0) > 60:
        rec['last_seen'] = time.time()
        _write(os.path.join(ACTIVE_DIR, sid + '.json'), rec)


def deactivate(sid):
    for d in (ACTIVE_DIR, VERDICT_DIR):
        try:
            os.remove(os.path.join(d, sid + '.json'))
        except OSError:
            pass


def verdict(sid):
    return _read(os.path.join(VERDICT_DIR, sid + '.json'))


def set_verdict(sid, value, scope, minutes):
    now = time.time()
    rec = {'verdict': value, 'scope': scope, 'at': now,
           'until': now + minutes * 60 if value == 'GO' and minutes > 0 else 0}
    _write(os.path.join(VERDICT_DIR, sid + '.json'), rec)
    return rec


def gate_open(sid):
    v = verdict(sid)
    return bool(v and v.get('verdict') == 'GO' and v.get('until', 0) > time.time())


def log(sid, line):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, (sid or 'unknown') + '.log'), 'a') as f:
            f.write(time.strftime('%d/%m/%Y %H:%M:%S ') + line.replace('\n', ' ')[:600] + '\n')
    except OSError:
        pass


def hhmm(t):
    return time.strftime('%H:%M', time.localtime(t)) if t else '—'


# ---- hook output -------------------------------------------------------

def deny(reason):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason}}))
