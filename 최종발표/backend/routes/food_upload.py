
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from datetime import datetime
import secrets, shutil, io 
from PIL import Image, UnidentifiedImageError

from backend.database import get_db
from backend.utils.inference import detect_food_labels
from backend.utils.nutrition_matcher import (
    find_food_by_name, food_per_serving_dict, scale_nutrients
)

router = APIRouter(prefix="/food")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload")
async def upload_food(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),

    username: str = Form(..., description="로그인한 사용자명"),
    meal_index: int = Form(..., description="1=아침,2=점심,3=저녁,4=간식"),
    servings: float = Form(1.0, description="인분 수(기본 1.0, 소수 허용)")
):
    # ─────────────────────────────────────
    # 0) 입력 검증
    # ─────────────────────────────────────
    if servings <= 0 or servings > 10:
        raise HTTPException(status_code=422, detail="servings must be in (0, 10].")
    if meal_index not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="meal_index must be one of {1,2,3,4}.")

    user_row = db.execute(
        text("SELECT id, meals_per_day FROM users WHERE username = :u"),
        {"u": username.strip()}
    ).fetchone()
    if not user_row:
        raise HTTPException(status_code=404, detail=f"사용자 '{username}'를 찾을 수 없습니다.")
    user_id, meals_per_day = user_row

    # ─────────────────────────────────────
    # 1) daily_plan 존재 보장
    # ─────────────────────────────────────
    cnt_row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM daily_plan
            WHERE user_id = :user_id AND DATE(plan_date) = CURDATE()
        """),
        {"user_id": user_id}
    ).fetchone()
    if (cnt_row[0] if cnt_row else 0) == 0:
        total_meals = meals_per_day or 3
        db.execute(
            text("""
                INSERT INTO daily_plan (user_id, plan_date, total_meals)
                VALUES (:user_id, CURDATE(), :total_meals)
            """),
            {"user_id": user_id, "total_meals": total_meals}
        )
        db.commit()

    # ─────────────────────────────────────
    # 2) 파일 저장 (바이트 검증 후 저장)
    # ─────────────────────────────────────
    raw = await file.read()
    if not raw or len(raw) < 100:  
        raise HTTPException(status_code=400, detail="업로드된 파일이 비어있거나 손상되었습니다.")

    # Pillow로 먼저 열어 유효성 확인 + RGB 강제
    try:
        pil = Image.open(io.BytesIO(raw))
        pil.load()  
        pil = pil.convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=415, detail="이미지로 판별할 수 없는 파일 형식입니다(JPG/PNG 권장).")
    except Exception as e:
        raise HTTPException(status_code=415, detail=f"이미지 처리 중 오류: {e}")

    # 확장자 결정: PIL 포맷 기준
    pil_fmt = (pil.format or "").upper()
    ext_by_fmt = { "JPEG": ".jpg", "JPG": ".jpg", "PNG": ".png", "WEBP": ".jpg" }
    suffix = ext_by_fmt.get(pil_fmt, None)
    if not suffix:  # 업로드 파일명으로 보조 결정
        suffix = Path(file.filename or "").suffix.lower() or ".jpg"
        if suffix not in {".jpg", ".jpeg", ".png"}:
            suffix = ".jpg"

    safe_name = f"{secrets.token_hex(8)}{suffix}"
    dst = UPLOAD_DIR / safe_name

    # 디스크에 저장 (검증된 이미지)
    try:
        pil.save(dst)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 저장에 실패했습니다: {e}")

    if not dst.exists() or dst.stat().st_size < 100:
        raise HTTPException(status_code=500, detail="이미지 저장에 실패했습니다.")

    # ─────────────────────────────────────
    # 3) 모델 추론
    # ─────────────────────────────────────
    try:
        result = detect_food_labels(
            str(dst),
            aggregate=False,
            min_prob=0.20,
            yolo_iou=0.80,
            merge_boxes=False,
            require_ae=True, 
        ) or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"탐지 모델 실행 중 오류: {e}")

    detections = result.get("detections") or []
    if not detections:
        raise HTTPException(status_code=422, detail="탐지된 음식이 없습니다.")

    MAX_DETS = 12
    detections = sorted(
        detections, key=lambda d: float(d.get("prob", 0.0)), reverse=True
    )[:MAX_DETS]

    # ─────────────────────────────────────
    # 4) DB 매칭 & food_logs 기록 + 영양 계산
    # ─────────────────────────────────────
    matched_results = []
    for det in detections:
        label = det.get("label")
        prob  = float(det.get("prob", 0.0))
        if not label:
            continue

        # DB의 foods 테이블에서 이름/유사어 매칭
        food = find_food_by_name(db, label)
        if not food:
            continue

        servings_each = float(servings)

        # 로그 저장
        db.execute(
            text("""
                INSERT INTO food_logs
                    (user_id, food_id, servings, consumed_at, meal_index, source, note, image_url)
                VALUES
                    (:user_id, :food_id, :servings, :consumed_at, :meal_index, :source, :note, :image_url)
            """),
            {
                "user_id": user_id,
                "food_id": food.id,
                "servings": servings_each,
                "consumed_at": datetime.now(),
                "meal_index": meal_index,
                "source": "ml_auto",
                "note": f"Detected automatically from image: {file.filename} (prob={prob:.2f})",
                "image_url": str(dst),
            }
        )

        # 1인분 / 총량(인분 반영) 계산
        per_serv = food_per_serving_dict(food)  # {'kcal','carb_g','protein_g','fat_g', ...}
        total = scale_nutrients(per_serv, servings_each)

        matched_results.append({
            "raw_label": label,
            "confidence": prob,
            "food_id": food.id,
            "food_name": food.name,
            "servings": servings_each,
            "per_serving": per_serv,
            "total_nutrients": total,
        })

    db.commit()

    if not matched_results:
        raise HTTPException(status_code=404, detail="DB에 매칭된 음식이 없습니다.")

    # ─────────────────────────────────────
    # 5) 오늘 누적 합
    # ─────────────────────────────────────
    totals_row = db.execute(
        text("""
            SELECT
              COALESCE(SUM(f.kcal      * l.servings), 0) AS total_kcal,
              COALESCE(SUM(f.protein_g * l.servings), 0) AS total_protein_g,
              COALESCE(SUM(f.fat_g     * l.servings), 0) AS total_fat_g,
              COALESCE(SUM(f.carb_g    * l.servings), 0) AS total_carb_g,
              COALESCE(SUM(f.sugar_g   * l.servings), 0) AS total_sugar_g,
              COALESCE(SUM(f.sodium_mg * l.servings), 0) AS total_sodium_mg,
              COALESCE(SUM(f.fiber_g   * l.servings), 0) AS total_fiber_g
            FROM food_logs l
            JOIN foods f ON f.id = l.food_id
            WHERE l.user_id = :uid AND DATE(l.consumed_at) = CURDATE()
        """),
        {"uid": user_id}
    ).mappings().first() or {}

    # ─────────────────────────────────────
    # 6) 프론트 카드용 요약(summary, top_summary)
    # ─────────────────────────────────────
    summary_items = []
    for item in matched_results[:3]:
        tot = item.get("total_nutrients") or {}
        summary_items.append({
            "food_name": item.get("food_name") or item.get("raw_label"),
            "confidence": round(float(item.get("confidence", 0.0)), 4),
            "servings": float(item.get("servings", 1.0)),
            "kcal": float(tot.get("kcal", 0.0)),
            "carb_g": float(tot.get("carb_g", 0.0)),
            "protein_g": float(tot.get("protein_g", 0.0)),
            "fat_g": float(tot.get("fat_g", 0.0)),
        })

    top_item = matched_results[0]
    top_summary = {
        "food_name": top_item.get("food_name") or top_item.get("raw_label"),
        "confidence": round(float(top_item.get("confidence", 0.0)), 4),
        "servings": float(top_item.get("servings", 1.0)),
        "per_serving": {
            "kcal": float(top_item["per_serving"].get("kcal", 0.0)),
            "carb_g": float(top_item["per_serving"].get("carb_g", 0.0)),
            "protein_g": float(top_item["per_serving"].get("protein_g", 0.0)),
            "fat_g": float(top_item["per_serving"].get("fat_g", 0.0)),
        },
        "total": {
            "kcal": float(top_item["total_nutrients"].get("kcal", 0.0)),
            "carb_g": float(top_item["total_nutrients"].get("carb_g", 0.0)),
            "protein_g": float(top_item["total_nutrients"].get("protein_g", 0.0)),
            "fat_g": float(top_item["total_nutrients"].get("fat_g", 0.0)),
        }
    }

    # ─────────────────────────────────────
    # 7) 응답
    # ─────────────────────────────────────
    return {
        "message": "탐지·매칭 및 food_logs 저장 완료",
        "username": username,
        "user_id": user_id,
        "image_path": str(dst),

        "detected_raw": detections,
        "matched": matched_results,
        "today_totals": totals_row,

        "summary": {"items": summary_items},
        "top_summary": top_summary
    }
