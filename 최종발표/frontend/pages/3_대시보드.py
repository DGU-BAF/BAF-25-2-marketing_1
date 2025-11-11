import streamlit as st
import pandas as pd
import altair as alt

from ui import app_shell, guard_login
from state import init_state
from api import get_dashboard, get_recommend


st.set_page_config(page_title="대시보드", page_icon="📊", layout="centered")
init_state()
app_shell("📊 대시보드", active="dashboard", show_tabs=True)
guard_login()


st.markdown("""
<style>
.block-container{max-width:420px !important}
.h-title{font-size:24px; font-weight:900; margin:8px 0 6px 0}
.h-sec{font-size:18px; font-weight:800; margin:8px 0 6px 0}
.t-caption{font-size:12px; color:#9ca3af; margin:0}
.t-value{font-size:22px; font-weight:800; margin:2px 0 10px 0}
.t-small{font-size:13px}
.t-badge{font-size:12px; font-weight:800; padding:4px 8px; border-radius:999px; display:inline-block}
.badge-ok{background:#dcfce7; color:#065f46}
.k-sep{border-top:1px solid #1f2937; margin:14px 0}
[data-testid="stMetricValue"]{font-size:18px}
[data-testid="stMetricDelta"]{font-size:12px}
</style>
""", unsafe_allow_html=True)

def lack_badge(text: str) -> str:
    # t-badge / badge-ok 클래스는 위에서 넣어둔 CSS에 이미 있음
    return f"<span class='t-badge badge-ok'>{text}</span>"

token = st.session_state.get("access_token")
username = st.session_state.get("username", "")

with st.spinner("오늘 요약 불러오는 중..."):
    dash = get_dashboard(username, token)
with st.spinner("추천 불러오는 중..."):
    rec = get_recommend(username, token)


targets = (dash.get("targets") or {})
t_kcal = float(targets.get("kcal") or 0)
t_pro  = float(targets.get("protein") or 0)
t_fat  = float(targets.get("fat") or 0)
t_carb = float(targets.get("carb") or 0)

if t_kcal <= 0 or t_pro <= 0 or t_fat <= 0 or t_carb <= 0:
    gender = (st.session_state.get("gender") or "female").lower()
    if gender.startswith("m"):
        t_kcal, t_pro, t_fat, t_carb = 2600.0, 65.0, 65.0, 130.0
    else:
        t_kcal, t_pro, t_fat, t_carb = 2000.0, 55.0, 50.0, 130.0
    

meals = dash.get("meals", [])
today_kcal = float(dash.get("total_kcal") or 0)
today_pro  = float(sum(m.get("protein", 0) for m in meals))
today_fat  = float(sum(m.get("fat", 0) for m in meals))
today_carb = float(sum(m.get("carb", 0) for m in meals))

rem_pro  = t_pro  - today_pro
rem_fat  = t_fat  - today_fat
rem_carb = t_carb - today_carb

pct_c = 0 if t_carb == 0 else max(0, min(1, today_carb / t_carb))
pct_p = 0 if t_pro  == 0 else max(0, min(1, today_pro  / t_pro))
pct_f = 0 if t_fat  == 0 else max(0, min(1, today_fat  / t_fat))

CLR_C = "#60a5fa"
CLR_P = "#34d399"
CLR_F = "#f59e0b"
GREY  = "#e5e7eb"


st.markdown("<div class='h-title'>대시보드</div>", unsafe_allow_html=True)
h1, h2 = st.columns(2)
with h1:
    st.markdown("<div class='t-caption'>날짜</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='t-value'>{dash.get('date','')}</div>", unsafe_allow_html=True)
with h2:
    st.markdown("<div class='t-caption'>총 섭취 칼로리 (kcal)</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='t-value'>{today_kcal:.0f}</div>", unsafe_allow_html=True)

def ring_chart(pct: float, color: str, size: int = 92) -> alt.Chart:
    pct = float(max(0, min(1, pct)))
    bg = alt.Chart(pd.DataFrame({"v": [1]})).mark_arc(
        innerRadius=size * 0.34, outerRadius=size * 0.46, color=GREY
    ).encode(theta=alt.Theta("v:Q", stack=True))

    fg = alt.Chart(pd.DataFrame({"v": [pct]})).mark_arc(
        innerRadius=size * 0.34, outerRadius=size * 0.46, color=color
    ).encode(theta=alt.Theta("v:Q", stack=True))

    txt = alt.Chart(pd.DataFrame({"t": [f"{int(round(pct * 100))}%"]})).mark_text(
        fontWeight="bold", fontSize=16, dy=1
    ).encode(text="t:N")


    return (
        alt.layer(bg, fg, txt)
        .properties(width=size, height=size, padding={"top": 7, "right": 0, "bottom": 0, "left": 0})
        .configure_view(stroke=None)
    )

c1, c2, c3 = st.columns(3)
for label, color, t_val, now_val, rem_val, pct in [
    ("탄수화물", CLR_C, t_carb, today_carb, rem_carb, pct_c),
    ("단백질", CLR_P, t_pro, today_pro, rem_pro, pct_p),
    ("지방", CLR_F, t_fat, today_fat, rem_fat, pct_f),
]:
    with eval(f"c{['탄수화물','단백질','지방'].index(label)+1}"):
        st.markdown(
            f"<div class='macro-title'>{label}</div>"
            f"<div style='font-size:10px;color:#6b7280;'>목표 {t_val:.1f} g / 누적 {now_val:.1f} g</div>",
            unsafe_allow_html=True
        )
        st.altair_chart(ring_chart(pct, color),use_container_width=True)
        st.markdown(lack_badge(f"부족 {max(rem_val,0):.1f} g ({(1-pct)*100:.1f}%)"), unsafe_allow_html=True)

st.markdown("<div class='k-sep'></div>", unsafe_allow_html=True)


st.markdown("<div class='h-sec'>🔔 오늘의 추천 (Top 3)</div>", unsafe_allow_html=True)

if rec.get("mode") != "next":
    st.info("오늘 식사가 모두 끝났어요. 내일 다시 추천해드릴게요.")
else:
    items = pd.DataFrame(rec.get("recommendations", []))
    if items.empty:
        st.info("추천 데이터가 없어요.")
    else:
        def mini_donut(row):
            df = pd.DataFrame({
                "macro": ["단백질", "지방", "탄수화물"],
                "gram": [row["protein"], row["fat"], row["carb"]],
            })
            return (
                alt.Chart(df)
                .mark_arc(innerRadius=22, outerRadius=32)
                .encode(
                    theta="gram:Q",
                    color=alt.Color("macro:N", scale=alt.Scale(
                        domain=["단백질", "지방", "탄수화물"],
                        range=[CLR_P, CLR_F, CLR_C]
                    ), legend=None),
                )
                .properties(width=90, height=90)
                .configure_view(stroke=None)
            )

        for i, row in items.head(3).iterrows():
            with st.container(border=True):
                a, b, c = st.columns([3.0, 2.0, 1.2])
                with a:
                    st.markdown(
                        f"**{i+1}위 · {row['name']}** "
                        f"<span class='t-badge' style='background:#DBEAFE;color:#1E40AF'>{row['servings']:.1f}인분</span>",
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f"<div class='t-small'>칼로리 <b>{row['kcal']:.0f} kcal</b> · "
                        f"단백질 <b>{row['protein']:.0f} g</b> · 지방 <b>{row['fat']:.0f} g</b> · "
                        f"탄수 <b>{row['carb']:.0f} g</b></div>",
                        unsafe_allow_html=True
                    )
                with b:
                    st.metric("남은 칼로리", f"{row.get('rem_kcal', 0):.0f} kcal")
                    st.metric("남은 단백질", f"{row.get('rem_protein', 0):.0f} g")
                with c:
                    st.altair_chart(mini_donut(row), use_container_width=True)
