import sqlite3
import json

db_path = r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db'
c = sqlite3.connect(db_path)
cur = c.cursor()

sid = 'ses_0687adc99ffe5Sp3Xh8J0qGB8b'

# Get assistant messages with tool calls
cur.execute("""
    SELECT m.id, json_extract(m.data, '$.role') as role, 
           datetime(m.time_created/1000, 'unixepoch') as ts,
           json_extract(m.data, '$.agent_id') as agent_id
    FROM message m
    WHERE m.session_id = ?
    ORDER BY m.time_created
""", (sid,))
msgs = cur.fetchall()
print(f"=== Messages in {sid} ({len(msgs)} total) ===")
for msg_id, role, ts, agent_id in msgs:
    print(f"  {ts} | {role} | agent={agent_id} | {msg_id}")

# Get text parts from assistant messages
print("\n=== Assistant text parts ===")
cur.execute("""
    SELECT m.id, json_extract(m.data, '$.role') as role, p.data
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE m.session_id = ?
    AND json_extract(m.data, '$.role') = 'assistant'
    AND json_extract(p.data, '$.type') = 'text'
    ORDER BY m.time_created
""", (sid,))
for msg_id, role, pdata in cur.fetchall():
    pd = json.loads(pdata)
    text = pd.get('text', '')[:500]
    if text.strip():
        print(f"\n  [{msg_id}] {text[:400]}")

c.close()
