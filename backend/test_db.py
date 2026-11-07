from sqlalchemy import text
from app.database.connection import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))
        version = result.fetchone()

        print("Successfully connected to Neon!")
        print("PostgreSQL version:")
        print(version[0])

except Exception as e:
    print("Database connection failed!")
    print("Error:", e)