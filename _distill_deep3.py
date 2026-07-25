import sqlite3, json

conn = sqlite3.connect(r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db')
cur = conn.cursor()

sessions = [
    'ses_094e83009ffeCS9DKYI43Tz8YM',
    'ses_0956070caffejde7IDSMl9vyvc',
    'ses_096bd8c39ffex1pZTvQTZP1ww1',
    'ses_09756a028ffeWr5Eipx0c9hAwf',
    'ses_0687adc99ffe5Sp3Xh8J0qGB8b',
]
for sid in sessions:
    cur.execute(
        "SELECT json_extract(data, '$.content') FROM message WHERE session_id = ? AND json_extract(data, '$.role') = 'user' ORDER BY time_created ASC LIMIT 3",
        (sid,)
    )
    rows = cur.fetchall()
    print(f'=== {sid} ===')
    for r in rows:
        if r[0]:
            print(f'  {r[0][:400]}')
    print()

# Also get user messages from the very first messages in all sessions to see what people ask for
print('\n=== ALL USER FIRST MESSAGES (last 30 sessions) ===')
cur.execute(
    "SELECT s.id, s.title, json_extract(m.data, '$.content') FROM session s JOIN message m ON m.session_id = s.id WHERE json_extract(m.data, '$.role') = 'user' AND s.title NOT LIKE 'checkpoint-writer%' AND s.title NOT LIKE 'Auto %' GROUP BY s.id HAVING m.time_created = (SELECT MIN(time_created) FROM message WHERE session_id = s.id AND json_extract(data, '$.role') = 'user') ORDER BY s.time_created DESC LIMIT 20"
)
for r in cur.fetchall():
    content = r[2][:300] if r[2] else "(empty)"
    print(f'  [{r[0]}] {r[1]}: {content}')

conn.close()
