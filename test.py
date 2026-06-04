from supabase import create_client

url = "https://gbfdgtvvegyefhlztodw.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdiZmRndHZ2ZWd5ZWZobHp0b2R3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDQxODU3NCwiZXhwIjoyMDk1OTk0NTc0fQ.bel_ewlfBOMbbutvrWjADEUTAXFgWKFi839h5LDhi30"

client = create_client(url, key)
resp = client.table("users").select("*").eq("username", "admin").execute()
print("rows returned:", len(resp.data))
print("data:", resp.data)
import bcrypt
password_hash = "$2b$12$K5yl2qSiB0SrjnZXajC4tuXTBfDr1xAz8xDoVrZDg5I7HqBjHjDtG"
print("password check:", bcrypt.checkpw(b"admin123", password_hash.encode("utf-8")))

# Generate a fresh hash
new_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(12)).decode("utf-8")
print("New hash:", new_hash)

# Update it in the database
resp2 = client.table("users").update({"password_hash": new_hash}).eq("username", "admin").execute()
print("Update result:", resp2.data)

# Verify it works
check = bcrypt.checkpw(b"admin123", new_hash.encode("utf-8"))
print("Verify:", check)
