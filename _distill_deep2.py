import sqlite3, json, time

DB = r"C:\Users\PHONGQK\.local\share\mimocode\mimocode.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get user messages for big sessions
big_sessions = [
    ('ses_094e83009ffeCS9DKYI43Tz8YM', 'Skip hour 17'),
    ('ses_0956070caffejde7IDSMl9vyvc', 'D-DIRECTION add GBP'),
    ('ses_096bd8c39ffex1pZTvQTZP1ww1', 'Dashboard auto-refresh'),
    ('ses_09756a028ffeWr5Eipx0c9hAwf', 'Check logic core T3,T5,T6'),
    ('ses_0687adc99ffe5Sp3Xh8J0qGB8b', 'Sua logic H=3,7,12,13'),
]
for sid, title in big_sessions:
    print(f"\n--- {title} [{sid}] ---")
    cur.execute("""
        SELECT json_extract(m.data, '$.content')
        FROM message m
        WHERE m.session_id = ? AND json_extract(m.data, '$.role') = 'user'
        ORDER BY m.time_created ASC
        LIMIT 5
    """, (sid,))
    for r in cur.fetchall():
        content = r[0] if r[0] else "(empty)"
        print(f"  USER: {content[:300]}")

    # Tool sequence
    cur.execute("""
        SELECT json_extract(p.data, '$.tool') as tool
        FROM message m
        JOIN part p ON p.message_id = m.id
        WHERE m.session_id = ?
          AND json_extract(m.data, '$.role') = 'assistant'
          AND json_extract(p.data, '$.type') = 'tool'
        ORDER BY m.time_created ASC
        LIMIT 40
    """, (sid,))
    tools = [r[0] for r in cur.fetchall() if r[0]]
    print(f"  Tool sequence: {' -> '.join(tools[:30])}")

# Find repeated "deploy workflow" sequences
print("\n=== DEPLOY WORKFLOW SEQUENCES ===")
cur.execute("""
    SELECT m.session_id,
           json_extract(p.data, '$.tool') as tool,
           json_extract(p.data, '$.state.input') as inp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'bash'
      AND json_extract(p.data, '$.state.input') LIKE '%git push%'
    ORDER BY m.time_created ASC
""", ())
push_sessions = {}
for r in cur.fetchall():
    sid = r[0]
    push_sessions.setdefault(sid, []).append(r[2][:200] if r[2] else "")

print(f"  Sessions with git push: {len(push_sessions)}")
for sid, pushes in list(push_sessions.items())[:5]:
    print(f"    {sid}: {len(pushes)} pushes")
    for p in pushes[:2]:
        print(f"      {p[:150]}")

# Find patterns: what happens BEFORE each push
print("\n=== PRE-PUSH WORKFLOW (what happens before git push) ===")
cur.execute("""
    SELECT m.session_id,
           json_extract(p.data, '$.tool') as tool,
           json_extract(p.data, '$.state.input') as inp,
           m.time_created
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'bash'
    ORDER BY m.time_created ASC
""", ())

# Build per-session tool timelines
session_tools = {}
for r in cur.fetchall():
    sid = r[0]
    inp = r[2][:200] if r[2] else ""
    ts = r[3]
    session_tools.setdefault(sid, []).append((ts, inp))

# For sessions with push, find what preceded it
push_pre = []
for sid, tools in session_tools.items():
    for i, (ts, inp) in enumerate(tools):
        if 'git push' in inp:
            # Get 5 commands before
            pre = [t[1] for t in tools[max(0,i-5):i]]
            push_pre.append(pre)

from collections import Counter
pre_patterns = Counter()
for pre in push_pre:
    key = " -> ".join([p.split('"command":"')[1][:40] if '"command":"' in p else p[:40] for p in pre[-3:]])
    pre_patterns[key] += 1

print("  Top pre-push sequences:")
for pattern, n in pre_patterns.most_common(10):
    print(f"    [{n}x] {pattern}")

conn.close()
