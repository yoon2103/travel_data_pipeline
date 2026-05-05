import json
import logging
import db_client
from course_builder import build_course

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

request = {
    "region":    "서울",
    "companion": "커플",
    "themes":    ["역사", "문화"],
    "template":  "standard",
}

conn = db_client.get_connection()
try:
    result = build_course(conn, request)
    print(json.dumps(result, ensure_ascii=False, indent=2))
finally:
    conn.close()
