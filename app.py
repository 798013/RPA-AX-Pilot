import streamlit as st
import pandas as pd
import pyodbc
from datetime import datetime
import base64
import time
import secrets
import requests
import io

# 💡 system_config에 접속 정보가 없을 때 사용할 최초 기동용 로컬 기본값
DEFAULT_SERVER = r"localhost\EXPRESS2025"
DEFAULT_DB = "HealingDB"

def get_mssql_connection():
    """System_Config 인프라 혹은 기본값 기준으로 동적 커넥션을 반환하는 함수 (Exception 반영)"""
    try:
        # 1단계: 우선 기본 로컬 정보로 연결을 시도해서 환경 설정을 읽을 준비를 합니다.
        conn = pyodbc.connect(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DEFAULT_SERVER};"
            f"DATABASE={DEFAULT_DB};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;",
            timeout=3 # 3초 내에 반응 없으면 예외 처리
        )
        return conn
    except Exception as e:
        # DB가 아예 안 켜졌거나 스키마가 없을 때 화면 뻗는 것을 방지
        st.error(f"🚨 데이터베이스 연결 실패 (localhost\EXPRESS2025 상태를 확인하세요): {e}")
        return None

def init_db():
    """MSSQL 인프라 테이블 자동 생성 및 기본 마스터 설정 세팅 (Exception 반영)"""
    conn = get_mssql_connection()
    if conn is None:
        return # DB 연결 실패 시 에러만 띄우고 다음 로직으로 안전하게 패스
        
    try:
        cursor = conn.cursor()
        
        # [테이블 1] 형님이 정의해주신 user_master 스키마 반영
        cursor.execute("""
            IF OBJECT_ID('dbo.user_master', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.user_master (
                    user_id NVARCHAR(50) PRIMARY KEY,
                    user_pw NVARCHAR(100) NOT NULL,
                    project_name NVARCHAR(150) NULL,
                    user_name NVARCHAR(100) NOT NULL,
                    user_email NVARCHAR(150) NOT NULL,
                    is_admin CHAR(1) DEFAULT 'N',
                    created_dt DATETIME2 DEFAULT SYSDATETIME(),
                    update_dt DATETIME2 DEFAULT SYSDATETIME()
                );
            END
        """)
        
        # [테이블 2] 형님이 정의해주신 system_config 스키마 반영
        cursor.execute("""
            IF OBJECT_ID('dbo.system_config', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.system_config (
                    config_key NVARCHAR(100) PRIMARY KEY,
                    config_value NVARCHAR(500) NOT NULL,
                    created_dt DATETIME2 DEFAULT SYSDATETIME(),
                    update_dt DATETIME2 DEFAULT SYSDATETIME()
                );
            END
        """)
        conn.commit()
        
        # 초기 admin 데이터 보정 투입
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM dbo.user_master WHERE user_id = 'admin')
            BEGIN
                INSERT INTO dbo.user_master (user_id, user_pw, project_name, user_name, user_email, is_admin)
                VALUES ('admin', '1234', 'SYSTEM', N'홍길동', 'sict@sict.co.kr', 'Y');
            END
        """)
        
        # config 기본 접속정보 세팅
        db_configs = [
            ('DB_SERVER', r'localhost\EXPRESS2025'),
            ('DB_NAME', 'HealingDB'),
            ('DB_TYPE', 'MSSQL')
        ]
        for key, val in db_configs:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.system_config WHERE config_key = ?)
                BEGIN
                    INSERT INTO dbo.system_config (config_key, config_value) VALUES (?, ?);
                END
            """, (key, key, val))
            
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"⚠️ 테이블 생성 및 초기화 중 오류 발생: {e}")

# 앱 구동 시 초기화 실행
init_db()

# --- 세션 상태 관리 ---
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

# --- 로고 이미지 처리 ---
try:
    with open("SICT.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()
    logo_html = f"""<div style="text-align:center; margin-bottom:20px;"><img src="data:image/png;base64,{logo_base64}" style="max-width:250px; width:50%;"></div>"""
except:
    logo_html = "<h3 style='text-align: center; color: #1E3A8A;'>🏢 Self-Healing Portal</h3>"

# --- 화면 1: 에러 리다이렉트 ---
if st.session_state["page_state"] == "default_error":
    st.set_page_config(page_title="접근 차단됨", layout="centered")
    st.error("🚨 잘못된 인증 정보입니다. 등록되지 않은 ID이거나 비밀번호가 다릅니다.")
    time.sleep(2)
    change_page_and_clear_inputs("login")

# --- 화면 2: 신규 회원가입 ---
elif st.session_state["page_state"] == "signup":
    st.set_page_config(page_title="신규 회원가입", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    
    with st.form("signup_form"):
        new_id = st.text_input("사용할 아이디 (ID)")
        new_pw = st.text_input("비밀번호 (Password)", type="password")
        new_project = st.text_input("사이트명 (RPA 프로젝트명)")
        new_name = st.text_input("사용자 이름")
        new_email = st.text_input("이메일 주소")
        submit_signup = st.form_submit_button("가입 신청 완료")
        
        if submit_signup:
            if not (new_id and new_pw and new_project and new_name and new_email):
                st.error("⚠️ 모든 칸을 입력해 주세요.")
            else:
                try:
                    conn = get_mssql_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM dbo.user_master WHERE user_id = ?", (new_id,))
                    if cursor.fetchone():
                        st.error("❌ 이미 존재하는 아이디입니다.")
                    else:
                        cursor.execute("""
                            INSERT INTO dbo.user_master (user_id, user_pw, project_name, user_name, user_email, is_admin)
                            VALUES (?, ?, ?, ?, ?, 'N')
                        """, (new_id, new_pw, new_project, new_name, new_email))
                        conn.commit()
                        st.success("🎉 가입 완료! 로그인 페이지로 이동합니다.")
                        time.sleep(1.5)
                        change_page_and_clear_inputs("login")
                    conn.close()
                except Exception as e:
                    st.error(f"회원가입 처리 중 DB 오류: {e}")
                    
    if st.button("⬅️ 로그인 화면으로 복귀"):
        change_page_and_clear_inputs("login")

# --- 화면 4: 완성형 로그인 화면 (Form 내 배치 완료 + Enter 키 지원) ---
elif st.session_state["page_state"] == "login":
    st.set_page_config(page_title="Self-Healing Portal 로그인", layout="centered")
    st.markdown(logo_html, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>Self-Healing Portal</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)", key=f"id_input_{st.session_state['login_id_key']}")
        user_pw = st.text_input("비밀번호 (Password)", type="password", key=f"pw_input_{st.session_state['login_pw_key']}")
        
        st.write("")
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            submit_find = st.form_submit_button("ID / PW 찾기", use_container_width=True)
        with col_nav2:
            submit_signup = st.form_submit_button("회원 가입", use_container_width=True)
                
        st.write("")
        submit_login = st.form_submit_button("로그인", type="primary", use_container_width=True)
        
        if submit_login:
            try:
                conn = get_mssql_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_pw, is_admin FROM dbo.user_master WHERE user_id = ?", (user_id,))
                    db_result = cursor.fetchone()
                    conn.close()
                    
                    if db_result and db_result[0] == user_pw:
                        st.session_state["is_admin"] = db_result[1]
                        st.session_state["page_state"] = "main_dashboard"
                        st.session_state["current_user"] = user_id
                        st.rerun()
                    else:
                        change_page_and_clear_inputs("default_error")
            except Exception as e:
                st.error(f"로그인 인증 중 장애 발생: {e}")
                
        elif submit_find:
            st.info("💡 ID/PW 찾기 화면 연동은 생략 혹은 간소화 가능합니다.")
            
        elif submit_signup:
            change_page_and_clear_inputs("signup")

# --- 화면 5: 메인 관제 대시보드 (미니멀 메뉴 트리 트리밍) ---
elif st.session_state["page_state"] == "main_dashboard":
    st.set_page_config(page_title="Self-Healing Portal", layout="wide")
    st.title("🤖 Self-Healing Portal")

    with st.sidebar:
        st.success(f"사용자 : {st.session_state['current_user']}")
        is_admin = st.session_state.get("is_admin", "N") == "Y"
        
        # 🟢 지침대로 6개 핵심 메뉴트리만 깔끔하게 유지 및 admin 필터 적용
        menu_options = ["Dashboard", "Knowledge DB"]
        if is_admin:
            menu_options.extend(["사용자 관리", "시스템 설정"])
        menu_options.extend(["비밀번호 변경", "로그아웃"])
        
        menu = st.radio("메뉴 선택", menu_options)

    # 모든 대시보드 조회 파트 비정상 데이터 에러 방지(Exception) 적용
    try:
        conn = get_mssql_connection()
    except:
        conn = None

    if conn is None:
        st.warning("⚠️ 데이터베이스에 연결할 수 없어 관제 데이터를 표시할 수 없습니다.")
    else:
        if menu == "Dashboard":
            try:
                # 데이터가 아예 없을 때 0건 처리용 에러 방지 카운트
                user_count = pd.read_sql("SELECT COUNT(*) cnt FROM dbo.user_master", conn)["cnt"][0]
                kn_count = pd.read_sql("SELECT COUNT(*) cnt FROM dbo.selector_knowledge", conn)["cnt"][0]
                
                c1, c2 = st.columns(2)
                c1.metric("등록 사용자 수", user_count)
                c2.metric("Knowledge 축적 건수", kn_count)
                
                st.divider()
                st.subheader("최근 축적된 Selector Knowledge 정보")
                df = pd.read_sql("SELECT TOP 10 project_name, process_name, healed_selector, success_count FROM dbo.selector_knowledge ORDER BY knowledge_id DESC", conn)
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"대시보드 로딩 실패: {e}")

        elif menu == "Knowledge DB":
            st.subheader("📚 Selector Knowledge DB")
            try:
                df = pd.read_sql("SELECT * FROM dbo.selector_knowledge", conn)
                if df.empty:
                    st.info("현재 축적된 Selector 지식이 데이터베이스에 없습니다.")
                else:
                    st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"지식 베이스 데이터 로드 실패: {e}")

        elif menu == "사용자 관리":
            st.subheader("👥 사용자 계정 리스트")
            try:
                user_df = pd.read_sql("SELECT user_id, project_name, user_name, user_email, is_admin, created_dt FROM dbo.user_master", conn)
                st.dataframe(user_df, use_container_width=True)
            except Exception as e:
                st.error(f"사용자 목록 로드 실패: {e}")

        elif menu == "시스템 설정":
            st.subheader("⚙️ System Config 설정")
            try:
                config_df = pd.read_sql("SELECT * FROM dbo.system_config", conn)
                st.dataframe(config_df, use_container_width=True)
            except Exception as e:
                st.error(f"시스템 설정 로드 실패: {e}")

        elif menu == "비밀번호 변경":
            st.subheader("🔑 비밀번호 변경")
            with st.form("pw_form"):
                curr_pw = st.text_input("현재 비밀번호", type="password")
                new_pw = st.text_input("새 비밀번호", type="password")
                submit_pw = st.form_submit_button("변경 적용")
                if submit_pw:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE dbo.user_master SET user_pw = ?, update_dt = SYSDATETIME() WHERE user_id = ?", (new_pw, st.session_state['current_user']))
                        conn.commit()
                        st.success("비밀번호가 변경되었습니다.")
                    except Exception as e:
                        st.error(f"비밀번호 변경 실패: {e}")

        elif menu == "로그아웃":
            st.session_state["current_user"] = ""
            change_page_and_clear_inputs("login")

        conn.close()
