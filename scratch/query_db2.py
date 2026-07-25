import sqlite3
import json

db_path = r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db'
c = sqlite3.connect(db_path)
cur = c.cursor()

# Get user messages from recent sessions containing keywords about rules/decisions
sessions = [
    'ses_0687adc99ffe5Sp3Xh8J0qGB8b',
    'ses_094e83009ffeCS9DKYI43Tz8YM',
    'ses_0956070caffejde7IDSMl9vyvc',
    'ses_096bd8c39ffex1pZTvQTZP1ww1',
    'ses_1063c5258ffe7vPcH2RlPy4I6k',
    'ses_102c03d41ffeSXw6Kgs0XNHDuB',
    'ses_102704e86ffeWUNO58n7AvbvCD',
    'ses_1025d6626ffex5Bgd1QXlrm14n',
    'ses_100f1e800ffepqyx5Hl8l7FAeU',
]

for sid in sessions:
    cur.execute("""
        SELECT m.id, json_extract(m.data, '$.role') as role, p.data
        FROM message m
        JOIN part p ON p.message_id = m.id
        WHERE m.session_id = ? AND json_extract(m.data, '$.role') = 'user'
        AND json_extract(p.data, '$.type') = 'text'
        ORDER BY m.time_created
        LIMIT 3
    """, (sid,))
    rows = cur.fetchall()
    if rows:
        print(f"\n=== User messages from {sid} ===")
        for msg_id, role, pdata in rows:
            pd = json.loads(pdata)
            text = pd.get('text', '')[:300]
            print(f"  [{role}] {text}")

c.close()
