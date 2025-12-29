import sqlite3
import os

# 資料庫檔案名稱
DB_NAME = 'dorm.db'

def create_tables():
    # 如果舊的資料庫存在，先刪除它，確保每次測試都是乾淨的環境
    # (注意：這會清空所有舊資料！)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"舊的 {DB_NAME} 已刪除，重新建立中...")

    # 建立連結
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. 建立【學生資料表】
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        room_number TEXT,
        bed_number TEXT,
        gender TEXT,
        is_special BOOLEAN DEFAULT 0,
        class_name TEXT,
        nationality TEXT
    );
    ''')

    # 2. 建立【裝置綁定表】
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        device_uuid TEXT NOT NULL UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    );
    ''')

    # 3. 建立【點名紀錄表】(✅ 完整欄位版)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS checkin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_uuid TEXT NOT NULL,
        checkin_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        ip_address TEXT,          
        gps_lat REAL,             
        gps_lng REAL,             
        photo_filename TEXT,      
        FOREIGN KEY (device_uuid) REFERENCES device_profiles (device_uuid)
    );
    ''')

    conn.commit()
    conn.close()
    print(f"✅ 成功！資料庫 {DB_NAME} 重建完成 (包含 ip_address 欄位)。")

if __name__ == '__main__':
    create_tables()