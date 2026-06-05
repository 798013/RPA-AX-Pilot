import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import time
import re
import secrets
import requests

def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_master (
            user_id TEXT PRIMARY KEY,
            user_pw TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            is_admin TEXT DEFAULT 'N',
            force_pw_change TEXT DEFAULT 'N',
            created_at TEXT
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
    cursor.execute("INSERT OR IGNORE INTO user_master VALUES ('admin','1234','홍길동','sict@sict.co.kr','Y','N',datetime('now'))")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")

    # ai_analysis_logs 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_logs (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER,
            recommended_selector TEXT,
            analysis_reason TEXT,
            created_at TEXT
        )
    """)

    # element_context 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS element_context (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_name TEXT,
        element_purpose TEXT,
        selector TEXT,
        selector_type TEXT,
        element_text TEXT,
        dom_path TEXT,
        outer_html TEXT,
        success_count INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
                   
    # 더미 데이터 생성
    cursor.execute("""
    INSERT OR IGNORE INTO element_context
    (
        page_name,
        element_purpose,
        selector,
        selector_type,
        element_text,
        dom_path,
        outer_html,
        success_count,
        created_at
    )
    VALUES
    (
        '국토부_실거래가',
        '조회버튼',
        'button.search',
        'CSS',
        '조회',
        '/html/body/div/button',
        '<button>조회</button>',
        15,
        datetime('now')
    )
    """)
    
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
                    cursor.execute("""
                        INSERT INTO user_master
                        (
                        user_id,
                        user_pw,
                        user_name,
                        user_email,
                        is_admin,
                        force_pw_change,
                        created_at
                        )
                        VALUES
                        (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                        )
                        """,
                        (
                        new_id,
                        new_pw,
                        new_name,
                        new_email,
                        "N",
                        "N",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )
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
            cursor.execute("""SELECT user_pw,is_admin,force_pw_change FROM user_master WHERE user_id = ?""", (user_id,))
            db_result = cursor.fetchone()
            conn.close()
            
            if db_result and db_result[0] == user_pw:
                st.session_state["is_admin"] = db_result[1]

                if db_result[2] == "Y":
                    st.session_state["page_state"] = "change_password"
                    st.rerun()
                st.session_state["page_state"] = "main_dashboard"
                st.session_state["current_user"] = user_id
                st.rerun()
            else:
                st.session_state["page_state"] = "default_error"
                st.rerun()


# --- 화면 5: 메인 관제 대시보드 ---
elif st.session_state["page_state"] == "main_dashboard":

    st.set_page_config(
        page_title="AX-RPA Selector 관제 콘솔",
        layout="wide"
    )

    st.title("🤖 AX-RPA Selector 관제 콘솔")

    with st.sidebar:
        st.success(f"사용자 : {st.session_state['current_user']}")
        
        # 1. 권한 확인 (로그인 시 is_admin 정보가 세션에 있다고 가정)
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        
        # 2. 메뉴 리스트 정의
        menu_options = ["Dashboard", "Healing 이력", "Healing Monitor", "Knowledge DB", "AI Analysis Log"]
        
        # 3. 관리자 전용 메뉴 추가
        if is_admin:
            menu_options.extend(["사용자 관리", "페이지 관리", "시스템 설정"])
            
        menu_options.extend(["비밀번호 변경", "로그아웃"])
        
        # 4. 라디오 버튼 생성
        menu = st.radio("메뉴 선택", menu_options)

    conn = sqlite3.connect("rpa_management.db")

    if menu == "Dashboard":

        page_count = pd.read_sql(
            "SELECT COUNT(*) cnt FROM page_elements",
            conn
        )["cnt"][0]

        log_count = pd.read_sql(
            "SELECT COUNT(*) cnt FROM selector_healing_logs",
            conn
        )["cnt"][0]

        success_count = pd.read_sql(
            "SELECT COUNT(*) cnt FROM selector_healing_logs WHERE status='AI_추천완료'",
            conn
        )["cnt"][0]

        user_count = pd.read_sql(
            "SELECT COUNT(*) cnt FROM user_master",
            conn
        )["cnt"][0]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("등록 페이지", page_count)
        c2.metric("Healing 건수", log_count)
        c3.metric("성공 건수", success_count)
        c4.metric("사용자 수", user_count)

        st.divider()

        st.subheader("최근 Healing 이력")

        df = pd.read_sql("""
            SELECT log_date,page_name,broken_selector,fixed_selector,status
            FROM selector_healing_logs
            ORDER BY log_id DESC
            LIMIT 20
        """, conn)

        st.dataframe(df, use_container_width=True)

    # Knowledge DB 메뉴 추가
    elif menu == "Knowledge DB":

        st.subheader("Selector Knowledge DB")
    
        # 1. 권한 및 사용자 데이터 가져오기
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        current_user = st.session_state.get("current_user", "")
        
        # 관리자일 경우 사용자 목록 전체 가져오기
        if is_admin:
            users_df = pd.read_sql("SELECT user_id FROM user_master", conn)
            user_list = ["전체"] + users_df["user_id"].tolist()
        else:
            user_list = [current_user]

        # 2. 조회 필터 배치 (5개 컬럼 정렬)
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        with col1: search_date = st.date_input("날짜 선택", value=None)
        with col2: 
            pages = pd.read_sql("SELECT page_name FROM page_elements", conn)["page_name"].tolist()
            search_page = st.selectbox("페이지 선택", ["전체"] + pages)
        with col3: search_user = st.selectbox("사용자 ID", user_list, disabled=(not is_admin))
        with col4: page_size = st.selectbox("건수", [50, 100, 150], index=0)
        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            search_btn = st.button("조회", use_container_width=True)

        # 3. SQL 동적 구성
        query = "SELECT * FROM element_context WHERE 1=1"
        params = []
        if search_date:
            query += " AND log_date LIKE ?"
            params.append(f"{search_date}%")
        if search_page != "전체":
            query += " AND page_name = ?"
            params.append(search_page)
        if is_admin and search_user != "전체":
            query += " AND user_id = ?"
            params.append(search_user)
        elif not is_admin:
            query += " AND user_id = ?"
            params.append(current_user)
            
        # 전체 데이터 조회
        full_df = pd.read_sql(query + " ORDER BY 1 DESC", conn, params=params)

        # 4. 결과 처리 (페이징 반영)
        if full_df.empty:
            st.warning("🔍 조회된 Healing 이력이 없습니다.")
            st.button("📥 엑셀 다운로드", disabled=True)
        else:
            # 화면에는 설정한 page_size만큼만 보여줌
            display_df = full_df.head(page_size)
            
            st.success(f"총 {len(full_df)}건 중 상위 {len(display_df)}건을 표시합니다.")
            st.dataframe(display_df, use_container_width=True)
            
            # 5. 엑셀 다운로드 (전체 내역)
            import io
            buffer = io.BytesIO()
            full_df.to_excel(buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 엑셀 다운로드 (전체 내역)",
                data=buffer.getvalue(),
                file_name="healing_logs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # 사용자 관리 메뉴 추가
    elif menu == "사용자 관리":

        st.subheader("사용자 관리")
    
        user_df = pd.read_sql("""
            SELECT
            user_id,
            user_name,
            user_email,
            is_admin,
            created_at
            FROM user_master
        """, conn)
    
        st.dataframe(
            user_df,
            use_container_width=True
        )

    # AI Analysis Log
    elif menu == "AI Analysis Log":

        st.subheader("AI Analysis Log")
    
        # 1. 권한 및 사용자 데이터 가져오기
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        current_user = st.session_state.get("current_user", "")
        
        # 관리자일 경우 사용자 목록 전체 가져오기
        if is_admin:
            users_df = pd.read_sql("SELECT user_id FROM user_master", conn)
            user_list = ["전체"] + users_df["user_id"].tolist()
        else:
            user_list = [current_user]

        # 2. 조회 필터 배치 (5개 컬럼 정렬)
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        with col1: search_date = st.date_input("날짜 선택", value=None)
        with col2: 
            pages = pd.read_sql("SELECT page_name FROM page_elements", conn)["page_name"].tolist()
            search_page = st.selectbox("페이지 선택", ["전체"] + pages)
        with col3: search_user = st.selectbox("사용자 ID", user_list, disabled=(not is_admin))
        with col4: page_size = st.selectbox("건수", [50, 100, 150], index=0)
        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            search_btn = st.button("조회", use_container_width=True)

        # 3. SQL 동적 구성
        query = "SELECT * FROM ai_analysis_logs WHERE 1=1"
        params = []
        if search_date:
            query += " AND log_date LIKE ?"
            params.append(f"{search_date}%")
        if search_page != "전체":
            query += " AND page_name = ?"
            params.append(search_page)
        if is_admin and search_user != "전체":
            query += " AND user_id = ?"
            params.append(search_user)
        elif not is_admin:
            query += " AND user_id = ?"
            params.append(current_user)
            
        # 전체 데이터 조회
        full_df = pd.read_sql(query + " ORDER BY 1 DESC", conn, params=params)

        # 4. 결과 처리 (페이징 반영)
        if full_df.empty:
            st.warning("🔍 조회된 Healing 이력이 없습니다.")
            st.button("📥 엑셀 다운로드", disabled=True)
        else:
            # 화면에는 설정한 page_size만큼만 보여줌
            display_df = full_df.head(page_size)
            
            st.success(f"총 {len(full_df)}건 중 상위 {len(display_df)}건을 표시합니다.")
            st.dataframe(display_df, use_container_width=True)
            
            # 5. 엑셀 다운로드 (전체 내역)
            import io
            buffer = io.BytesIO()
            full_df.to_excel(buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 엑셀 다운로드 (전체 내역)",
                data=buffer.getvalue(),
                file_name="healing_logs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # Healing Monitor 추가
    elif menu == "Healing Monitor":

        st.subheader("Healing Request Monitor")
    
        # 1. 권한 및 사용자 데이터 가져오기
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        current_user = st.session_state.get("current_user", "")
        
        # 관리자일 경우 사용자 목록 전체 가져오기
        if is_admin:
            users_df = pd.read_sql("SELECT user_id FROM user_master", conn)
            user_list = ["전체"] + users_df["user_id"].tolist()
        else:
            user_list = [current_user]

        # 2. 조회 필터 배치 (5개 컬럼 정렬)
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        with col1: search_date = st.date_input("날짜 선택", value=None)
        with col2: 
            pages = pd.read_sql("SELECT page_name FROM page_elements", conn)["page_name"].tolist()
            search_page = st.selectbox("페이지 선택", ["전체"] + pages)
        with col3: search_user = st.selectbox("사용자 ID", user_list, disabled=(not is_admin))
        with col4: page_size = st.selectbox("건수", [50, 100, 150], index=0)
        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            search_btn = st.button("조회", use_container_width=True)

        # 3. SQL 동적 구성
        query = "SELECT * FROM selector_healing_logs WHERE status != 'Completed'"
        params = []
        if search_date:
            query += " AND log_date LIKE ?"
            params.append(f"{search_date}%")
        if search_page != "전체":
            query += " AND page_name = ?"
            params.append(search_page)
        if is_admin and search_user != "전체":
            query += " AND user_id = ?"
            params.append(search_user)
        elif not is_admin:
            query += " AND user_id = ?"
            params.append(current_user)
            
        # 전체 데이터 조회
        full_df = pd.read_sql(query + " ORDER BY 1 DESC", conn, params=params)

        # 4. 결과 처리 (페이징 반영)
        if full_df.empty:
            st.warning("🔍 조회된 Healing 이력이 없습니다.")
            st.button("📥 엑셀 다운로드", disabled=True)
        else:
            # 화면에는 설정한 page_size만큼만 보여줌
            display_df = full_df.head(page_size)
            
            st.success(f"총 {len(full_df)}건 중 상위 {len(display_df)}건을 표시합니다.")
            st.dataframe(display_df, use_container_width=True)
            
            # 5. 엑셀 다운로드 (전체 내역)
            import io
            buffer = io.BytesIO()
            full_df.to_excel(buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 엑셀 다운로드 (전체 내역)",
                data=buffer.getvalue(),
                file_name="healing_logs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    elif menu == "Healing 이력":

        st.subheader("Selector Healing 이력")

        # 1. 권한 및 사용자 데이터 가져오기
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        current_user = st.session_state.get("current_user", "")
        
        # 관리자일 경우 사용자 목록 전체 가져오기
        if is_admin:
            users_df = pd.read_sql("SELECT user_id FROM user_master", conn)
            user_list = ["전체"] + users_df["user_id"].tolist()
        else:
            user_list = [current_user]

        # 2. 조회 필터 배치 (5개 컬럼 정렬)
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        with col1: search_date = st.date_input("날짜 선택", value=None)
        with col2: 
            pages = pd.read_sql("SELECT page_name FROM page_elements", conn)["page_name"].tolist()
            search_page = st.selectbox("페이지 선택", ["전체"] + pages)
        with col3: search_user = st.selectbox("사용자 ID", user_list, disabled=(not is_admin))
        with col4: page_size = st.selectbox("건수", [50, 100, 150], index=0)
        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            search_btn = st.button("조회", use_container_width=True)

        # 3. SQL 동적 구성
        query = "SELECT * FROM selector_healing_logs WHERE 1=1"
        params = []
        if search_date:
            query += " AND log_date LIKE ?"
            params.append(f"{search_date}%")
        if search_page != "전체":
            query += " AND page_name = ?"
            params.append(search_page)
        if is_admin and search_user != "전체":
            query += " AND user_id = ?"
            params.append(search_user)
        elif not is_admin:
            query += " AND user_id = ?"
            params.append(current_user)
            
        # 전체 데이터 조회
        full_df = pd.read_sql(query + " ORDER BY 1 DESC", conn, params=params)

        # 4. 결과 처리 (페이징 반영)
        if full_df.empty:
            st.warning("🔍 조회된 Healing 이력이 없습니다.")
            st.button("📥 엑셀 다운로드", disabled=True)
        else:
            # 화면에는 설정한 page_size만큼만 보여줌
            display_df = full_df.head(page_size)
            
            st.success(f"총 {len(full_df)}건 중 상위 {len(display_df)}건을 표시합니다.")
            st.dataframe(display_df, use_container_width=True)
            
            # 5. 엑셀 다운로드 (전체 내역)
            import io
            buffer = io.BytesIO()
            full_df.to_excel(buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 엑셀 다운로드 (전체 내역)",
                data=buffer.getvalue(),
                file_name="healing_logs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    elif menu == "페이지 관리":

        st.subheader("관리 대상 페이지")

        pages = pd.read_sql(
            "SELECT * FROM page_elements",
            conn
        )

        st.dataframe(pages, use_container_width=True)

        new_page = st.text_input("신규 페이지명")

        if st.button("페이지 추가"):

            cursor = conn.cursor()

            cursor.execute(
                "INSERT OR IGNORE INTO page_elements VALUES (?)",
                (new_page,)
            )

            conn.commit()

            st.success("등록 완료")
            st.rerun()

    elif menu == "시스템 설정":

        st.subheader("시스템 설정")

        config_df = pd.read_sql(
            "SELECT * FROM system_config",
            conn
        )

        st.dataframe(config_df, use_container_width=True)

    elif menu == "비밀번호 변경":

        st.subheader("🔑 비밀번호 변경")
        
        with st.form("password_change_form"):
            current_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 비밀번호", type="password")
            confirm_pw = st.text_input("새 비밀번호 확인", type="password")
            submit_btn = st.form_submit_button("비밀번호 변경하기")
            
        if submit_btn:
            # 1. DB에서 현재 비밀번호 조회
            user_id = st.session_state['current_user']
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM user_master WHERE user_id = ?", (user_id,))
            db_pw = cursor.fetchone()[0]
            
            # 2. 로직 검증
            if current_pw != db_pw:
                st.error("현재 비밀번호가 일치하지 않습니다.")
            elif new_pw != confirm_pw:
                st.error("새 비밀번호와 확인란의 내용이 다릅니다.")
            elif new_pw == "":
                st.error("새 비밀번호를 입력해주세요.")
            else:
                # 3. DB 업데이트 실행
                cursor.execute("UPDATE user_master SET password = ? WHERE user_id = ?", (new_pw, user_id))
                conn.commit()
                st.success("비밀번호가 성공적으로 변경되었습니다. 다시 로그인해 주세요.")
                # 선택사항: 변경 후 로그아웃 처리하려면 아래 주석 해제
                # st.session_state['logged_in'] = False
                # st.rerun()

    elif menu == "로그아웃":

        st.session_state["current_user"] = ""
        change_page_and_clear_inputs("login")

    conn.close()
