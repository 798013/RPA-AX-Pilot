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
    
    # 초기 테스트 마스터 계정 자동 삽입 (ID: admin / PW: 1234)
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

if "saved_login_id" not in st.session_state:
    st.session_state["saved_login_id"] = ""
if "saved_login_pw" not in st.session_state:
    st.session_state["saved_login_pw"] = ""

# 화면 전환 시 입력폼 데이터를 완전히 비워버리는 함수
def change_page_and_clear_inputs(target_state):
    st.session_state["page_state"] = target_state
    st.session_state["saved_login_id"] = ""
    st.session_state["saved_login_pw"] = ""
    st.rerun()

# Formspree API를 이용한 이메일 전송 함수
def send_temporary_pw_email_api(to_email, user_name, user_id, temp_pw):
    FORMSPREE_URL = "https://formspree.io" 
    
    email_data = {
        "작업 대상자 이름": user_name,
        "알림 수신 이메일": to_email,
        "발급된 아이디 (ID)": user_id,
        "새로운 임시 비밀번호 (Temporary PW)": temp_pw,
        "message": f"AX-RPA 시스템 인증 안내: {user_name}님의 계정({user_id}) 임시 비밀번호는 [{temp_pw}] 입니다. 로그인 후 즉시 변경하세요."
    }
    
    try:
        response = requests.post(FORMSPREE_URL, json=email_data)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

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
# [상태 1] 로그인 실패용 Default Page
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
        new_email = st.text_input("이메일 주소 (필수 입력)", placeholder="example@sictglobal.com")
        submit_signup = st.form_submit_button("가입 신청 완료")
        
        if submit_signup:
            id_pattern = re.compile(r"^[a-z][a-z0-9]{4,14}$")
            email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
            
            if not (new_id and new_pw and new_name and new_email):
                st.error("⚠️ 모든 칸을 정확하게 입력해 주세요. (이메일 주소는 필수 항목입니다.)")
            elif not id_pattern.match(new_id):
                st.error("❌ 아이디 규칙 위반:\n1. 5자 이상 15자 이하만 가능합니다.\n2. 첫 글자는 반드시 영문 소문자여야 합니다.\n3. 영문 소문자와 숫자 조합만 사용할 수 있습니다. (한글, 특수문자 금지)")
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
# [상태 3] ID / PW 찾기 화면 (ID 기준 전면 변경 및 튜플 디코딩 반영)
# ==========================================
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
            cursor.execute("""
                SELECT user_id, user_name FROM user_master 
                WHERE user_id = ? AND user_email = ?
            """, (input_id, input_email))
            result = cursor.fetchone()
            
            if result:
                # 💡 튜플 구조 분해로 문자열 데이터 추출 에러 원천 차단
                target_user_id = result
                target_user_name = result
                
                alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
                temp_password = "".join(secrets.choice(alphabet) for _ in range(8))
                
                cursor.execute("""
                    UPDATE user_master 
                    SET user_pw = ? 
                    WHERE user_id = ?
                """, (temp_password, target_user_id))
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
        # 💡 [보정 핵심] 이 아래의 모든 실행 로직 라인을 if문 내부 및 with문 내부 구조에 맞춰 일괄 밀어넣음
        if st.button("로그인", type="primary", use_container_width=True):
            conn = sqlite3.connect("rpa_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_pw FROM user_master WHERE user_id = ?", (user_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result and db_result == user_pw:
                st.session_state["page_state"] = "main_dashboard"
                st.rerun()
            else:
                st.session_state["page_state"] = "default_error"
                st.rerun()
