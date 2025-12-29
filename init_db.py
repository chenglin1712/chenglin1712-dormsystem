import sqlite3
import os

# 資料庫檔案名稱
DB_NAME = 'dorm.db'

def create_tables():
    # 如果舊的資料庫存在，先刪除它，確保每次測試都是乾淨的環境
    # (等系統上線後，這行要拿掉，但在開發初期這樣比較方便除錯)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"舊的 {DB_NAME} 已刪除，重新建立中...")

    # 建立連結
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. 建立【學生資料表】
    # 我們加入了 gender (性別) 和 is_special (是否為國專班)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL UNIQUE,   -- 學號 (主鍵)
        name TEXT NOT NULL,                -- 姓名
        room_number TEXT,                  -- 房號
        bed_number TEXT,                   -- 床位 (A/B/C)
        gender TEXT,                       -- 性別 (男/女)
        is_special BOOLEAN DEFAULT 0,      -- 國專班標記 (1是, 0否)
        class_name TEXT,                   -- 班級 (例如: 資工一甲, 春8班)
        nationality TEXT                   -- 國籍
    );
    ''')

    # 2. 建立【裝置綁定表】(這是你之後要用描述檔綁定的核心)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS device_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        device_uuid TEXT NOT NULL UNIQUE,  -- 描述檔裡的 ID
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    );
    ''')

    # 3. 建立【點名紀錄表】
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS checkin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_uuid TEXT NOT NULL,
        checkin_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        ip_address TEXT,          -- ✅ 請補上這一行
        gps_lat REAL,             -- (建議) 既然 app.py 有用到 gps，這裡最好也補上
        gps_lng REAL,             -- (建議) 同上
        photo_filename TEXT,      -- (建議) app.py 也有用到照片欄位
        FOREIGN KEY (device_uuid) REFERENCES device_profiles (device_uuid)
    );
    ''')

    conn.commit()
    conn.close()
    print(f"✅ 成功！資料庫 {DB_NAME} 與三個表格已建立完成。")

if __name__ == '__main__':
    create_tables()