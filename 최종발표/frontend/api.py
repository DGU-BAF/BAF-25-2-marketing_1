
import os
import requests
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _get_base() -> str:
    """
    백엔드 베이스 URL 결정 우선순위:
    1) 환경변수 BACKEND_BASE
    2) Streamlit secrets["backend_base"]
    3) 기본값 "http://localhost:8000"
    """
    base = os.getenv("BACKEND_BASE")
    if base:
        return base.rstrip("/")

    try:
        import streamlit as st
        sec = getattr(st, "secrets", None)
        if sec:
            base = sec.get("backend_base")
            if base:
                return str(base).rstrip("/")
    except Exception:
        pass

    return "http://localhost:8000"


BASE = _get_base()


def _auth(token: Optional[str]):
    return {"Authorization": f"Bearer {token}"} if token else {}


def _json_or_error(res: requests.Response):
    """
    응답을 JSON으로 파싱해 dict로 반환.
    오류일 때는 {"error": "..."} 형태로 통일.
    """
    try:
        res.raise_for_status()
        try:
            return res.json()
        except Exception:
            return {"error": f"Unexpected response (non-JSON): {res.text[:500]}"}
    except requests.exceptions.HTTPError:
        try:
            j = res.json()
            detail = j.get("detail", j)
            return {"error": detail}
        except Exception:
            return {"error": f"HTTP {res.status_code}: {res.text[:500]}"}
    except Exception as e:
        return {"error": f"Network error: {e}"}


def _response_bundle(res: requests.Response):
    """
    업로드 화면에서 디버깅하기 쉽게 raw 메타 포함 번들로 반환.
    """
    content_type = res.headers.get("content-type", "")
    try:
        payload = res.json() if "application/json" in content_type else res.text
    except Exception:
        payload = res.text
    return {
        "ok": res.ok,
        "status": res.status_code,
        "content_type": content_type,
        "payload": payload,
        "headers": dict(res.headers),
        "url": res.request.url,
        "method": res.request.method,
    }


def signup(username, password, height, weight, gender, meals_per_day):
    """
    POST /auth/signup
    반환: {"ok": true} 또는 {"error": "..."}
    """
    url = f"{BASE_URL}/auth/signup"
    payload = {
        "username": username,
        "password": password,
        "height": height,
        "weight": weight,
        "gender": gender,
        "meals_per_day": meals_per_day,
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        return _json_or_error(res)
    except Exception as e:
        return {"error": f"Signup request failed: {e}"}


def login(username, password):
    """
    POST /auth/login
    기대: {"access_token": "...", "token_type":"bearer", "username":"..."}
    실패: {"error":"..."}
    """
    url = f"{BASE_URL}/auth/login"
    payload = {"username": username, "password": password}
    try:
        res = requests.post(url, json=payload, timeout=30)
        data = _json_or_error(res)
        if "access_token" in data:
            return data
        return {"error": data.get("error", "로그인 실패")}
    except Exception as e:
        return {"error": f"Login request failed: {e}"}


def upload_food(
    file_bytes: bytes,
    filename: str,
    username: str,
    servings: float,
    meal_index: int,
    token: Optional[str] = None,
) -> dict:
    """
    /food/upload 로 멀티파트 폼 업로드.
    백엔드 응답(JSON) 그대로 반환.
    """
    files = {"file": (filename, file_bytes, "image/jpeg")}
    data = {
        "username": username,
        "meal_index": str(meal_index),
        "servings": str(servings),
    }
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.post(f"{BASE}/food/upload", files=files, data=data, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()


def get_dashboard(username, token: Optional[str]):
    """GET /dashboard/{username} → dict 또는 {"error": "..."}"""
    url = f"{BASE_URL}/dashboard/{username}"
    try:
        res = requests.get(url, headers=_auth(token), timeout=30)
        return _json_or_error(res)
    except Exception as e:
        return {"error": f"Dashboard request failed: {e}"}


def get_recommend(username: str, access_token: str, base: Optional[str] = None):
    """GET /recommend/{username} → dict (에러 시 예외 throw; 호출부에서 처리)"""
    base = base or BASE_URL
    url = f"{base}/recommend/{username}"
    headers = _auth(access_token)
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_weekly_report(
    username: str,
    access_token: str,
    offset_weeks: int = 1,
    base: Optional[str] = None,
):
    """GET /report/weekly/{username}?offset_weeks=N → dict (에러 시 예외 throw)"""
    base = base or BASE_URL
    url = f"{base}/report/weekly/{username}"
    headers = _auth(access_token)
    params = {"offset_weeks": int(offset_weeks)}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


__all__ = [
    "signup",
    "login",
    "upload_food",
    "get_dashboard",
    "get_recommend",
    "get_weekly_report",
]
