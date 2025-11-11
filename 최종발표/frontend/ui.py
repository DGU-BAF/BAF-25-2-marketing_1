
import streamlit as st

_MOBILE_CSS = """
<style>
.block-container{
  max-width: 420px !important;
  padding-bottom: 88px !important; /* 하단 탭바 공간 */
}

/* 컬러/폰트 */
:root{
  --txt:#1f2937; --muted:#6b7280; --border:#e5e7eb; --panel:#f9fafb;
  --brand:#0f172a; --brand2:#1f2937;
}
html, body, [data-baseweb="baseweb"]{
  font-family: -apple-system, BlinkMacSystemFont, "Noto Sans KR", system-ui, Segoe UI, Roboto, Arial, sans-serif;
  color: var(--txt);
}

/* 타이포(모바일 스케일) */
.h1 {font-size: 22px; font-weight: 900; margin: 10px 0 4px;}
.h2 {font-size: 18px; font-weight: 800; margin: 10px 0 6px;}
.h3 {font-size: 16px; font-weight: 800; margin: 8px 0 6px;}
.value-lg {font-size: 20px; font-weight: 800; margin: 2px 0 6px;}
.caption {font-size: 12px; color: var(--muted); margin: 0;}
.card{ background: var(--panel); border:1px solid var(--border); border-radius:14px; padding:12px 14px; margin:8px 0 10px; }

/* 상단 앱바 */
.appbar{
  position: sticky; top:0; z-index:50;
  background: var(--brand); color:#e5e7eb; border-bottom:1px solid #111827;
  padding: 10px 14px; margin: -10px -10px 8px -10px; font-weight:800; font-size:18px; text-align:center;
}

/* 하단 탭바(고정) */
.mobile-tabbar{
  position: fixed; left:0; right:0; bottom:0; z-index:60;
  background: var(--brand); border-top:1px solid #111827; padding:8px 8px 10px;
}
.mobile-tabbar__inner{ max-width: 420px; margin:0 auto; }
.tab-btn{
  border-radius:12px; font-weight:800; font-size:14px; padding:0; overflow:hidden;
  background:#111827; color:#cbd5e1; border: none;
}
.tab-btn.active{ background: var(--brand2); color:#e5e7eb; }

/* Streamlit 기본 UI 숨김 */
#MainMenu, header, footer {visibility:hidden;}
/* metric 축소 */
[data-testid="stMetricValue"]{font-size:16px}
[data-testid="stMetricDelta"]{font-size:11px}
</style>
"""

def app_shell(title: str, active: str = "home", show_tabs: bool = True):
    """
    active: 'home' | 'dashboard' | 'weekly' | 'auth'
    - 각 페이지 파일 상단에서 st.set_page_config(...) 먼저 호출할 것
    - 여기서는 set_page_config 호출하지 않음
    """
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)
    st.markdown(f"<div class='appbar'>{title}</div>", unsafe_allow_html=True)

    if not show_tabs:
        return

    is_authed = bool(st.session_state.get("access_token"))

    # 탭바 렌더
    with st.container():
        st.markdown("<div class='mobile-tabbar'><div class='mobile-tabbar__inner'>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        def _tab(label, page_path, is_active):
            btn_class = "tab-btn active" if is_active else "tab-btn"
            st.markdown(f"<div class='{btn_class}'>", unsafe_allow_html=True)
            st.page_link(page_path, label=label, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if is_authed:
            with c1: _tab("📊 대시보드", "pages/3_대시보드.py", active == "dashboard")
            with c2: _tab("🏠 홈",       "pages/2_업로드.py",   active == "home")
            with c3: _tab("🗓️ 리포트",   "pages/5_주간리포트.py", active == "weekly")
        else:
            # 비로그인 상태에선 전부 로그인으로
            with c1: _tab("🔐 로그인", "pages/1_로그인.py", active == "auth")
            with c2: _tab("🔐 로그인", "pages/1_로그인.py", active == "auth")
            with c3: _tab("🔐 로그인", "pages/1_로그인.py", active == "auth")

def page_header(title: str, emoji: str = "🍱"):
    st.markdown(f"<h2 style='margin:8px 0 0 0'>{emoji} {title}</h2>", unsafe_allow_html=True)

def guard_login():
    # 토큰이 없으면 무조건 차단
    if not st.session_state.get("access_token"):
        st.warning("로그인이 필요합니다.")
        st.page_link("pages/1_로그인.py", label="🔐 로그인 화면으로 이동",use_container_width=True)
        st.stop()

def show_json(data):
    with st.expander("자세히 보기 (JSON)", expanded=False):
        st.json(data)

def nutrition_card(name: str, conf: float, servings: float, kcal: float, carb: float, prot: float, fat: float):
    with st.container(border=True):
        st.markdown(f"**{name}** · 신뢰도 {conf:.0%} · {servings:g} 인분")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("kcal", f"{kcal:.0f}")
        c2.metric("탄수화물(g)", f"{carb:.1f}")
        c3.metric("단백질(g)", f"{prot:.1f}")
        c4.metric("지방(g)", f"{fat:.1f}")
