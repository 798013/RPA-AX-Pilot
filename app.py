import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64

# 0. 초기 가상 DB 세팅 및 더미 데이터 삽입 (파일럿용 임시 생성)
def init_db():
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
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
    # 더미 데이터 채우기 (최초 1회만)
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('국토부_실거래가')")
    cursor.execute("INSERT OR IGNORE INTO page_elements VALUES ('상권정보_포털')")
    
    cursor.execute("SELECT COUNT(*) FROM selector_healing_logs")
    if cursor.fetchone() == 0:
        # 페이징 테스트를 위해 대량의 더미 생성 (150건 자동 생성)
        for i in range(1, 151):
            cursor.execute("""
                INSERT INTO selector_healing_logs (user_id, log_date, page_name, element_purpose, broken_selector, fixed_selector, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f"user_{i%3+1}", "2026-06-04", "국토부_실거래가" if i%2==0 else "상권정보_포털", 
                  "조회_버튼", f"button#old_id_{i}", f"div.new_class_{i} > button", "AI_추천완료"))
    conn.commit()
    conn.close()

# DB 초기화 실행
init_db()

# 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# ==========================================
# 화면 1: 로그인 페이지 (회사 CI 포함)
# ==========================================
if not st.session_state["logged_in"]:
    st.set_page_config(page_title="AX-RPA 제어 포털 로그인", layout="centered")
    
    # 🎨 [절대 깨지지 않는 내장형 반응형 정렬] 로컬 이미지를 읽어 가상 주소 없이 다이렉트 주입
    try:
        with open("SICT.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; width: 100%; margin-bottom: 20px;">
                <img src="data:image/png;base64,{encoded_string}" style="max-width: 250px; width: 50%; height: auto; object-fit: contain;">
            </div>
            """,
            unsafe_allow_html=True
        )
    except Exception:
        # 혹시 파일명 대소문자가 다를 경우를 대비한 백업 안내 텍스트
        st.markdown("<h3 style='text-align: center; color: #1E3A8A;'>🏢 SICT 로고 구역</h3>", unsafe_allow_html=True)
        
    st.markdown("<h1 style='text-align: center;'>AX-RPA 관제 시스템 로그인</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)", value="admin")
        user_pw = st.text_input("비밀번호 (Password)", type="password")
        login_btn = st.form_submit_button("로그인")
        
        if login_btn:
            if user_id == "admin" and user_pw == "1234":  # 파일럿용 마스터 계정
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ 로그인 실패: 아이디 또는 비밀번호를 확인하세요. (기본 화면 유지)")

# ==========================================
# 화면 2: 메인 대시보드 및 Grid (로그인 성공 시)
# ==========================================
else:
    st.set_page_config(page_title="AX-RPA Selector 관제 콘솔", layout="wide")
    
    col_title, col_logout = st.columns([0.85, 0.15])
    with col_title:
        st.title("🎛️ AX-RPA Selector RAG 제어 포털")
    with col_logout:
        if st.button("로그아웃"):
            st.session_state["logged_in"] = False
            st.rerun()

    st.markdown("---")
    
    st.subheader("🔍 Selector 변경 및 로그 조회 조건")
    
    # DB에서 웹페이지 목록 가져와 콤보박스에 뿌리기
    conn = sqlite3.connect("rpa_management.db")
    pages_df = pd.read_sql_query("SELECT page_name FROM page_elements", conn)
    page_options = pages_df["page_name"].tolist()
    conn.close()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        search_id = st.text_input("작업자 ID", value="user_1")
    with col2:
        search_date = st.date_input("조회 일자", datetime.now())
    with col3:
        search_page = st.selectbox("대상 Web Page (DB 연동)", options=page_options)
    with col4:
        limit_count = st.selectbox("조회 데이터 제한 (Grid Count)", options=[50, 100, 500])
    with col5:
        page_num = st.selectbox("페이지 선택 (Pagination)", options=[1, 2, 3])

    search_submitted = st.button("🚀 조건 조회", type="primary")

    if search_submitted or "current_data" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Selector 매칭 및 치유 이력 (Grid)")
        
        # 페이징 알고리즘 계산 (LIMIT, OFFSET)
        offset_value = limit_count * (page_num - 1)
        
        # 데이터 조회 실행
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
            
            # 엑셀 다운로드 비즈니스 로직
            towrite = pd.ExcelWriter('rpa_selector_logs.xlsx', engine='xlsxwriter')
            df.to_excel(towrite, index=False, sheet_name='Sheet1')
            towrite.close()
            
            with open('rpa_selector_logs.xlsx', 'rb') as f:
                st.download_button(label="📥 엑셀 내려받기", data=f, file_name=f"RPA_Logs_Page_{page_num}.xlsx", mime="application/vnd.ms-excel")
            
            st.info("💡 정보 수정 안내: 아래 그리드에서 'fixed_selector' 칸을 더블클릭하여 사람이 직접 정확한 Selector로 수정한 후 아래 [수정 내용 DB 반영] 버튼을 누르시면 RAG 지식이 보정됩니다.")
            
            # 수동 업데이트가 가능한 Interactive Grid 배치
            edited_df = st.data_editor(
                df, 
                num_rows="dynamic", 
                disabled=["log_id", "user_id", "log_date", "page_name", "element_purpose", "broken_selector"],
                use_container_width=True
            )
            
            # 사용자가 수정한 데이터 DB 반영 (Update Query)
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
                st.toast("🎉 수정 사항이 데이터베이스에 실시간 업데이트되었습니다! 다음 RPA 구동 시 반영됩니다.", icon="✅")
        else:
            st.warning("조회 조건에 일치하는 데이터가 현재 페이지 구간에 존재하지 않습니다.")
