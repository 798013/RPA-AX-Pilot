import streamlit as st
import pandas as pd
import sqlite3
import base64
import time
import re
import secrets
import requests

# 1. 페이지 설정은 무조건 맨 위에 한 번만 실행
st.set_page_config(page_title="AX-RPA 시스템", layout="wide")

# --- [함수 정의] ---
def render_header(title):
    h1, h2 = st.columns([0.7, 0.3])
    with h1:
        st.subheader(title)
    with h2:
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
    st.divider()

def init_db():
    # (기존 init_db 내용 그대로 유지)
    conn = sqlite3.connect("rpa_management.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS user_master (user_id TEXT PRIMARY KEY, user_pw TEXT, user_name TEXT, user_email TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS selector_healing_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, log_date TEXT, page_name TEXT, element_purpose TEXT, broken_selector TEXT, fixed_selector TEXT, status TEXT)")
    cursor.execute("INSERT OR IGNORE INTO user_master VALUES ('admin', '1234', '홍길동', 'sict@sict.co.kr')")
    conn.commit()
    conn.close()

init_db()

# 세션 상태 초기화
if "page_state" not in st.session_state: st.session_state["page_state"] = "login"

# --- [페이지 라우팅] ---
if st.session_state["page_state"] == "login":
    st.title("로그인")
    # 로그인 폼...
    if st.button("로그인 테스트"):
        st.session_state["page_state"] = "main_dashboard"
        st.rerun()

elif st.session_state["page_state"] == "main_dashboard":
    render_header("등록 내역 검색")
    st.write("대시보드 메인 내용입니다.")
    # 검색 로직 시작

elif st.session_state["page_state"] == "change_password":
    render_header("비밀번호 변경")
    st.write("비밀번호 변경 폼입니다.")
