import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def connect_to_db():
    try:
        # Read all database details from environment variables
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        if not all([db_host, db_user, db_password, db_name]):
            raise ValueError("One or more database environment variables are not set.")

        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        return conn
    except Error as e:
        print(f"❌ MySQL Connection Error: {e}")
        return None
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        return None

def setup_database():
    """Connects to the database and ensures the necessary table exists."""
    conn = connect_to_db()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        
        # Check if the conversations table exists
        cursor.execute("SHOW TABLES LIKE 'conversations'")
        result = cursor.fetchone()

        if not result:
            # If the table doesn't exist, create it
            print("Table 'conversations' not found. Creating it...")
            create_table_query = """
            CREATE TABLE conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                timestamp DATETIME NOT NULL
            );
            """
            cursor.execute(create_table_query)
            conn.commit()
            print("✅ Table 'conversations' created successfully.")
        
        cursor.close()
        conn.close()

    except Error as e:
        print(f"❌ Database Setup Error: {e}")

def log_to_db(username, question, answer):
    # This function remains the same as before
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
            print("✅ Conversation saved to database.")
    except Error as e:
        print(f"❌ MySQL Insert Error: {e}")

# Call this function once when your application starts
setup_database()