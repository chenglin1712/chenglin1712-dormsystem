import pandas as pd
import os

# 設定檔案名稱
FILE_NAME = 'data.xlsx'

def read_excel_data():
    if not os.path.exists(FILE_NAME):
        print(f"❌ 找不到檔案：{FILE_NAME}，請確認檔案有在資料夾內。")
        return

    print(f"📂 正在讀取 {FILE_NAME} ...")
    
    # 讀取 Excel (使用 openpyxl 引擎)
    # dtype=str 代表把所有欄位都先當成「文字」讀進來，避免學號開頭的 0 被吃掉
    df = pd.read_excel(FILE_NAME, engine='openpyxl', dtype=str)

    # 簡單統計
    print(f"✅ 讀取成功！總共有 {len(df)} 筆資料。\n")
    print("-" * 50)
    print("🔍 開始測試解析邏輯 (只顯示前 20 筆國專班學生)...")

    count_special = 0

    # 逐行讀取
    for index, row in df.iterrows():
        # 1. 抓取欄位 (使用 .get 避免欄位是空的報錯)
        # 注意：這裡的中文必須跟你的 Excel 表頭一模一樣
        student_id = str(row.get('學號', '')).strip()
        name = str(row.get('姓名', '')).strip()
        gender_raw = str(row.get('姓', '')).strip() # Excel 裡這一欄叫 '姓'
        
        # 2. 過濾無效資料 (例如標題列重複、特殊用途房間)
        if not student_id or student_id == 'nan' or name == '特殊' or '儲藏室' in name:
            continue

        # 3. 判斷國專班
        # 我們把 '學籍', '身分', '註2' 這幾欄串起來檢查
        info_text = str(row.get('學籍', '')) + str(row.get('身分', '')) + str(row.get('註2', ''))
        
        is_special = False
        if '國專班' in info_text:
            is_special = True

        # 4. 判斷性別
        gender = '男'
        if gender_raw == '女':
            gender = '女'

        # 5. 如果是國專班，就印出來檢查
        if is_special:
            count_special += 1
            if count_special <= 20: # 只印前 20 個避免洗版
                print(f"[{count_special}] 國專班發現: {name} ({student_id}) - {gender}")

    print("-" * 50)
    print(f"📊 測試結束。共發現 {count_special} 位國專班學生。")

if __name__ == '__main__':
    read_excel_data()