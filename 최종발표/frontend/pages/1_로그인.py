import streamlit as st
from ui import app_shell, page_header
from api import login  

st.set_page_config(page_title="로그인", layout="centered")

app_shell("🔐 로그인", active="auth", show_tabs=False)

if st.session_state.get("access_token") and st.session_state.get("username"):
    st.switch_page("pages/3_대시보드.py")

st.markdown("<div class='mobile-card'><div class='mobile-title'>계정 로그인</div>", unsafe_allow_html=True)

with st.form("login_form", clear_on_submit=False):
    username = st.text_input("아이디", placeholder="아이디를 입력하세요")
    password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
    col1, col2 = st.columns([1, 1])
    with col1:
        remember = st.checkbox("자동 로그인", value=False)
    with col2:
        submit = st.form_submit_button("로그인", use_container_width=True, type="primary")

st.markdown("</div>", unsafe_allow_html=True)


if submit:
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        st.warning("아이디와 비밀번호를 모두 입력하세요.")
        st.stop()

    try:
        with st.spinner("로그인 중..."):
            res = login(username, password)  
    except Exception as e:
        st.error(f"로그인 요청 실패: {e}")
        st.stop()


    err = res.get("error")
    token = res.get("access_token")

    if err:
        st.error(f"로그인 실패: {err}")
    elif token:
        st.session_state["access_token"] = token
        st.session_state["username"] = res.get("username", username)
        st.session_state["remember_me"] = bool(remember)
        st.success(f"{st.session_state['username']}님, 환영합니다!")
        st.switch_page("pages/2_업로드.py")
    else:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")


st.divider()
st.page_link("pages/0_회원가입.py", label="아직 계정이 없나요? ➜ 회원가입")
