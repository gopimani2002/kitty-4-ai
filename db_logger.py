import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def connect_to_db():
    try:
        db_password = os.getenv("DB_PASSWORD") # Read the password from an environment variable
        
        if not db_password:
            # Handle the case where the password isn't set, which is good practice
            raise ValueError("DB_PASSWORD environment variable is not set.")

        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password=db_password, # Use the environment variable here
            database='kitty_db'
        )
        return conn
    except Error as e:
        print(f"❌ MySQL Connection Error: {e}")
        return None
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        return None


def log_to_db(username, question, answer):
    try:
        conn = connect_to_db()
        if conn:
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = """
                INSERT INTO conversations (username, question, answer, timestamp)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (username, question, answer, timestamp))
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Conversation saved to database with timestamp.")
    except Error as e:
        print(f"❌ MySQL Insert Error: {e}")