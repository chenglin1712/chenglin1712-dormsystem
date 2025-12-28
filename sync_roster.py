import sqlite3
import pandas as pd
import os
import uuid

DB_NAME = 'dorm.db'
FILE_NAME = 'data.xlsx'

# ✅ 這裡已經拿掉 setup 了，只有純網址
BASE_URL = "http://127.0.0.1:5000" 

def sync_data():
    if not os.path.exists(FILE_NAME):
        print(f"❌ 找不到 {FILE_NAME}")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"📂 正在讀取 {FILE_NAME} 並進行差異比對...")

    # 1. 讀取 Excel
    df = pd.read_excel(FILE_NAME, engine='openpyxl', dtype=str)
    
    processed_students = [] 

    for index, row in df.iterrows():
        # 判斷是否為國專班
        info_text = str(row.get('學籍', '')) + str(row.get('身分', '')) + str(row.get('註2', ''))
        if '國專班' not in info_text:
            continue

        student_id = str(row.get('學號', '')).strip()
        name = str(row.get('姓名', '')).strip()
        room_number = str(row.get('房號', '')).strip()
        bed_number = str(row.get('床', '')).strip()
        class_name = str(row.get('班級', '')).strip()
        nationality = str(row.get('國籍', '')).strip()
        gender_raw = str(row.get('姓', '')).strip()
        gender = '女' if gender_raw == '女' else '男'
        
        processed_students.append(student_id)

        # UPSERT 更新資料
        cursor.execute('''
            INSERT INTO students (student_id, name, room_number, bed_number, gender, is_special, class_name, nationality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name=excluded.name,
                room_number=excluded.room_number,
                bed_number=excluded.bed_number,
                class_name=excluded.class_name,
                nationality=excluded.nationality;
        ''', (student_id, name, room_number, bed_number, gender, 1, class_name, nationality))

    conn.commit()
    print("✅ 名單同步完成。")

    # 2. 為沒有 UUID 的新生補發鑰匙
    print("🔍 檢查是否有新生需要產生 UUID...")
    cursor.execute('''
        SELECT s.student_id, s.name 
        FROM students s
        LEFT JOIN device_profiles dp ON s.student_id = dp.student_id
        WHERE dp.device_uuid IS NULL AND s.is_special = 1
    ''')
    
    new_students = cursor.fetchall()

    if new_students:
        print(f"🆕 發現 {len(new_students)} 位新同學，正在生成鑰匙...")
        for row in new_students:
            s_id = row[0]
            s_name = row[1]
            new_uuid = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO device_profiles (student_id, device_uuid)
                VALUES (?, ?)
            ''', (s_id, new_uuid))
            print(f"   ➕ 已配發: {s_name}")
        conn.commit()
    else:
        print("👌 所有人都已有鑰匙。")

    # 3. 匯出連結清單
    cursor.execute('''
        SELECT s.student_id, s.name, dp.device_uuid 
        FROM students s
        JOIN device_profiles dp ON s.student_id = dp.student_id
        WHERE s.is_special = 1
    ''')
    all_pairs = cursor.fetchall()
    
    with open("student_links.txt", "w", encoding="utf-8") as f:
        f.write("學號,姓名,專屬連結\n")
        for row in all_pairs:
            # 這裡組合連結，確保沒有 setup
            link = f"{BASE_URL}/?token={row[2]}"
            f.write(f"{row[0]},{row[1]},{link}\n")
            
    print(f"\n📄 最新連結清單已更新至 'student_links.txt' (共 {len(all_pairs)} 人)")
    conn.close()

if __name__ == '__main__':
    sync_data()