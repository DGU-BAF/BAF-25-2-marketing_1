
from fastapi import APIRouter, HTTPException
from backend.schemas.responses import RecommendationResponse
from backend.services.recommend_service import recommend_or_summary

router = APIRouter(prefix="/recommend", tags=["recommend"])

@router.get("/{username}", response_model=RecommendationResponse)
def get_recommendation(username: str):
    try:
        return recommend_or_summary(username)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
