import streamlit as st
from state import init_state
from api import signup


init_state()
from ui import app_shell
app_shell("👤 회원가입", active="auth", show_tabs=False)


with st.form("signup-form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("아이디")
        height   = st.number_input("키 (cm)", min_value=100, max_value=250, value=170, step=1)
        gender   = st.selectbox("성별", ["남자", "여자"])
    with col2:
        password = st.text_input("비밀번호", type="password")
        weight   = st.number_input("몸무게 (kg)", min_value=30.0, max_value=200.0, value=60.0, step=0.1)
        meals    = st.number_input("하루 끼니 수", min_value=1, max_value=10, value=3, step=1)

    submitted = st.form_submit_button("가입하기", use_container_width=True)

if submitted:
    # 1) 클라이언트 검증
    if not username or not password:
        st.warning("아이디/비밀번호를 입력하세요.")
    elif len(username) < 4 or len(username) > 20:
        st.warning("아이디는 4~20자로 입력하세요.")
    else:
        # 2) 서버 호출
        try:
            with st.spinner("회원가입 중..."):
                resp = signup(username, password, int(height), float(weight), gender, int(meals))
            st.success(resp.get("message", "회원가입 완료 ✅"))

            # 3) 다음 액션 안내
            st.info("이제 로그인 페이지로 이동해 로그인 해주세요.")
            st.page_link("pages/1_로그인.py", label="➡ 로그인 페이지로 이동")
        except Exception as e:
            # requests.HTTPError인 경우 서버 메시지를 최대한 노출
            msg = str(e)
            try:
                # e.response가 있을 때 detail 꺼내기
                detail = e.response.json()
                msg = detail.get("detail", msg)
            except Exception:
                pass
            st.error(f"회원가입 실패: {msg}")

