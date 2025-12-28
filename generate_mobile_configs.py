import sqlite3
import os

DB_NAME = 'dorm.db'
# ✅ 改回本機網址 (注意：手機連不到這個，僅供電腦瀏覽器測試用)
BASE_URL = "http://127.0.0.1:5000" 
OUTPUT_DIR = "student_profiles"

# iOS 描述檔模板
IOS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
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
            <key>Label</key>
            <string>宿舍晚點名</string>
            <key>PayloadDescription</key>
            <string>設定 Web Clip 以進行宿舍點名</string>
            <key>PayloadDisplayName</key>
            <string>宿舍晚點名 (Web Clip)</string>
            <key>PayloadIdentifier</key>
            <string>com.dorm.webclip.{uuid}</string>
            <key>PayloadType</key>
            <string>com.apple.webClip.managed</string>
            <key>PayloadUUID</key>
            <string>{uuid}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Precomposed</key>
            <true/>
            <key>URL</key>
            <string>{link}</string>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>宿舍點名系統 - {name}</string>
    <key>PayloadIdentifier</key>
    <string>com.dorm.profile.{uuid}</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
"""

# Android 啟動檔模板 (自動跳轉 HTML)
ANDROID_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>正在啟動宿舍系統...</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="0; url={link}">
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 40px 20px; }}
        .card {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; background: #f9f9f9; }}
        a {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="card">
        <h3>👋 你好，{name}</h3>
        <p>正在為您開啟專屬點名系統...</p>
        <p>如果沒有自動跳轉，請點擊下方按鈕：</p>
        <a href="{link}">進入系統</a>
    </div>
</body>
</html>
"""

def generate_profiles():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"🛠️  正在生成設定檔 (Base URL: {BASE_URL})...")

    students = cursor.execute('''
        SELECT s.student_id, s.name, dp.device_uuid 
        FROM students s
        JOIN device_profiles dp ON s.student_id = dp.student_id
        WHERE s.is_special = 1
    ''').fetchall()

    count = 0
    for row in students:
        s_id = row[0]
        name = row[1]
        uuid_token = row[2]
        
        # 綁定 Token 的連結
        magic_link = f"{BASE_URL}/?token={uuid_token}"

        # 1. 產出 iOS 檔
        ios_content = IOS_TEMPLATE.format(uuid=uuid_token, link=magic_link, name=name)
        with open(os.path.join(OUTPUT_DIR, f"{s_id}_{name}_iOS.mobileconfig"), "w", encoding="utf-8") as f:
            f.write(ios_content)

        # 2. 產出 Android 檔
        android_content = ANDROID_TEMPLATE.format(link=magic_link, name=name)
        with open(os.path.join(OUTPUT_DIR, f"{s_id}_{name}_Android.html"), "w", encoding="utf-8") as f:
            f.write(android_content)
        
        count += 1

    conn.close()
    print("-" * 30)
    print(f"✅ 完成！共產生 {count * 2} 個檔案，請至 '{OUTPUT_DIR}' 查看。")

if __name__ == '__main__':
    generate_profiles()