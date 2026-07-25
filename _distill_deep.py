import sqlite3, json, time

DB = r"C:\Users\PHONGQK\.local\share\mimocode\mimocode.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cutoff_ms = int((time.time() - 30*86400) * 1000)

# 1. Find bash command sequences (tool call patterns per session)
print("=== REPEATED BASH COMMANDS (top patterns) ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp, count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'bash'
      AND m.time_created > ?
    GROUP BY inp
    HAVING n >= 3
    ORDER BY n DESC
    LIMIT 30
""", (cutoff_ms,))
for r in cur.fetchall():
    inp = r[0][:250] if r[0] else ""
    print(f"  [{r[1]}x] {inp}")

# 2. Find user messages about H-schedule changes (H=3,7,8,9,14 etc)
print("\n=== USER MESSAGES ABOUT H-SCHEDULE ===")
cur.execute("""
    SELECT m.id, substr(json_extract(m.data, '$.content'), 1, 300)
    FROM message m
    WHERE json_extract(m.data, '$.role') = 'user'
      AND m.time_created > ?
    ORDER BY m.time_created DESC
    LIMIT 80
""", (cutoff_ms,))
for r in cur.fetchall():
    content = r[1] if r[1] else ""
    keywords = ['h=', 'hour', 'schedule', 'logic', 'signal', 'xau', 'gbp', 'direction', 'dashboard', 'deploy', 'push', 'vercel', 'build']
    lower = content.lower()
    if any(kw in lower for kw in keywords):
        print(f"  [{r[0]}] {content[:250]}")

# 3. Find repeated edit targets (which files are edited together)
print("\n=== FILES EDITED TOGETHER (co-occurrence in same session) ===")
cur.execute("""
    SELECT m.session_id, json_extract(p.data, '$.state.input') as inp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'edit'
      AND m.time_created > ?
""", (cutoff_ms,))
session_edits = {}
for r in cur.fetchall():
    sid = r[0]
    inp = r[1] if r[1] else ""
    # Extract file_path from JSON
    try:
        d = json.loads(inp)
        fp = d.get('file_path', '')
        if fp and 'ROBOT SLTP' in fp:
            # Normalize to relative path
            rel = fp.split('ROBOT SLTP\\')[-1] if 'ROBOT SLTP\\' in fp else fp
            session_edits.setdefault(sid, set()).add(rel)
    except:
        pass

# Find pairs that co-occur frequently
from collections import Counter
pair_counter = Counter()
for sid, files in session_edits.items():
    files_list = sorted(files)
    for i in range(len(files_list)):
        for j in range(i+1, len(files_list)):
            pair_counter[(files_list[i], files_list[j])] += 1

print("  Top co-edited file pairs:")
for (a, b), n in pair_counter.most_common(15):
    print(f"    [{n}x] {a} <-> {b}")

# 4. Find repeated grep patterns
print("\n=== REPEATED GREP PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp, count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'grep'
      AND m.time_created > ?
    GROUP BY inp
    HAVING n >= 3
    ORDER BY n DESC
    LIMIT 20
""", (cutoff_ms,))
for r in cur.fetchall():
    inp = r[0][:250] if r[0] else ""
    print(f"  [{r[1]}x] {inp}")

# 5. Look at the biggest sessions for workflow patterns
print("\n=== BIG SESSIONS (most messages, last 30 days) ===")
big_sessions = [
    ('ses_094e83009ffeCS9DKYI43Tz8YM', 'Skip hour 17'),
    ('ses_0956070caffejde7IDSMl9vyvc', 'D-DIRECTION add GBP'),
    ('ses_096bd8c39ffex1pZTvQTZP1ww1', 'Dashboard auto-refresh'),
    ('ses_09756a028ffeWr5Eipx0c9hAwf', 'Check logic core T3,T5,T6'),
    ('ses_0687adc99ffe5Sp3Xh8J0qGB8b', 'Sua logic H=3,7,12,13'),
]
for sid, title in big_sessions:
    print(f"\n  --- {title} [{sid}] ---")
    # Get first few user messages to understand the workflow
    cur.execute("""
        SELECT substr(json_extract(m.data, '$.content'), 1, 300)
        FROM message m
        WHERE m.session_id = ? AND json_extract(m.data, '$.role') = 'user'
        ORDER BY m.time_created ASC
        LIMIT 5
    """, (sid,))
    for r in cur.fetchall():
        print(f"    USER: {r[0][:250]}")

    # Get tool sequence
    cur.execute("""
        SELECT json_extract(p.data, '$.tool') as tool,
               substr(json_extract(p.data, '$.state.input'), 1, 120) as inp
        FROM message m
        JOIN part p ON p.message_id = m.id
        WHERE m.session_id = ?
          AND json_extract(m.data, '$.role') = 'assistant'
          AND json_extract(p.data, '$.type') = 'tool'
        ORDER BY m.time_created ASC
        LIMIT 30
    """, (sid,))
    tools = []
    for r in cur.fetchall():
        tools.append(f"{r[0]}")
    # Show tool sequence summary
    from collections import Counter as C
    tc = C(tools)
    print(f"    Tool sequence: {' -> '.join(tools[:20])}")
    print(f"    Tool counts: {dict(tc)}")

conn.close()
