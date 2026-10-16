import hashlib, os, subprocess, yaml
password = os.environ.get("DEMO_PASSWORD")
def find(conn, uid):
    return conn.cursor().execute("SELECT * FROM users WHERE id=?", (uid,))
def run(host):
    subprocess.run(["ping", "-c", "1", host], check=False)
def load(s):
    return yaml.safe_load(s)
def digest(b):
    return hashlib.sha256(b).hexdigest()
