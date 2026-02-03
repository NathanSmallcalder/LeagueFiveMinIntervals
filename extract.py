import mysql.connector
import csv
import os

# 1. Database Configuration
db_config = {
    'host': 'localhost',
    'port': 3306,
    'database': 'LeagueStatsInterval',
    'user': 'league_user',
    'password': 'StrongPassword123!',
    'autocommit': False,
    'auth_plugin': 'mysql_native_password'
}

def export_to_csv():
    try:
        # Connect to the server
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(buffered=True)
        
        tables = ['matches', 'players', 'intervals']
        
        for table in tables:
            print(f"Starting export for: {table}...")
            
            # Fetch column names for the header
            cursor.execute(f"SHOW COLUMNS FROM {table}")
            headers = [column[0] for column in cursor.fetchall()]
            
            # Execute the main data query
            cursor.execute(f"SELECT * FROM {table}")
            
            file_path = f"{table}.csv"
            
            # Writing to CSV in chunks to save memory
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)  # Write header first
                
                # Fetching in batches of 10,000 to be safe with 1.7M rows
                while True:
                    rows = cursor.fetchmany(10000)
                    if not rows:
                        break
                    writer.writerows(rows)
            
            print(f"Successfully exported {table} to {file_path}")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    export_to_csv()