# Intentionally vulnerable demo. Do NOT run; scan only. Values are fake.
import os, sqlite3, hashlib, yaml
password = "DemoPassword123"
def find(conn, uid):
    return conn.cursor().execute("SELECT * FROM users WHERE id=" + uid)
def run(host):
    os.system("ping " + host)
def load(s):
    return yaml.load(s)
def digest(b):
    return hashlib.md5(b).hexdigest()
