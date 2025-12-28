import sqlite3
import pandas as pd
import os
import uuid
import shutil

# ==========================================
# ⚙️ 設定區
# ==========================================
DB_NAME = 'dorm.db'
EXCEL_FILE = 'data.xlsx'
OUTPUT_DIR = 'student_profiles'

# ⚠️ 注意：如果要給手機用，請填入 ngrok 網址 (例如 "https://xxxx.ngrok-free.app")
# 如果只是本機測試，可以用 "http://127.0.0.1:8000"
BASE_URL = "http://127.0.0.1:8000"  

# ==========================================
# 🛠️ 核心功能
# ==========================================

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def sync_excel_to_db():
    print(f"📂 正在讀取 {EXCEL_FILE} 並同步至資料庫...")
    
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ 錯誤：找不到 {EXCEL_FILE}，請確認檔案存在。")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # 讀取 Excel (強制轉為字串以免學號開頭 0 被吃掉)
    try:
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl', dtype=str)
    except Exception as e:
        print(f"❌ 讀取 Excel 失敗: {e}")
        return

    count = 0
    for index, row in df.iterrows():
        # 邏輯判斷：只匯入 '國專班'
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

        # UPSERT: 如果學號存在就更新，不存在就新增
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
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ 名單同步完成，共處理 {count} 筆資料。")

def generate_keys_for_new_students():
    print("🔍 檢查是否有新生需要配發鑰匙 (UUID)...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 找出有學生資料但沒有 device_profiles 的人
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
            print(f"   ➕ 已配發鑰匙給: {s_name}")
        conn.commit()
    else:
        print("👌 所有學生都已有鑰匙。")
    
    conn.close()

def generate_files_and_links():
    print(f"🚀 開始製作 iOS/Android 設定檔與連結清單...")
    
    # 清空並重建輸出資料夾
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 抓取所有資料
    cursor.execute('''
        SELECT s.student_id, s.name, dp.device_uuid 
        FROM students s
        JOIN device_profiles dp ON s.student_id = dp.student_id
        WHERE s.is_special = 1
    ''')
    students = cursor.fetchall()

    links_file_content = "學號,姓名,專屬連結\n"
    generated_count = 0

    for row in students:
        s_id = row[0]
        name = row[1]
        token = row[2]
        
        # 1. 產生連結
        full_link = f"{BASE_URL}/?token={token}"
        links_file_content += f"{s_id},{name},{full_link}\n"

        # 2. 產生 iOS 描述檔 (.mobileconfig)
        ios_config = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>FullScreen</key>
            <true/>
            <key>IsRemovable</key>
            <true/>
            <key>Icon</key>
            <data>
            </data>
            <key>Label</key>
            <string>宿舍晚點名</string>
            <key>PayloadDescription</key>
            <string>設定 Web Clip 連結</string>
            <key>PayloadDisplayName</key>
            <string>宿舍晚點名 ({name})</string>
            <key>PayloadIdentifier</key>
            <string>com.dorm.checkin.{s_id}</string>
            <key>PayloadType</key>
            <string>com.apple.webClip.managed</string>
            <key>PayloadUUID</key>
            <string>{uuid.uuid4()}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Precomposed</key>
            <true/>
            <key>URL</key>
            <string>{full_link}</string>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>宿舍點名安裝檔 - {name}</string>
    <key>PayloadIdentifier</key>
    <string>com.dorm.checkin.profile.{s_id}</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{uuid.uuid4()}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>"""
        
        # 3. 產生 Android PWA 安裝檔 (.html)
        android_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>宿舍晚點名安裝 - {name}</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 40px 20px; background: #f0f2f5; }}
        .card {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }}
        .btn {{ display: block; width: 100%; padding: 15px; background: #007aff; color: white; text-decoration: none; border-radius: 10px; margin-top: 20px; font-weight: bold; }}
        h1 {{ color: #333; }}
        p {{ color: #666; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>👋 哈囉，{name}</h1>
        <p>這是您的專屬點名連結。</p>
        <p>請點擊下方按鈕進入系統，然後在瀏覽器選單中選擇<strong>「加到主畫面」</strong>以完成安裝。</p>
        <a href="{full_link}" class="btn">🚀 進入點名系統</a>
    </div>
</body>
</html>
"""

        # 寫入檔案
        filename_base = f"{s_id}_{name}"
        # iOS
        with open(os.path.join(OUTPUT_DIR, f"{filename_base}_iOS.mobileconfig"), "w", encoding="utf-8") as f:
            f.write(ios_config)
        # Android
        with open(os.path.join(OUTPUT_DIR, f"{filename_base}_Android.html"), "w", encoding="utf-8") as f:
            f.write(android_html)
            
        generated_count += 1

    # 4. 寫入總連結清單 txt
    with open("student_links.txt", "w", encoding="utf-8") as f:
        f.write(links_file_content)

    conn.close()
    print(f"🎉 全部完成！")
    print(f"   - 設定檔已產生於 '{OUTPUT_DIR}/' 資料夾 (共 {generated_count} 人)")
    print(f"   - 連結清單已更新至 'student_links.txt'")

# ==========================================
# 🚀 主程式執行點
# ==========================================
if __name__ == '__main__':
    # 1. 同步資料庫
    sync_excel_to_db()
    
    # 2. 補發鑰匙
    generate_keys_for_new_students()
    
    # 3. 產生檔案與連結
    generate_files_and_links()