import psycopg2
import sys

host = "jiaa-db.cveg64k8yuia.ap-northeast-2.rds.amazonaws.com"
password = "jiaa1234!!"
user = "jiaa_admin" # Testing this username
dbname = "postgres" # Default DB

print(f"Connecting to {host} with user {user}...")

try:
    conn = psycopg2.connect(
        host=host,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=10
    )
    print(">> SUCCESS! Connected successfully.")
    
    # Check if we can run a query
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"DB Version: {cur.fetchone()[0]}")
    conn.close()
    
except Exception as e:
    print(f">> FAIL: {e}")
