import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

from state import init_state
from api import get_weekly_report
from ui import app_shell, guard_login

st.set_page_config(page_title="주간 리포트", page_icon="🗓️", layout="centered")
init_state()
app_shell("🗓️ 주간 리포트", active="weekly", show_tabs=True)
guard_login()

st.markdown("""
<style>
.card{
  border:2px solid #111827; border-radius:14px; background:#f9fafb;
  padding:14px 16px; margin:10px 0 14px 0;
  color:#111 !important;
}
.card .title{ font-weight:900; font-size:1.08rem; margin-bottom:8px; color:#111 !important; }
.card .row{ margin:4px 0; font-size:0.98rem; color:#111 !important; }
.pill{
  display:inline-block; padding:2px 8px; margin-left:8px;
  border-radius:999px; font-weight:800; font-size:0.85rem;
}
.t-bold{ font-weight:800; color:#111 !important; }
.w80{ display:inline-block; width:96px; }
</style>
""", unsafe_allow_html=True)

username = st.session_state.get("username", "")
with st.spinner("주간 데이터 집계 중..."):
    data = get_weekly_report(username, st.session_state["access_token"], offset_weeks=0)

if isinstance(data, dict) and ("chart_data" in data or "daily_breakdown" in data):
    days_from_server = data.get("chart_data", []) or data.get("daily_breakdown", [])
    targets = data.get("targets")
    if not targets:
        gender = (st.session_state.get("gender") or "female").lower()
        if gender.startswith("m"):
            targets = {"kcal": 2600.0, "protein": 65.0, "fat": 65.0, "carb": 130.0}
        else:
            targets = {"kcal": 2000.0, "protein": 55.0, "fat": 50.0, "carb": 130.0}
    summary = data.get("summary", {}) or {}
    data = {"summary": summary, "targets": targets, "days": days_from_server}

days = pd.DataFrame(data.get("days", []))
if days.empty:
    st.info("주간 데이터가 아직 없어요.")
    st.stop()

# 표준화
days["date"] = pd.to_datetime(days["date"], errors="coerce")
for col in ["kcal", "protein", "fat", "carb"]:
    days[col] = pd.to_numeric(days[col], errors="coerce").fillna(0.0)
days = days.sort_values("date").reset_index(drop=True)

# 목표값
targets = data.get("targets") or {}
target_kcal    = float(targets.get("kcal", 0))
target_protein = float(targets.get("protein", 0))
target_fat     = float(targets.get("fat", 0))
target_carb    = float(targets.get("carb", 0))

st.caption(
    f"🎯 목표 — 칼로리 {int(target_kcal)} kcal · 단백질 {int(target_protein)} g · "
    f"지방 {int(target_fat)} g · 탄수화물 {int(target_carb)} g"
)

summary = data.get("summary", {}) or {}

def _avg_from_summary_or_days(summary_key: str, col: str) -> float:
    v = summary.get(summary_key, None)
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = np.nan
    if v is None or np.isnan(v) or v <= 0:
        return float(days[col].mean()) if not days.empty else 0.0
    return v

avg_kcal    = _avg_from_summary_or_days("avg_kcal", "kcal")
avg_protein = _avg_from_summary_or_days("avg_protein", "protein")
avg_fat     = _avg_from_summary_or_days("avg_fat", "fat")
avg_carb    = _avg_from_summary_or_days("avg_carb", "carb")

st.markdown("### 📅 주간 평균 요약")
c1, c2, c3, c4 = st.columns(4)
c1.metric("🔥 칼로리", f"{avg_kcal:.0f} kcal")
c2.metric("💪 단백질", f"{avg_protein:.0f} g")
c3.metric("🥑 지방", f"{avg_fat:.0f} g")
c4.metric("🍚 탄수화물", f"{avg_carb:.0f} g")

st.subheader("📈 일자별 칼로리 추이")

bar = alt.Chart(days).mark_bar().encode(
    x=alt.X("date:T", title="날짜", axis=alt.Axis(format="%a %d", labelAngle=0)),
    y=alt.Y("kcal:Q", title="kcal"),
    tooltip=[
        alt.Tooltip("date:T", title="날짜", format="%Y-%m-%d"),
        alt.Tooltip("kcal:Q", title="칼로리", format=".0f")
    ],
)
label = alt.Chart(days).mark_text(
    align="center", baseline="bottom", dy=-4, fontWeight="bold"
).encode(x="date:T", y="kcal:Q", text=alt.Text("kcal:Q", format=".0f"))

rule_df = pd.DataFrame({"y": [float(target_kcal)]})
rule = alt.Chart(rule_df).mark_rule(strokeDash=[6, 4]).encode(y="y:Q")

if target_kcal > 0:
    rule_label = alt.Chart(rule_df).mark_text(
        align="left", dx=6, dy=-6, fontWeight="bold"
    ).encode(y="y:Q", text=alt.value(f"목표 {int(target_kcal)} kcal"))
    st.altair_chart((bar + label + rule + rule_label).properties(height=300),use_container_width=True)
else:
    st.altair_chart((bar + label + rule).properties(height=300), use_container_width=True)

st.markdown("### 🎯 목표 근접도 (주간)")

CLR_P, CLR_F, CLR_C = "#34d399", "#f59e0b", "#60a5fa"
days["date_label"] = days["date"].dt.strftime("%m/%d (%a)")
days_sorted = days.sort_values("date")

def hbar_with_target(value_col, target_val, title, color):
    df = days_sorted[["date_label", value_col]].rename(columns={value_col: "grams"})
    base = alt.Chart(df).properties(width=700, height=220, title=title)
    bar = base.mark_bar(color=color).encode(
        y=alt.Y("date_label:N", sort=list(df["date_label"])),
        x="grams:Q",
        tooltip=[alt.Tooltip("date_label:N", title="날짜"),
                 alt.Tooltip("grams:Q", title="섭취(g)", format=".0f")],
    )
    rule = alt.Chart(pd.DataFrame({"x": [float(target_val)]})).mark_rule(strokeDash=[6, 4]).encode(x="x:Q")
    if target_val > 0:
        rule_txt = alt.Chart(pd.DataFrame({"x": [float(target_val)], "y": [df['date_label'].iloc[-1]]})).mark_text(
            dx=6, align="left", fontWeight="bold"
        ).encode(x="x:Q", y="y:N", text=alt.value(f"목표 {int(target_val)} g"))
        return alt.layer(bar, rule, rule_txt)
    else:
        return alt.layer(bar, rule)

panel_carb = hbar_with_target("carb", target_carb, "탄수화물 (g)", CLR_C)
panel_pro  = hbar_with_target("protein", target_protein, "단백질 (g)", CLR_P)
panel_fat  = hbar_with_target("fat", target_fat, "지방 (g)", CLR_F)
st.altair_chart(panel_carb & panel_pro & panel_fat, use_container_width=True)

if not days.empty:
    max_row = days.loc[days["kcal"].idxmax()]
    min_row = days.loc[days["kcal"].idxmin()]

    def closest_day(col, target):
        idx = (days[col] - target).abs().idxmin()
        row = days.loc[idx]
        return row["date"].date(), float(row[col]), float(row[col] - target)

    k_day, k_val, k_gap = closest_day("kcal", target_kcal)
    p_day, p_val, p_gap = closest_day("protein", target_protein)
    c_day, c_val, c_gap = closest_day("carb", target_carb)
    f_day, f_val, f_gap = closest_day("fat", target_fat)

    def _gap_badge(g):
        if g > 0:
            color, text = "#ef4444", f"+{g:.0f} g"
        elif g < 0:
            color, text = "#2563eb", f"{g:.0f} g"
        else:
            color, text = "#16a34a", f"{g:.0f} g"
        return f"<span class='pill' style='background:{color}1a;color:{color}'>{text}</span>"

    p_badge, c_badge, f_badge = _gap_badge(p_gap), _gap_badge(c_gap), _gap_badge(f_gap)

    st.markdown(f"""
    <div class="card">
      <div class="title">📊 요약</div>
      <div class="row"><span class="w80 t-bold">목표 칼로리</span> {int(target_kcal)} kcal</div>
      <div class="row"><span class="w80 t-bold">최대 섭취</span> {max_row['date'].date()} — <b>{max_row['kcal']:.0f} kcal</b></div>
      <div class="row"><span class="w80 t-bold">최소 섭취</span> {min_row['date'].date()} — <b>{min_row['kcal']:.0f} kcal</b></div>
      <div class="row"><span class="w80 t-bold">목표 근접</span> {k_day} — <b>{k_val:.0f} kcal</b></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="card">
      <div class="title">🎯 목표 근접일</div>
      <div class="row"><span class="w80 t-bold">단백질</span> {p_day} — <b>{p_val:.0f} g</b> {p_badge}</div>
      <div class="row"><span class="w80 t-bold">탄수화물</span> {c_day} — <b>{c_val:.0f} g</b> {c_badge}</div>
      <div class="row"><span class="w80 t-bold">지방</span> {f_day} — <b>{f_val:.0f} g</b> {f_badge}</div>
    </div>
    """, unsafe_allow_html=True)
