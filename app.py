from flask import Flask, request, render_template, make_response, jsonify
import sqlite3
from datetime import datetime
import math

app = Flask(__name__)
BASE_URL = "http://127.0.0.1:5000"
DB_NAME = 'dorm.db'

# 📍 [設定] 宿舍的中心點座標
# (請記得改成真實座標，這裡目前是測試用的範例座標)
DORM_LAT = 24.998040186562055
DORM_LNG = 121.34191342114971

# 允許的誤差範圍 (公尺)
# 開發測試時設大一點 (1000m)，正式上線建議改為 100m
MAX_DISTANCE_METERS = 1000

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# [核心功能] 計算兩點經緯度距離 (Haversine formula)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371e3 # 地球半徑 (公尺)
    phi1 = lat1 * math.pi / 180
    phi2 = lat2 * math.pi / 180
    delta_phi = (lat2 - lat1) * math.pi / 180
    delta_lambda = (lon2 - lon1) * math.pi / 180

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c # 回傳單位：公尺

# ----------------------------------------------------
# 路由 1: 首頁 (點名系統核心)
# ----------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    student = None
    log = None
    error_msg = None
    
    # 1. 抓取 Token (網址列優先，其次是 Cookie)
    token = request.args.get('token')
    if not token:
        token = request.cookies.get('student_uuid')

    # 2. 驗證身分 (使用 device_uuid 查詢)
    if token:
        student = conn.execute('''
            SELECT s.name, s.room_number, s.student_id 
            FROM students s
            JOIN device_profiles dp ON s.student_id = dp.student_id
            WHERE dp.device_uuid = ?
        ''', (token,)).fetchone()

    # 3. 處理點名 (POST 請求)
    if request.method == 'POST' and student:
        try:
            # 從前端表單取得 GPS 座標
            user_lat = float(request.form.get('lat'))
            user_lng = float(request.form.get('lng'))
            
            # 計算距離
            distance = calculate_distance(user_lat, user_lng, DORM_LAT, DORM_LNG)
            print(f"📍 學生 {student['name']} 距離宿舍: {int(distance)} 公尺")

            if distance <= MAX_DISTANCE_METERS:
                cursor = conn.cursor()
                # ✅ 寫入點名紀錄 (確保欄位是 device_uuid)
                cursor.execute('''
                    INSERT INTO checkin_logs (device_uuid, status, checkin_time, ip_address, gps_lat, gps_lng)
                    VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?)
                ''', (token, 'SUCCESS', request.remote_addr, user_lat, user_lng))
                conn.commit()
            else:
                error_msg = f"點名失敗！偵測到距離宿舍 {int(distance)} 公尺，請回到宿舍範圍內。"
        
        except (TypeError, ValueError):
            error_msg = "無法抓取位置資訊，請確認手機 GPS 已開啟並允許瀏覽器讀取位置。"

    # 4. 讀取今日狀態 (確保欄位是 device_uuid)
    if student:
        log = conn.execute('''
            SELECT checkin_time, status FROM checkin_logs 
            WHERE device_uuid = ? AND date(checkin_time) = date('now', 'localtime')
            ORDER BY id DESC LIMIT 1
        ''', (token,)).fetchone()

    conn.close()

    # 5. 回傳畫面
    resp = make_response(render_template('index.html', student=student, log=log, error_msg=error_msg))
    
    # 如果這次有 Token，更新 Cookie (保持登入 1 年)
    if token and student:
        resp.set_cookie('student_uuid', token, max_age=60*60*24*365, httponly=True)

    return resp

# ----------------------------------------------------
# 路由 2: PWA 設定檔 (給 Android 加到主畫面用)
# ----------------------------------------------------
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "宿舍晚點名",
        "short_name": "晚點名",
        "start_url": ".",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#007aff",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/1946/1946488.png",
                "sizes": "192x192",
                "type": "image/png"
            }
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)