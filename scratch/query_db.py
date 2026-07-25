import sqlite3

db_path = r'C:\Users\PHONGQK\.local\share\mimocode\mimocode.db'
c = sqlite3.connect(db_path)
cur = c.cursor()

# Recent sessions for this project
print("=== Recent sessions for ROBOT SLTP (last 20) ===")
cur.execute("""
    SELECT id, datetime(time_created/1000, 'unixepoch') as ts, title,
           summary_additions, summary_deletions, summary_files
    FROM session 
    WHERE project_id = '396b0dfb-fc05-4cf4-80af-72c1dfcbc975'
    ORDER BY time_created DESC LIMIT 20
""")
for row in cur.fetchall():
    sid, ts, title, adds, dels, files = row
    print(f"{sid} | {ts} | {title}")
    print(f"  +{adds} -{dels} | {files} files")

# Recent sessions NOT in this project
print("\n=== Recent sessions for OTHER projects ===")
cur.execute("""
    SELECT id, datetime(time_created/1000, 'unixepoch') as ts, title, project_id
    FROM session 
    WHERE project_id != '396b0dfb-fc05-4cf4-80af-72c1dfcbc975'
    ORDER BY time_created DESC LIMIT 10
""")
for row in cur.fetchall():
    print(f"{row[0]} | {row[1]} | {row[2]} | proj={row[3]}")

# Task counts
print("\n=== Task stats ===")
cur.execute("SELECT COUNT(*) FROM task")
print(f"Total tasks: {cur.fetchone()[0]}")
cur.execute("SELECT status, COUNT(*) FROM task GROUP BY status")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

c.close()
