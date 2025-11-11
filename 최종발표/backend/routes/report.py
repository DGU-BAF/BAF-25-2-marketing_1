
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.report_service import build_weekly_report

router = APIRouter(prefix="/report", tags=["Report"])

@router.get("/weekly/{username}", summary="주간 리포트 조회 (지난주 월~일)",
            description="""
주간 리포트를 통계 중심으로 제공합니다.

- 기본 기간: **지난주 월요일~일요일**
- 계산 데이터:
  -  주간 요약 카드: 총/평균 칼로리, 목표 달성률(%), 베스트/워스트 데이
  -  일자별 추이(chart_data): 칼로리, 단백질, 지방, 탄수화물, 나트륨
  -  일자별 비교(daily_breakdown): 요일별 수치 + 목표 달성률(%)

옵션:
- `offset_weeks`:
  - `1` (기본): 지난주
  - `0`: 이번주
  - `2`: 지지난주
""")
def get_weekly_report(
    username: str,
    offset_weeks: int = Query(1, ge=0, le=8, description="0=이번주, 1=지난주(기본), 2=지지난주 ..."),
    db: Session = Depends(get_db)
):
    report = build_weekly_report(db, username=username, offset_weeks=offset_weeks)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report
