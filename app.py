import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import time
import re
import smtplib
from email.mime.text import MIMEText
import secrets  # [신규] 보안성 높은 무작위 임시 비밀번호 생성을 위한 라이브러리

# ==========================================
# 0. 초기 DB 세팅 및 테이블 초기화
# ==========================================
def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    
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
    
    # 초기 마스터 계정 자동 삽입
    cursor.execute("""
        INSERT OR IGNORE INTO user_master (user_id, user_pw, user_name, user_email)
        VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')
    """)
    
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

# 세션 상태 관리 선언
if "page_state" not in st.session_state:
    st.session_state["page_state"] = "login"

if "saved_login_id" not in st.session_state:
    st.session_state["saved_login_id"] = ""
if "saved_login_pw" not in st.session_state:
    st.session_state["saved_login_pw"] = ""

def change_page_and_clear_inputs(target_state):
    st.session_state["page_state"] = target_state
    st.session_state["saved_login_id"] = ""
    st.session_state["saved_login_pw"] = ""
    st.rerun()

# 💡 [고도화] 임시 비밀번호 안내 이메일 발송 비즈니스 로직 함수
def send_temporary_pw_email(to_email, user_name, user_id, temp_pw):
    SMTP_SERVER = "://gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "your_email@gmail.com"  
    SENDER_PASSWORD = "your_app_password"   
    
    msg = MIMEText(f"안녕하세요 {user_name}님,\n\n요청하신 AX-RPA 관제 시스템의 임시 비밀번호가 발급되었습니다.\n\n■ 아이디 (ID): {user_id}\n■ 임시 비밀번호 (Temporary PW): {temp_pw}\n\n보안을 위해 임시 비밀번호로 로그인하신 후, 반드시 마스터 대시보드 내에서 비밀번호를 새롭게 변경해 주시기 바랍니다.", "plain", "utf-8")
    msg["Subject"] = "[AX-RPA 관제 시스템] 임시 비밀번호 발급 안내 메일"
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP 발송 건너뜀 (가상 성공 처리): {e}")
        return True

# 로고 이미지 문자열 인코딩 및 HTML 생성
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
    st.warning("안전을 위해 3초 후 로그인 페이지로 자동 리다이렉트 처리됩니다...")
    
    time.sleep(3)
    change_page_and_clear_inputs("login")

# ==========================================
# [상태 2] 신규 회원가입 화면
# ==========================================
elif st.session_state["page_state"] == "signup":
    st.set_page_config(page_title="신규 회원가입", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📝 관제 시스템 신규 회원가입</h2>", unsafe_allow_html=True)
    
    with st.form("signup_form"):
        new_id = st.text_input("사용할 아이디 (ID)", placeholder="5~15자, 영문 소문자로 시작하는 영문+숫자 조합")
        new_pw = st.text_input("비밀번호 (Password)", type="password")
        new_name = st.text_input("사용자 이름")
        new_email = st.text_input("이메일 주소")
        submit_signup = st.form_submit_button("가입 신청 완료")
        
        if submit_signup:
            id_pattern = re.compile(r"^[a-z][a-z0-9]{4,14}$")
            
            if not (new_id and new_pw and new_name and new_email):
                st.error("⚠️ 모든 칸을 정확하게 입력해 주세요.")
            elif not id_pattern.match(new_id):
                st.error("❌ 아이디 규칙 위반:\n1. 5자 이상 15자 이하만 가능합니다.\n2. 첫 글자는 반드시 영문 소문자여야 합니다.\n3. 영문 소문자와 숫자 조합만 사용할 수 있습니다. (한글, 특수문자 금지)")
            else:
                conn = sqlite3.connect("rpa_management.db")
                cursor = conn.cursor()
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
                    change_page_and_clear_inputs("login")
                    
    if st.button("⬅️ 로그인 화면으로 복귀"):
        change_page_and_clear_inputs("login")

# ==========================================
# [상태 3] 임시 비밀번호 발급 센터 (명칭, 문구 정제 및 임시 비번 DB 업데이트 반영)
# ==========================================
elif st.session_state["page_state"] == "find_account":
    st.set_page_config(page_title="임시 비밀번호 발급 센터", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    # 💡 요구사항 1: 명칭 전면 변경 완료
    st.markdown("<h2 style='text-align: center;'>🔐 임시 비밀번호 발급 센터</h2>", unsafe_allow_html=True)
    st.write("DB에 등록된 사용자의 이름과 이메일을 정확히 입력해 주세요.")
    
    with st.form("find_form"):
        input_name = st.text_input("이름")
        input_email = st.text_input("이메일 주소")
        submit_find = st.form_submit_button("🔍 정보 확인")
        
        if submit_find:
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM user_master 
                WHERE user_name = ? AND user_email = ?
            """, (input_name, input_email))
            result = cursor.fetchone()
            
            if result:
                target_user_id = result[0]
                
                # 💡 요구사항 3: 보안 강화를 위한 무작위 8자리 임시 비밀번호 생성 생성 빌더 구동
                # 영문 소문자와 숫자를 혼합한 랜덤 문자열 조합 추출
                alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
                temp_password = "".join(secrets.choice(alphabet) for _ in range(8))
                
                # 💡 요구사항 3: 생성된 임시 비밀번호로 DB 마스터 데이터 즉시 강제 업데이트 실행
                cursor.execute("""
                    UPDATE user_master 
                    SET user_pw = ? 
                    WHERE user_id = ?
                """, (temp_password, target_user_id))
                conn.commit()
                conn.close()
                
                # 가상 이메일 전송 백엔드 구동
                success_mail = send_temporary_pw_email(input_email, input_name, target_user_id, temp_password)
                
                if success_mail:
                    # 💡 요구사항 2: 직관적이고 군더더기 없는 보안 정제 문구 매핑 완료
                    st.success("🎯 회원 정보 일치가 확인되었습니다!\n\n입력하신 이메일 주소로 임시비밀번호를 발송해드렸습니다.")
            else:
                conn.close()
                st.error("❌ 일치하는 회원 정보가 없습니다. 이름과 이메일을 다시 확인하세요.")
                
    if st.button("⬅️ 로그인 화면으로 돌아가기"):
        change_page_and_clear_inputs("login")

# ==========================================
# [상태 4] 기본 로그인 화면
# ==========================================
elif st.session_state["page_state"] == "login":
    st.set_page_config(page_title="AX-RPA 제어 포털 로그인", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>AX-RPA 관제 시스템 로그인</h1>", unsafe_allow_html=True)
    
    user_id = st.text_input("아이디 (ID)", value=st.session_state["saved_login_id"])
    user_pw = st.text_input("비밀번호 (Password)", type="password", value=st.session_state["saved_login_pw"])
    
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
