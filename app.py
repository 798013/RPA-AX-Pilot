import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import time

# ==========================================
# 0. 초기 DB 세팅 및 회원 관리 테이블 추가
# ==========================================
def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    
    # [신규] 회원 관리 마스터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_master (
            user_id TEXT PRIMARY KEY,
            user_pw TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_elements (
            page_name TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS selector_healing_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            log_date TEXT,
            page_name TEXT,
            element_purpose TEXT,
            broken_selector TEXT,
            fixed_selector TEXT,
            status TEXT
        )
    """)
    
    # 테스트용 회원 계정 삽입 (ID: admin / PW: 1234 / 이름: 홍길동 / 이메일: sict@sict.co.kr)
    cursor.execute("""
        INSERT OR IGNORE INTO user_master (user_id, user_pw, user_name, user_email)
        VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')
    """)
    
    # 더미 데이터 채우기
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")
    
    cursor.execute("SELECT COUNT(*) FROM selector_healing_logs")
    if cursor.fetchone() == 0:
        for i in range(1, 151):
            cursor.execute("""
                INSERT INTO selector_healing_logs (user_id, log_date, page_name, element_purpose, broken_selector, fixed_selector, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f"admin", "2026-06-04", "국토부_실거래가" if i%2==0 else "상권정보_포털", 
                  "조회_버튼", f"button#old_id_{i}", f"div.new_class_{i} > button", "AI_추천완료"))
    conn.commit()
    conn.close()

init_db()

# 화면 상태 제어용 세션 초기화 (login, default_error, find_account, main_dashboard)
if "page_state" not in st.session_state:
    st.session_state["page_state"] = "login"

# 로고 이미지 문자열 구워두기 (재사용)
try:
    with open("SICT.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()
    logo_html = f"""
    <div style="display: flex; justify-content: center; align-items: center; width: 100%; margin-bottom: 20px;">
        <img src="data:image/png;base64,{logo_base64}" style="max-width: 250px; width: 50%; height: auto; object-fit: contain;">
    </div>
    """
except:
    logo_html = "<h3 style='text-align: center; color: #1E3A8A;'>🏢 SICT 로고 구역</h3>"

# ==========================================
# [상태 1] 로그인 실패용 Default Page (자동 리다이렉트)
# ==========================================
if st.session_state["page_state"] == "default_error":
    st.set_page_config(page_title="접근 차단됨", layout="centered")
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.error("🚨 [접근 경고] 잘못된 인증 정보입니다. 등록되지 않은 ID이거나 비밀번호가 다릅니다.")
    st.warning("안전을 위해 잠시 후 로그인 페이지로 자동 리다이렉트 처리됩니다...")
    
    # 3초 대기 후 페이지 상태를 복구하고 재실행
    time.sleep(3)
    st.session_state["page_state"] = "login"
    st.rerun()

# ==========================================
# [상태 2] ID / PW 찾기 화면 (DB 검증 연동)
# ==========================================
elif st.session_state["page_state"] == "find_account":
    st.set_page_config(page_title="계정 정보 찾기", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🔐 ID / PW 찾기 센터</h2>", unsafe_allow_html=True)
    st.write("DB에 등록된 사용자의 이름과 이메일을 정확히 입력해 주세요.")
    
    with st.form("find_form"):
        input_name = st.text_input("이름")
        input_email = st.text_input("이메일 주소")
        submit_find = st.form_submit_button("🔍 정보 확인")
        
        if submit_find:
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, user_pw FROM user_master 
                WHERE user_name = ? AND user_email = ?
            """, (input_name, input_email))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                st.success(f"🎯 매칭되는 계정을 찾았습니다!\n* **아이디 (ID)**: `{result[0]}`\n* **비밀번호 (PW)**: `{result[1]}`")
            else:
                st.error("❌ 일치하는 회원 정보가 없습니다. 대소문자와 공백을 확인하세요.")
                
    if st.button("⬅️ 로그인 화면으로 돌아가기"):
        st.session_state["page_state"] = "login"
        st.rerun()

# ==========================================
# [상태 3] 기본 로그인 화면
# ==========================================
elif st.session_state["page_state"] == "login":
    st.set_page_config(page_title="AX-RPA 제어 포털 로그인", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>AX-RPA 관제 시스템 로그인</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)", value="admin")
        user_pw = st.text_input("비밀번호 (Password)", type="password")
        login_btn = st.form_submit_button("로그인")
        
        if login_btn:
            # [DB 연동] ID/PW 일치 여부 쿼리 검증
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_pw FROM user_master WHERE user_id = ?", (user_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result and db_result[0] == user_pw:
                st.session_state["page_state"] = "main_dashboard"
                st.rerun()
            else:
                # 로그인 실패 시 Default 페이지 상태로 이전
                st.session_state["page_state"] = "default_error"
                st.rerun()
                
    # ID/PW 찾기 화면으로 이동하는 트리거 버튼
    if st.button("❓ 아이디 / 비밀번호를 잊으셨나요?"):
        st.session_state["page_state"] = "find_account"
        st.rerun()

# ==========================================
# [상태 4] 메인 관제 대시보드 (로그인 완료 시)
# ==========================================
elif st.session_state["page_state"] == "main_dashboard":
    st.set_page_config(page_title="AX-RPA Selector 관제 콘솔", layout="wide")
    
    col_title, col_logout = st.columns([0.85, 0.15])
    with col_title:
        st.title("🎛️ AX-RPA Selector RAG 제어 포털")
    with col_logout:
        if st.button("로그아웃"):
            st.session_state["page_state"] = "login"
            st.rerun()

    st.markdown("---")
    st.subheader("🔍 Selector 변경 및 로그 조회 조건")
    
    conn = sqlite3.connect("rpa_management.db")
    pages_df = pd.read_sql_query("SELECT page_name FROM page_elements", conn)
    page_options = pages_df["page_name"].tolist()
    conn.close()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        search_id = st.text_input("작업자 ID", value="admin")
    with col2:
        search_date = st.date_input("조회 일자", datetime.now())
    with col3:
        search_page = st.selectbox("대상 Web Page (DB 연동)", options=page_options)
    with col4:
        limit_count = st.selectbox("조회 데이터 제한 (Grid Count)", options=[50, 100, 500], index=0)
    with col5:
        page_num = st.selectbox("페이지 선택 (Pagination)", options=[1, 2, 3], index=0)

    search_submitted = st.button("🚀 조건 조회", type="primary")

    if search_submitted or "current_data" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Selector 매칭 및 치유 이력 (Grid)")
        
        offset_value = limit_count * (page_num - 1)
        
        conn = sqlite3.connect("rpa_management.db")
        query = """
            SELECT log_id, user_id, log_date, page_name, element_purpose, broken_selector, fixed_selector, status
            FROM selector_healing_logs
            WHERE user_id = ? AND page_name = ?
            LIMIT ? OFFSET ?
        """
        df = pd.read_sql_query(query, conn, params=(search_id, search_page, limit_count, offset_value))
        conn.close()

        if not df.empty:
            st.success(f"🎯 {len(df)}건의 데이터를 조회했습니다. (선택된 페이지: {page_num}번 구간)")
            
            towrite = pd.ExcelWriter('rpa_selector_logs.xlsx', engine='xlsxwriter')
            df.to_excel(towrite, index=False, sheet_name='Sheet1')
            towrite.close()
            
            with open('rpa_selector_logs.xlsx', 'rb') as f:
                st.download_button(label="📥 엑셀 내려받기", data=f, file_name=f"RPA_Logs_Page_{page_num}.xlsx", mime="application/vnd.ms-excel")
            
            st.info("💡 정보 수정 안내: 아래 그리드에서 'fixed_selector' 칸을 더블클릭하여 수정 후 아래 버튼을 누르세요.")
            
            edited_df = st.data_editor(
                df, 
                num_rows="dynamic", 
                disabled=["log_id", "user_id", "log_date", "page_name", "element_purpose", "broken_selector"],
                use_container_width=True
            )
            
            if st.button("💾 수정 내용 DB 반영 (Update RAG)"):
                conn = sqlite3.connect("rpa_management.db")
                cursor = conn.cursor()
                
                for index, row in edited_df.iterrows():
                    cursor.execute("""
                        UPDATE selector_healing_logs 
                        SET fixed_selector = ?, status = '정밀보정완료'
                        WHERE log_id = ?
                    """, (row['fixed_selector'], row['log_id']))
                    
                conn.commit()
                conn.close()
                st.toast("🎉 수정 사항이 데이터베이스에 실시간 업데이트되었습니다!", icon="✅")
        else:
            st.warning("조회 조건에 일치하는 데이터가 현재 페이지 구간에 존재하지 않습니다.")
