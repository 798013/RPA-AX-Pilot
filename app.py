import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import time
import re
import secrets
import requests

# ==========================================
# 0. 데이터베이스(SQLite) 인프라 초기화
# ==========================================
def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_master (
            user_id TEXT PRIMARY KEY, user_pw TEXT NOT NULL, user_name TEXT NOT NULL, user_email TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS page_elements (page_name TEXT UNIQUE)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS selector_healing_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, log_date TEXT, page_name TEXT, 
            element_purpose TEXT, broken_selector TEXT, fixed_selector TEXT, status TEXT
        )
    """)
    # 💡 [고도화 2] 인프라 환경설정 정보를 영구 저장할 시스템 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            config_key TEXT PRIMARY KEY, config_value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO user_master VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")
    
    # 💡 [어드민 기본값 세팅] SMTP 및 DB 기본 접속 정보를 안전하게 인서트
    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('SMTP_SERVER', '://gmail.com')")
    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('SMTP_PORT', '587')")
    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('DB_PATH', 'rpa_management.db')")
    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('EMAIL_API_KEY', 'mqkrwdrn')")
    conn.commit()
    conn.close()

init_db()

# 💡 요구사항 1번: 150건의 지저분한 Default 더미 데이터를 생성하던 강제 삽입 로직을 완벽히 삭제했습니다.
# 이제 시스템 구동 시 첫 화면이 깨끗하게 유지됩니다.

if "page_state" not in st.session_state:
    st.session_state["page_state"] = "login"
if "login_id_key" not in st.session_state:
    st.session_state["login_id_key"] = 0
if "login_pw_key" not in st.session_state:
    st.session_state["login_pw_key"] = 1000
if "current_user" not in st.session_state:
    st.session_state["current_user"] = ""

def change_page_and_clear_inputs(target_state):
    st.session_state["page_state"] = target_state
    st.session_state["login_id_key"] += 1
    st.session_state["login_pw_key"] += 1
    st.rerun()

def send_temporary_pw_email_api(to_email, user_name, user_id, temp_pw):
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'EMAIL_API_KEY'")
    api_key = cursor.fetchone()[0]
    conn.close()
    
    FORMSPREE_URL = f"https://formspree.io{api_key}" 
    email_data = {
        "작업 대상자 이름": user_name, "알림 수신 이메일": to_email, "발급된 아이디 (ID)": user_id, "임시 비밀번호": temp_pw,
        "message": f"AX-RPA 인증: {user_name}님의 계정 임시 비밀번호는 [{temp_pw}] 입니다."
    }
    try:
        response = requests.post(FORMSPREE_URL, json=email_data)
        return response.status_code == 200
    except:
        return False

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

# --- 화면 1: 에러 리다이렉트 ---
if st.session_state["page_state"] == "default_error":
    st.set_page_config(page_title="접근 차단됨", layout="centered")
    st.error("🚨 [접근 경고] 잘못된 인증 정보입니다. 등록되지 않은 ID이거나 비밀번호가 다릅니다.")
    st.warning("안전을 위해 3초 후 로그인 페이지로 자동 리다이렉트 처리됩니다...")
    time.sleep(3)
    change_page_and_clear_inputs("login")

# --- 화면 2: 신규 회원가입 ---
elif st.session_state["page_state"] == "signup":
    st.set_page_config(page_title="신규 회원가입", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📝 관제 시스템 신규 회원가입</h2>", unsafe_allow_html=True)
    
    with st.form("signup_form"):
        new_id = st.text_input("사용할 아이디 (ID)", placeholder="5~15자, 영문 소문자로 시작하는 영문+숫자 조합")
        new_pw = st.text_input("비밀번호 (Password)", type="password")
        new_name = st.text_input("사용자 이름")
        new_email = st.text_input("이메일 주소 (필수 입력)", placeholder="example@sictglobal.com")
        submit_signup = st.form_submit_button("가입 신청 완료")
        
        if submit_signup:
            id_pattern = re.compile(r"^[a-z][a-z0-9]{4,14}$")
            email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
            
            if not (new_id and new_pw and new_name and new_email):
                st.error("⚠️ 모든 칸을 정확하게 입력해 주세요. (이메일 주소는 필수 항목입니다.)")
            elif not id_pattern.match(new_id):
                st.error("❌ 아이디 규칙 위반: 5~15자 영문 소문자 시작, 영문 소문자+숫자 조합만 가능.")
            elif not email_pattern.match(new_email):
                st.error("❌ 이메일 형식 오류: 올바른 이메일 규격으로 다시 입력해 주세요.")
            else:
                conn = sqlite3.connect("rpa_management.db")
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM user_master WHERE user_id = ?", (new_id,))
                if cursor.fetchone():
                    st.error("❌ 이미 존재하는 아이디입니다. 다른 아이디를 입력하세요.")
                    conn.close()
                else:
                    cursor.execute("INSERT INTO user_master VALUES (?, ?, ?, ?)", (new_id, new_pw, new_name, new_email))
                    conn.commit()
                    conn.close()
                    st.success("🎉 회원가입이 정상적으로 완료되었습니다! 로그인 페이지로 이동합니다.")
                    time.sleep(1.5)
                    change_page_and_clear_inputs("login")
                    
    if st.button("⬅️ 로그인 화면으로 복귀"):
        change_page_and_clear_inputs("login")

# --- 화면 3: ID / PW 찾기 ---
elif st.session_state["page_state"] == "find_account":
    st.set_page_config(page_title="ID / PW 찾기", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🔐 ID / PW 찾기</h2>", unsafe_allow_html=True)
    
    with st.form("find_form"):
        input_id = st.text_input("아이디 (ID)")
        input_email = st.text_input("이메일 주소")
        submit_find = st.form_submit_button("🔍 정보 확인")
        
        if submit_find:
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, user_name FROM user_master WHERE user_id = ? AND user_email = ?", (input_id, input_email))
            result = cursor.fetchone()
            
            if result:
                target_user_id = result[0]
                target_user_name = result[1]
                alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
                temp_password = "".join(secrets.choice(alphabet) for _ in range(8))
                
                cursor.execute("UPDATE user_master SET user_pw = ? WHERE user_id = ?", (temp_password, target_user_id))
                conn.commit()
                conn.close()
                
                send_temporary_pw_email_api(input_email, target_user_name, target_user_id, temp_password)
                st.success("🎯 회원 정보 일치가 확인되었습니다!\n\n입력하신 이메일 주소로 임시비밀번호를 발송해드렸습니다.")
                with st.expander("💡 [테스트 안내] 메일이 차단되거나 지연될 경우 확인용"):
                    st.info(f"현재 계정의 비밀번호가 DB상에서 **`{temp_password}`**로 실시간 즉시 업데이트되었습니다. 이 값으로 로그인 테스트를 진행하세요.")
            else:
                conn.close()
                st.error("❌ 일치하는 회원 정보가 없습니다. 아이디와 이메일을 다시 확인하세요.")
                
    if st.button("⬅️ 로그인 화면으로 돌아가기"):
        change_page_and_clear_inputs("login")

# --- 화면 4: 기본 로그인 화면 ---
elif st.session_state["page_state"] == "login":
    st.set_page_config(page_title="AX-RPA 제어 포털 로그인", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>AX-RPA 관제 시스템 로그인</h1>", unsafe_allow_html=True)
    
    user_id = st.text_input("아이디 (ID)", key=f"id_input_{st.session_state['login_id_key']}")
    user_pw = st.text_input("비밀번호 (Password)", type="password", key=f"pw_input_{st.session_state['login_pw_key']}")
    
    st.write("")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        if st.button("ID / PW 찾기", use_container_width=True):
            change_page_and_clear_inputs("find_account")
    with col_nav2:
        if st.button("회원 가입", use_container_width=True):
            change_page_and_clear_inputs("signup")
    with col_nav3:
        if st.button("로그인", type="primary", use_container_width=True):
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_pw FROM user_master WHERE user_id = ?", (user_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result and db_result[0] == user_pw:
                st.session_state["page_state"] = "main_dashboard"
                st.session_state["current_user"] = user_id
                st.rerun()
            else:
                st.session_state["page_state"] = "default_error"
                st.rerun()

# --- 화면 5: 메인 관제 대시보드 (어드민 환경설정 연동 버전) ---
elif st.session_state["page_state"] == "main_dashboard":
    st.set_page_config(page_title="AX-RPA Selector 관제 콘솔", layout="wide")
    
    # 💡 [고도화 2] 오직 최고 관리자(admin) 계정으로 접근했을 때만 사이드바에 어드민 설정 메뉴 오픈
    admin_menu = "📊 메인 관제 콘솔"
    if st.session_state["current_user"] == "admin":
        admin_menu = st.sidebar.radio("⚙️ 마스터 시스템 관리", ["📊 메인 관제 콘솔", "🛠️ 인프라 환경설정 (Admin)"])

    # ----------------------------------------
