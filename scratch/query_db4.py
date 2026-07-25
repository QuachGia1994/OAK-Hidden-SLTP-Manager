import sqlite3
import json

db_path = r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db'
c = sqlite3.connect(db_path)
cur = c.cursor()

# Get tool calls (edits) from the most recent active session
sid = 'ses_0687adc99ffe5Sp3Xh8J0qGB8b'
cur.execute("""
    SELECT m.id, json_extract(m.data, '$.role') as role, p.data
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE m.session_id = ?
    AND json_extract(p.data, '$.type') = 'tool'
    ORDER BY m.time_created
""", (sid,))
for msg_id, role, pdata in cur.fetchall():
    pd = json.loads(pdata)
    tool = pd.get('tool', '')
    state = pd.get('state', {})
    inp = state.get('input', {})
    out = state.get('output', {})
    if tool in ('edit', 'write', 'bash'):
        preview = str(inp)[:200]
        print(f"  {tool}: {preview}")
    else:
        print(f"  {tool}: {str(inp)[:150]}")

# Also check: what is the current state of DISABLED_HOURS and SIGNAL_LOGIC_VERSION
c.close()
