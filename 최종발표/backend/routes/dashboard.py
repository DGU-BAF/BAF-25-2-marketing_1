
from fastapi import APIRouter, HTTPException
from backend.schemas.responses import DashboardResponse
from backend.services.dashboard_service import get_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/{username}", response_model=DashboardResponse)
def fetch_dashboard(username: str):
    try:
        return get_dashboard(username)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
