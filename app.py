import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import time

# ==========================================
# 0. 데이터베이스(SQLite) 및 테이블 초기화
# ==========================================
def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    
    # 회원 관리 마스터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_master (
            user_id TEXT PRIMARY KEY,
            user_pw TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL
        )
    """)
    
    # 감시 대상 웹페이지 관리 마스터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_elements (
            page_name TEXT UNIQUE
        )
    """)
    
    # AI 치유 이력 및 RAG 캐시 테이블
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
    
    # 초기 파일럿용 테스트 마스터 계정 자동 삽입 (ID: admin / PW: 1234)
    cursor.execute("""
        INSERT OR IGNORE INTO user_master (user_id, user_pw, user_name, user_email)
        VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')
    """)
    
    # 콤보박스 연동용 기본 가상 웹페이지 정보 채우기
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")
    
    # 페이징 알고리즘 작동 검증을 위한 대량의 더미 로그 생성 (150건)
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

# 애플리케이션 시작 시 DB 초기화 작동
init_db()

# 웹페이지 화면 흐름 제어용 세션 상태 정의 (기본값: login)
if "page_state" not in st.session_state:
    st.session_state["page_state"] = "login"

# SICT 로고 이미지 로드 및 Base64 인코딩 주입 (보안 및 반응형 중앙 정렬 보장)
try:
    with open("SICT.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()
    logo_html = f"""
    <div style="display: flex; justify-content: center; align-items: center; width: 100%; margin-bottom: 20px;">
        <img src="data:image/png;base64,{logo_base64}" style="max-width: 250px; width: 50%; height: auto; object-fit: contain;">
    </div>
    """
except:
    logo_html = "<h3 style='text-align: center; color: #1E3A8A;'>🏢 SICT 로고 구역 (SICT.png 파일 없음)</h3>"

# ==========================================
# [상태 1] 로그인 실패용 Default Page (경고 후 자동 리다이렉트)
# ==========================================
if st.session_state["page_state"] == "default_error":
    st.set_page_config(page_title="접근 차단됨", layout="centered")
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.error("🚨 [접근 경고] 잘못된 인증 정보입니다. 등록되지 않은 ID이거나 비밀번호가 다릅니다.")
    st.warning("안전을 위해 3초 후 로그인 페이지로 자동 리다이렉트 처리됩니다...")
    
    time.sleep(3)
    st.session_state["page_state"] = "login"
    st.rerun()

# ==========================================
# [상태 2] 신규 회원가입 화면 (ID 중복 체크 및 DB 저장)
# ==========================================
elif st.session_state["page_state"] == "signup":
    st.set_page_config(page_title="신규 회원가입", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📝 관제 시스템 신규 회원가입</h2>", unsafe_allow_html=True)
    
    with st.form("signup_form"):
        new_id = st.text_input("사용할 아이디 (ID)", placeholder="영문, 숫자 조합")
        new_pw = st.text_input("비밀번호 (Password)", type="password")
        new_name = st.text_input("사용자 이름")
        new_email = st.text_input("이메일 주소")
        submit_signup = st.form_submit_button("가입 신청 완료")
        
        if submit_signup:
            if not (new_id and new_pw and new_name and new_email):
                st.error("⚠️ 모든 칸을 정확하게 입력해 주세요.")
            else:
                conn = sqlite3.connect("rpa_management.db")
                cursor = conn.cursor()
                
                # 아이디 중복 체크 검증
                cursor.execute("SELECT user_id FROM user_master WHERE user_id = ?", (new_id,))
                if cursor.fetchone():
                    st.error("❌ 이미 존재하는 아이디입니다. 다른 아이디를 입력하세요.")
                    conn.close()
                else:
                    cursor.execute("""
                        INSERT INTO user_master (user_id, user_pw, user_name, user_email)
                        VALUES (?, ?, ?, ?)
                    """, (new_id, new_pw, new_name, new_email))
                    conn.commit()
                    conn.close()
                    st.success("🎉 회원가입이 정상적으로 완료되었습니다! 로그인 페이지로 이동합니다.")
                    time.sleep(1.5)
                    st.session_state["page_state"] = "login"
                    st.rerun()
                    
    if st.button("⬅️ 로그인 화면으로 복귀"):
        st.session_state["page_state"] = "login"
        st.rerun()

# ==========================================
# [상태 3] ID / PW 찾기 화면 (이름, 이메일 기준 DB 조회)
# ==========================================
elif st.session_state["page_state"] == "find_account":
    st.set_page_config(page_title="계정 정보 찾기", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🔐 ID / PW 찾기 센터</h2>", unsafe_allow_html=True)
    
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
                st.success(f"🎯 계정을 찾았습니다!\n* **아이디 (ID)**: `{result[0]}`\n* **비밀번호 (PW)**: `{result[1]}`")
            else:
                st.error("❌ 일치하는 회원 정보가 없습니다.")
                
    if st.button("⬅️ 로그인 화면으로 돌아가기"):
        st.session_state["page_state"] = "login"
        st.rerun()

# ==========================================
# [상태 4] 반응형 3버튼 로그인 화면 (메인 엔트리)
# ==========================================
elif st.session_state["page_state"] == "login":
    st.set_page_config(page_title="AX-RPA 제어 포털 로그인", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>AX-RPA 관제 시스템 로그인</h1>", unsafe_allow_html=True)
    
    # 입력 정보 캡처를 위해 인풋 컨테이너 단독 생성
    user_id = st.text_input("아이디 (ID)", value="admin")
    user_pw = st.text_input("비밀번호 (Password)", type="password")
    
    st.write("") # 마진 공백용
    
    # 🎨 [반응형 최적화] 하단 3개 버튼을 3분할 열로 가로 배치하며 use_container_width 적용
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        if st.button("ID / PW 찾기", use_container_width=True):
            st.session_state["page_state"] = "find_account"
            st.rerun()
    with col_nav2:
        if st.button("회원 가입", use_container_width=True):
            st.session_state["page_state"] = "signup"
            st.rerun()
    with col_nav3:
        if st.button("로그인", type="primary", use_container_width=True):
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_pw FROM user_master WHERE user_id = ?", (user_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result and db_result[0] == user_pw:
                st.session_state["page_state"] = "main_dashboard"
                st.rerun()
            else:
                st.session_state["page_state"] = "default_error"
                st.rerun()

# ==========================================
# [상태 5] 메인 관제 대시보드 (로그인 완료 시 오픈)
# ==========================================
elif st.session_state["page_state"] == "main_dashboard":
    st.set_page_config(page_title="AX-RPA Selector 관제 콘솔", layout="wide")
    
    col_title, col_logout = st.columns([0.85, 0.15])
    with col_title:
        st.title("🎛️ AX-RPA Selector RAG 제어 포털")
    with col_logout:
        if st.button("로그아웃", use_container_width=True):
            st.session_state["page_state"] = "login"
            st.rerun()

    st.markdown("---")
    st.subheader("🔍 Selector 변경 및 로그 조회 조건")
    
    # DB에서 실시간 웹페이지 목록을 조회하여 콤보박스에 바인딩
    conn = sqlite3.connect("rpa_management.db")
    pages_df = pd.read_sql_query("SELECT page_name FROM page_elements", conn)
    page_options = pages_df["page_name"].tolist()
    conn.close()

    # 상단 5분할 조건 제어 그리드 배치
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
        
        # SQL 오프셋(OFFSET) 페이징 연산 적용
        offset_value = limit_count * (page_num - 1)
        
