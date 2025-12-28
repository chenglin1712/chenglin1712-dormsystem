import os
import csv
import io
# ✅ 新增 session, redirect, url_for
from flask import Flask, request, render_template, make_response, jsonify, send_from_directory, session, redirect, url_for
import sqlite3
from datetime import datetime
import math
from werkzeug.utils import secure_filename

app = Flask(__name__)
# ✅ [重要] 設定 Secret Key，Session 才能運作
app.secret_key = 'your_super_secret_key_change_this_in_production' 

DB_NAME = 'dorm.db'

# ✅ [設定] 照片上傳資料夾與允許的副檔名
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 確保上傳資料夾存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 📍 [設定] 宿舍座標
DORM_LAT = 24.998040186562055
DORM_LNG = 121.34191342114971
MAX_DISTANCE_METERS = 1000 

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
# 路由 0: 登入與登出 (新增!)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        # ✅ 這裡設定密碼為 admin
        if password == 'admin':
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error="❌ 密碼錯誤，請重試")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('login'))

# ==========================================
# 路由 1: 首頁 (學生點名端)
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
            user_lat = float(request.form.get('lat'))
            user_lng = float(request.form.get('lng'))
            distance = calculate_distance(user_lat, user_lng, DORM_LAT, DORM_LNG)
            print(f"📍 學生 {student['name']} 距離: {int(distance)}m")

            if distance > MAX_DISTANCE_METERS:
                error_msg = f"點名失敗！距離宿舍 {int(distance)} 公尺，請回到範圍內。"
            else:
                if 'photo' not in request.files:
                    error_msg = "未上傳照片。"
                else:
                    file = request.files['photo']
                    if file.filename == '':
                        error_msg = "未選擇照片。"
                    elif file and allowed_file(file.filename):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = secure_filename(f"{student['student_id']}_{timestamp}.jpg")
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        
                        cursor = conn.cursor()
                        # 注意：這裡確保 ip_address 寫入正確
                        cursor.execute('''
                            INSERT INTO checkin_logs (device_uuid, status, checkin_time, ip_address, gps_lat, gps_lng, photo_filename)
                            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?)
                        ''', (token, 'SUCCESS', request.remote_addr, user_lat, user_lng, filename))
                        conn.commit()
                        print(f"✅ {student['name']} 點名成功")
                    else:
                        error_msg = "照片格式不支援。"
        except (TypeError, ValueError):
            error_msg = "無法抓取位置資訊。"

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
# 路由 2: 後台管理頁面 (✅ 已加入登入保護)
# ==========================================
@app.route('/admin')
def admin_dashboard():
    # 🔒 保護檢查：如果沒登入，踢回 login 頁面
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    target_date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    
    query = '''
        SELECT 
            s.student_id, s.name, s.room_number, s.class_name,
            log.checkin_time, log.gps_lat, log.gps_lng, log.photo_filename, log.status
        FROM students s
        LEFT JOIN device_profiles dp ON s.student_id = dp.student_id
        LEFT JOIN (
            SELECT * FROM checkin_logs WHERE date(checkin_time) = ? 
        ) log ON dp.device_uuid = log.device_uuid
        ORDER BY s.room_number ASC, s.student_id ASC
    '''
    students = conn.execute(query, (target_date,)).fetchall()
    conn.close()
    
    total_count = len(students)
    checked_in_count = sum(1 for s in students if s['checkin_time'])
    missing_count = total_count - checked_in_count
    rate = round((checked_in_count / total_count) * 100, 1) if total_count > 0 else 0
    
    return render_template('admin.html', 
                           students=students, 
                           current_date=target_date,
                           stats={"total": total_count, "checked": checked_in_count, "missing": missing_count, "rate": rate})

# ==========================================
# 路由 2.1: 人工補點 (✅ 已加入登入保護)
# ==========================================
@app.route('/admin/manual_checkin', methods=['POST'])
def manual_checkin():
    # 🔒 保護檢查
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    student_id = request.form.get('student_id')
    conn = get_db_connection()
    profile = conn.execute('SELECT device_uuid FROM device_profiles WHERE student_id = ?', (student_id,)).fetchone()
    
    if profile:
        uuid = profile['device_uuid']
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO checkin_logs (device_uuid, status, checkin_time, ip_address, photo_filename)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?)
        ''', (uuid, 'MANUAL', 'Admin Manual', 'manual_checkin.png')) 
        conn.commit()
    
    conn.close()
    return '<script>window.location.href="/admin";</script>'

# ==========================================
# 路由 2.2: 匯出 CSV (✅ 已加入登入保護)
# ==========================================
@app.route('/admin/export_csv')
def export_csv():
    # 🔒 保護檢查：防止有人直接猜網址下載個資
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    target_date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))

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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['學號', '姓名', '房號', '班級', '點名時間', '狀態'])
    
    for row in rows:
        status = "已到" if row['checkin_time'] else "未到"
        if row['status'] == 'MANUAL': status = "人工補點"
        time_str = row['checkin_time'] if row['checkin_time'] else ""
        writer.writerow([row['student_id'], row['name'], row['room_number'], row['class_name'], time_str, status])
    
    output.seek(0)
    filename = f'dorm_report_{target_date.replace("-", "")}.csv'
    return make_response(output.getvalue(), 200, {
        'Content-Disposition': f'attachment; filename={filename}',
        'Content-Type': 'text/csv; charset=utf-8-sig'
    })

# ==========================================
# 路由 3: 提供照片
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
    app.run(debug=True, port=8000)