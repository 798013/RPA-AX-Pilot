import streamlit as st

import pandas as pd

import sqlite3

from datetime import datetime

import base64

import time

import re

import secrets

import requests



def render_header(title):

    # 타이틀(col1)과 버튼들(col2)을 한 줄에 배치

    h1, h2 = st.columns([0.7, 0.3])

    with h1:

        st.subheader(title) # 여기서 타이틀을 한번만 그립니다.

    with h2:

        # 버튼을 최대한 오른쪽으로 정렬

        cols = st.columns([1, 1, 1])

        with cols[0]:

            if st.button("⬅️", help="뒤로가기"):

                st.session_state["page_state"] = "main_dashboard"

                st.rerun()

        with cols[1]:

            if st.button("⚙️", help="설정"):

                st.session_state["page_state"] = "change_password"

                st.rerun()

        with cols[2]:

            if st.button("🚪", help="로그아웃"):

                for key in list(st.session_state.keys()):

                    del st.session_state[key]

                st.session_state["page_state"] = "login"

                st.rerun()

    st.divider() # 구분선은 여기서 한 번만 나옵니다.

    

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

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS system_config (

            config_key TEXT PRIMARY KEY, config_value TEXT

        )

    """)

    cursor.execute("INSERT OR IGNORE INTO user_master VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')")

    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")

    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")

    

    # 💡 기본 감시 데이터가 비어있을 경우에만 최초 1회 자동 생성 프로시저 가동

    cursor.execute("SELECT COUNT(*) FROM selector_healing_logs")

    if cursor.fetchone()[0] == 0:

        for i in range(1, 151):

            cursor.execute("""

                INSERT INTO selector_healing_logs (user_id, log_date, page_name, element_purpose, broken_selector, fixed_selector, status)

                VALUES (?, ?, ?, ?, ?, ?, ?)

            """, ("admin", "2026-06-04", "국토부_실거래가" if i%2==0 else "상권정보_포털", "조회_버튼", f"button#old_id_{i}", f"div.new_class_{i} > button", "AI_추천완료"))

            

    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('SMTP_SERVER', '://gmail.com')")

    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('SMTP_PORT', '587')")

    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('DB_PATH', 'rpa_management.db')")

    cursor.execute("INSERT OR IGNORE INTO system_config VALUES ('EMAIL_API_KEY', 'mqkrwdrn')")

    conn.commit()

    conn.close()



init_db()



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

                st.error("⚠️ 모든 칸을 정확하게 입력해 주세요.")

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



# --- 화면 5: 메인 관제 대시보드 ---

elif st.session_state["page_state"] == "main_dashboard":

    st.set_page_config(page_title="AX-RPA Selector 관제 콘솔", layout="wide")

    render_header("등록 내역 검색")

    

# --- 메인 : 설정 ---

elif st.session_state["page_state"] == "change_password":

    render_header("비밀번호 변경")

    

    # 1. 디자인: 중앙에 좁은 컨테이너 배치 (가로폭을 좁혀 비대칭 해결)

    col_center, _ = st.columns([0.5, 0.5]) 

    with col_center:

        st.markdown("#### 🔑 비밀번호 변경")

        

        with st.form("pw_change_form"):

            # 입력창 간격 조절

            old_pw = st.text_input("현재 비밀번호", type="password")

            new_pw = st.text_input("새 비밀번호", type="password")

            confirm_pw = st.text_input("새 비밀번호 확인", type="password")

            

            # 버튼 크기를 줄이고 색상을 정돈

            submit = st.form_submit_button("변경하기", type="primary")

            

            if submit:

                if not old_pw or not new_pw:

                    st.warning("모든 항목을 입력하세요.")

                elif new_pw != confirm_pw:

                    st.error("새 비밀번호가 일치하지 않습니다.")

                else:

                    # DB 로직 (기존과 동일)

                    conn = sqlite3.connect("rpa_management.db")

                    cursor = conn.cursor()

                    cursor.execute("UPDATE user_master SET user_pw = ? WHERE user_id = ? AND user_pw = ?", 

                                   (new_pw, st.session_state["current_user"], old_pw))

                    

                    if cursor.rowcount > 0:

                        conn.commit()

                        st.success("변경 완료!")

                    else:

                        st.error("현재 비밀번호가 일치하지 않습니다.")

                    conn.close()
