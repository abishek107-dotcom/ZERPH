import psycopg2
import os

connection_string = "postgresql://postgres:Abishek%40107@db.sstqmqteoewyaqkpknoe.supabase.co:5432/postgres"

schema_file = r"c:\Users\LENOVO\ZERPH\supabase_schema.sql"

try:
    print("Connecting to database...")
    conn = psycopg2.connect(connection_string)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Reading schema...")
    with open(schema_file, 'r') as f:
        schema = f.read()

    print("Executing schema...")
    cursor.execute(schema)
    
    print("Schema applied successfully!")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
