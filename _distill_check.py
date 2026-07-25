import sqlite3, json

conn = sqlite3.connect(r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db')
cur = conn.cursor()

# Check how messages are stored
cur.execute("SELECT data FROM message WHERE session_id = 'ses_094e83009ffeCS9DKYI43Tz8YM' AND json_extract(data, '$.role') = 'user' LIMIT 1")
row = cur.fetchone()
if row:
    d = json.loads(row[0])
    print("Message data keys:", list(d.keys()))
    print("Full data:", json.dumps(d, indent=2, ensure_ascii=False)[:500])

# Check parts
cur.execute("SELECT data FROM part WHERE session_id = 'ses_094e83009ffeCS9DKYI43Tz8YM' LIMIT 3")
for r in cur.fetchall():
    d = json.loads(r[0])
    print("\nPart type:", d.get('type'))
    if d.get('type') == 'text':
        print("Text:", d.get('text', '')[:300])
    elif d.get('type') == 'tool':
        print("Tool:", d.get('tool'))
        inp = d.get('state', {}).get('input', '')
        if isinstance(inp, str):
            print("Input:", inp[:200])
        else:
            print("Input:", json.dumps(inp, ensure_ascii=False)[:200])

conn.close()
