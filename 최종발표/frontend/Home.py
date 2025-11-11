
import streamlit as st
from pathlib import Path
from PIL import Image

from ui import app_shell 

st.set_page_config(page_title="FitBite: 균형 잡힌 한 입", page_icon="🍱", layout="centered")

app_shell("FitBite 🍱", active="home", show_tabs=False)

IMG_PATH = Path("/Users/minmi/Downloads/common-15.jpeg")

st.markdown(
    """
    <div style="text-align:center; margin-top:-12px;">
        <h2 style="font-weight:900; margin:6px 0;">FitBite</h2>
        <p style="color:#6b7280; font-size:14px; margin-bottom:12px;">
            균형 잡힌 한 입, 나만의 식단 분석 서비스
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if IMG_PATH.exists():
    img = Image.open(IMG_PATH)
    st.image(img, use_container_width=True, caption=None)
else:
    st.warning("대표 이미지를 찾을 수 없습니다. (common-15.jpeg)")

# ----------------- 로그인 / 회원가입 버튼 -----------------
st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    if st.button("🔐 로그인", use_container_width=True):
        try:
            st.switch_page("pages/1_로그인.py")
        except Exception:
            st.page_link("pages/1_로그인.py", label="로그인으로 이동", icon="➡️")

with c2:
    if st.button("🧾 회원가입", use_container_width=True):
        try:
            st.switch_page("pages/0_회원가입.py")
        except Exception:
            st.page_link("pages/0_회원가입.py", label="회원가입으로 이동", icon="➡️")


st.markdown(
    """
    <div style="text-align:center; font-size:11px; color:#9ca3af; margin-top:14px;">
        © 2025 FitBite | Developed by Team Sahur
    </div>
    """,
    unsafe_allow_html=True,
)
