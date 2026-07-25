import sqlite3, json

DB = r"C:\Users\PHONGQK\.local\share\mimocode\mimocode.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# 1. List real user sessions (not checkpoint-writer subagents)
print("=== REAL USER SESSIONS (last 30) ===")
cur.execute("SELECT id, title, time_created FROM session ORDER BY time_created DESC LIMIT 30")
sessions = cur.fetchall()
user_sessions = []
for s in sessions:
    if 'checkpoint-writer' not in s[1]:
        user_sessions.append(s)
        print(f"  {s[0]} | {s[1]} | {s[2]}")

# 2. Find repeated tool usage patterns
print("\n=== REPEATED TOOL USAGE PATTERNS (recent sessions) ===")
# Use 30 days ago as cutoff
import time
cutoff_ms = int((time.time() - 30*86400) * 1000)
cur.execute("""
    SELECT json_extract(p.data, '$.tool') as tool,
           substr(json_extract(p.data, '$.state.input'), 1, 150) as input_preview,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND m.time_created > ?
    GROUP BY tool, input_preview
    ORDER BY n DESC
    LIMIT 40
""", (cutoff_ms,))
for r in cur.fetchall():
    print(f"  [{r[2]}x] {r[0]}: {r[1][:120]}")

# 3. Find user messages with repeat keywords
print("\n=== USER MESSAGES WITH REPEAT KEYWORDS ===")
cur.execute("""
    SELECT m.id, substr(json_extract(m.data, '$.content'), 1, 200)
    FROM message m
    WHERE json_extract(m.data, '$.role') = 'user'
      AND m.time_created > ?
    ORDER BY m.time_created DESC
    LIMIT 50
""", (cutoff_ms,))
for r in cur.fetchall():
    content = r[1] if r[1] else ""
    keywords = ['again', 'mỗi', 'every time', 'lần trước', 'like last time', 'the usual', 'repeat', 'same as before', 'như', 'trước']
    lower_content = content.lower()
    if any(kw in lower_content for kw in keywords):
        print(f"  [{r[0]}] {content[:180]}")

# 4. Session details for real sessions
print("\n=== USER SESSION TITLES AND CONTENT SUMMARY ===")
for s in user_sessions[:15]:
    sid = s[0]
    cur.execute("""
        SELECT count(*) FROM message WHERE session_id = ?
    """, (sid,))
    msg_count = cur.fetchone()[0]
    print(f"  {s[0]} | {s[1]} | messages: {msg_count}")

# 5. Tool types per session
print("\n=== TOOL USAGE PER SESSION ===")
cur.execute("""
    SELECT m.session_id,
           json_extract(p.data, '$.tool') as tool,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND m.time_created > ?
    GROUP BY m.session_id, tool
    HAVING n >= 3
    ORDER BY m.session_id, n DESC
""", (cutoff_ms,))
current_session = None
for r in cur.fetchall():
    if r[0] != current_session:
        current_session = r[0]
        print(f"\n  Session {r[0]}:")
    print(f"    {r[1]}: {r[2]}x")

# 6. Check for repeated file paths in tool inputs
print("\n=== REPEATED FILE PATHS IN TOOL INPUTS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND m.time_created > ?
    GROUP BY inp
    HAVING n >= 3
    ORDER BY n DESC
    LIMIT 20
""", (cutoff_ms,))
for r in cur.fetchall():
    inp = r[0][:200] if r[0] else ""
    print(f"  [{r[1]}x] {inp}")

conn.close()
