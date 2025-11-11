import io
from PIL import Image
import streamlit as st

from state import init_state
from ui import app_shell, guard_login, page_header
from api import upload_food

init_state()
st.set_page_config(page_title="업로드칸", page_icon="🍱", layout="centered")

app_shell("🏠 홈 (업로드)", active="home", show_tabs=True)
guard_login()
page_header("📤 음식 업로드")

with st.form("upload_form", clear_on_submit=False):
    file = st.file_uploader("이미지 업로드 (jpg/png)", type=["jpg", "jpeg", "png"])
    servings = st.number_input("인분", min_value=0.1, max_value=10.0, step=0.5, value=1.0)
    meal_map = {"1️⃣ 아침":1, "2️⃣ 점심":2, "3️⃣ 저녁":3, "4️⃣ 간식":4}
    meal_label = st.selectbox("🕒 끼니 선택", list(meal_map.keys()), index=0)
    submit = st.form_submit_button("기록 완료", use_container_width=True)

if submit:
    if not file:
        st.error("이미지를 선택하세요.")
    else:
        file_bytes = file.read()
        if not file_bytes:
            st.error("업로드한 파일을 읽지 못했습니다.")
        else:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                st.image(img, caption=file.name, use_container_width=True)
            except Exception as e:
                st.warning(f"미리보기 로드 실패: {e}")

            
            with st.spinner("탐지 및 영양 계산 중..."):
                username = st.session_state.get("username", "demo")
                token = st.session_state.get("token")
                try:
                    resp = upload_food(
                        file_bytes,         
                        file.name,
                        username,
                        servings=float(servings),
                        meal_index=meal_map[meal_label],
                        token=token
                    )
                    st.session_state["last_upload_result"] = resp
                    st.success("업로드 및 탐지 완료!")
                except Exception as e:
                    st.error(f"업로드 실패: {e}")


def render_detected_cards(resp: dict):
    st.subheader("🔎 탐지 결과 요약")

    summary = (resp or {}).get("summary", {})
    items = summary.get("items", []) if isinstance(summary, dict) else []

    if not items:
        matched = (resp or {}).get("matched", []) or []
        for m in matched[:3]:
            tot = m.get("total_nutrients") or {}
            items.append({
                "food_name": m.get("food_name") or m.get("raw_label"),
                "confidence": float(m.get("confidence", 0.0)),
                "servings": float(m.get("servings", 1.0)),
                "kcal": float(tot.get("kcal", 0.0)),
                "carb_g": float(tot.get("carb_g", 0.0)),
                "protein_g": float(tot.get("protein_g", 0.0)),
                "fat_g": float(tot.get("fat_g", 0.0)),
            })

    if not items:
        st.info("탐지/매칭된 음식이 없습니다.")
        return

    for it in items:
        name = it.get("food_name", "음식")
        conf = it.get("confidence", 0.0)
        sv   = it.get("servings", 1.0)
        kcal = it.get("kcal", 0.0)
        carb = it.get("carb_g", 0.0)
        prot = it.get("protein_g", 0.0)
        fat  = it.get("fat_g", 0.0)

        with st.container(border=True):
            st.markdown(f"**{name}** · 신뢰도 {conf:.0%} · {sv:g} 인분")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("kcal", f"{kcal:.0f}")
            c2.metric("탄수화물(g)", f"{carb:.1f}")
            c3.metric("단백질(g)", f"{prot:.1f}")
            c4.metric("지방(g)", f"{fat:.1f}")

    totals = (resp or {}).get("today_totals", {}) or {}
    st.caption(
        f"오늘 누적: "
        f"{totals.get('total_kcal', 0):.0f} kcal · "
        f"탄 {totals.get('total_carb_g', 0):.1f} g · "
        f"단 {totals.get('total_protein_g', 0):.1f} g · "
        f"지 {totals.get('total_fat_g', 0):.1f} g"
    )

if "last_upload_result" in st.session_state:
    render_detected_cards(st.session_state["last_upload_result"])
