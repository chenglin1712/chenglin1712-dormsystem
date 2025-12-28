import os
import csv
import io
from flask import Flask, request, render_template, make_response, jsonify, send_from_directory
import sqlite3
from datetime import datetime
import math
# 引入處理檔案上傳需要的工具
from werkzeug.utils import secure_filename

app = Flask(__name__)
DB_NAME = 'dorm.db'

# ✅ [設定] 照片上傳資料夾與允許的副檔名
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 確保上傳資料夾存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 📍 [設定] 宿舍座標 (德明財經科技大學範例)
DORM_LAT = 24.998040186562055
DORM_LNG = 121.34191342114971
MAX_DISTANCE_METERS = 1000  # 測試用寬鬆距離

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# 檢查檔案副檔名是否合法
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 計算距離函數
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371e3 
    phi1 = lat1 * math.pi / 180
    phi2 = lat2 * math.pi / 180
    delta_phi = (lat2 - lat1) * math.pi / 180
    delta_lambda = (lon2 - lon1) * math.pi / 180
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ==========================================
# 路由 1: 首頁 (學生點名端 - 含拍照與 GPS)
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    student = None
    log = None
    error_msg = None
    
    token = request.args.get('token')
    if not token:
        token = request.cookies.get('student_uuid')

    if token:
        student = conn.execute('''
            SELECT s.name, s.room_number, s.student_id 
            FROM students s
            JOIN device_profiles dp ON s.student_id = dp.student_id
            WHERE dp.device_uuid = ?
        ''', (token,)).fetchone()

    # --- 處理點名 (POST) ---
    if request.method == 'POST' and student:
        try:
            # 1. 檢查 GPS
            user_lat = float(request.form.get('lat'))
            user_lng = float(request.form.get('lng'))
            distance = calculate_distance(user_lat, user_lng, DORM_LAT, DORM_LNG)
            print(f"📍 學生 {student['name']} 距離: {int(distance)}m")

            if distance > MAX_DISTANCE_METERS:
                error_msg = f"點名失敗！距離宿舍 {int(distance)} 公尺，請回到範圍內。"
            else:
                # 2. 檢查與處理照片
                if 'photo' not in request.files:
                    error_msg = "未上傳照片。"
                else:
                    file = request.files['photo']
                    if file.filename == '':
                        error_msg = "未選擇照片。"
                    elif file and allowed_file(file.filename):
                        # 產生安全的檔名：學號_時間戳記.jpg
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = secure_filename(f"{student['student_id']}_{timestamp}.jpg")
                        # 儲存檔案
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        
                        # 3. 寫入資料庫 (包含照片檔名)
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO checkin_logs (device_uuid, status, checkin_time, ip_address, gps_lat, gps_lng, photo_filename)
                            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?)
                        ''', (token, 'SUCCESS', request.remote_addr, user_lat, user_lng, filename))
                        conn.commit()
                        print(f"✅ {student['name']} 點名成功，照片已儲存: {filename}")
                    else:
                        error_msg = "照片格式不支援，請上傳 JPG 或 PNG。"

        except (TypeError, ValueError):
            error_msg = "無法抓取位置資訊，請確認 GPS 已開啟。"

    # --- 讀取今日狀態 ---
    if student:
        log = conn.execute('''
            SELECT checkin_time, status FROM checkin_logs 
            WHERE device_uuid = ? AND date(checkin_time) = date('now', 'localtime')
            ORDER BY id DESC LIMIT 1
        ''', (token,)).fetchone()

    conn.close()
    resp = make_response(render_template('index.html', student=student, log=log, error_msg=error_msg))
    if token and student:
        resp.set_cookie('student_uuid', token, max_age=60*60*24*365, httponly=True)
    return resp

# ==========================================
# 路由 2: 後台管理頁面 (支援日期選擇)
# ==========================================
@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    
    # ✅ 1. 決定要查詢的日期 (從網址參數抓，沒有就預設今天)
    target_date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    
    # ✅ 2. 抓出所有學生 + 指定日期(target_date) 的點名狀況
    query = '''
        SELECT 
            s.student_id,
            s.name, 
            s.room_number,
            s.class_name,
            log.checkin_time, 
            log.gps_lat, 
            log.gps_lng, 
            log.photo_filename,
            log.status
        FROM students s
        LEFT JOIN device_profiles dp ON s.student_id = dp.student_id
        LEFT JOIN (
            SELECT * FROM checkin_logs 
            WHERE date(checkin_time) = ? 
        ) log ON dp.device_uuid = log.device_uuid
        ORDER BY s.room_number ASC, s.student_id ASC
    '''
    # 這裡把 target_date 傳進去 SQL
    students = conn.execute(query, (target_date,)).fetchall()
    conn.close()
    
    # 3. 統計數據
    total_count = len(students)
    checked_in_count = sum(1 for s in students if s['checkin_time'])
    missing_count = total_count - checked_in_count
    rate = round((checked_in_count / total_count) * 100, 1) if total_count > 0 else 0
    
    # 回傳 current_date 給前端顯示
    return render_template('admin.html', 
                           students=students, 
                           current_date=target_date,
                           stats={
                               "total": total_count,
                               "checked": checked_in_count,
                               "missing": missing_count,
                               "rate": rate
                           })

# ==========================================
# 路由 2.1: 人工補點功能
# ==========================================
@app.route('/admin/manual_checkin', methods=['POST'])
def manual_checkin():
    student_id = request.form.get('student_id')
    conn = get_db_connection()
    
    # 先找出該學生的 device_uuid
    profile = conn.execute('SELECT device_uuid FROM device_profiles WHERE student_id = ?', (student_id,)).fetchone()
    
    if profile:
        uuid = profile['device_uuid']
        # 寫入一筆「人工補點」的紀錄
        conn.execute('''
            INSERT INTO checkin_logs (device_uuid, status, checkin_time, ip_address, photo_filename)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?)
        ''', (uuid, 'MANUAL', 'Admin Manual', 'manual_checkin.png')) 
        conn.commit()
    
    conn.close()
    # 重新整理頁面
    return '<script>window.location.href="/admin";</script>'

# ==========================================
# 路由 2.2: 匯出 CSV 報表 (支援日期選擇)
# ==========================================
@app.route('/admin/export_csv')
def export_csv():
    conn = get_db_connection()
    
    # ✅ 1. 也是一樣，看要匯出哪一天的 (預設今天)
    target_date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))

    # ✅ 2. SQL 也要跟著改用參數
    query = '''
        SELECT s.student_id, s.name, s.room_number, s.class_name, log.checkin_time, log.status
        FROM students s
        LEFT JOIN device_profiles dp ON s.student_id = dp.student_id
        LEFT JOIN (
            SELECT * FROM checkin_logs WHERE date(checkin_time) = ?
        ) log ON dp.device_uuid = log.device_uuid
        ORDER BY s.room_number ASC
    '''
    rows = conn.execute(query, (target_date,)).fetchall()
    conn.close()

    # 製作 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['學號', '姓名', '房號', '班級', '點名時間', '狀態']) # 表頭
    
    for row in rows:
        if row['checkin_time']:
            status = "已到"
            if row['status'] == 'MANUAL':
                status = "人工補點"
        else:
            status = "未到"
            
        time_str = row['checkin_time'] if row['checkin_time'] else ""
        writer.writerow([row['student_id'], row['name'], row['room_number'], row['class_name'], time_str, status])
    
    output.seek(0)
    
    # 檔名加上日期
    filename = f'dorm_report_{target_date.replace("-", "")}.csv'
    
    return make_response(output.getvalue(), 200, {
        'Content-Disposition': f'attachment; filename={filename}',
        'Content-Type': 'text/csv; charset=utf-8-sig'
    })

# ==========================================
# 路由 3: 提供照片檔案的特殊路由
# ==========================================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==========================================
# 路由 4: PWA 設定檔
# ==========================================
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "宿舍晚點名",
        "short_name": "晚點名",
        "start_url": ".",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#007aff",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/1946/1946488.png", "sizes": "192x192", "type": "image/png"}]
    })

if __name__ == '__main__':
    # 維持 Port 8000
    app.run(debug=True, port=8000)