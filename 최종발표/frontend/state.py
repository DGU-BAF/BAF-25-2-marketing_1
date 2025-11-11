import streamlit as st

def init_state():
    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("username", None)


import datetime as dt

def init_state():
    defaults = {
        "access_token": None,
        "username": None,
        "meal_log": [],
        "uploads_today": 0,
        "uploads_date": dt.date.today().isoformat(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
