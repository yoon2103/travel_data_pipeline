import json
import db_client

conn = db_client.get_connection()
cur = conn.cursor()

cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'places'
ORDER BY ordinal_position
""")

rows = cur.fetchall()

print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))

cur.close()
conn.close()