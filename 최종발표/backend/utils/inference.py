from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
from torchvision import transforms
import timm
from ultralytics import YOLO

# =========================
#  경로 / 기본 설정
# =========================
BASE_DIR     = Path(__file__).resolve().parents[1]
WEIGHTS_DIR  = BASE_DIR / "weights"

YOLO_WEIGHTS = WEIGHTS_DIR / "yolo" / "best.pt"
CLS_WEIGHTS  = WEIGHTS_DIR / "efficientnet" / "cls_food_best.pth"
CLASS_JSON   = WEIGHTS_DIR / "efficientnet" / "class_names.json"

AE_WEIGHTS_DIR = WEIGHTS_DIR

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
IMG_SIZE = 380

# =========================
#  클래스 이름 로드
# =========================
with open(CLASS_JSON, "r", encoding="utf-8") as f:
    CLASS_NAMES: List[str] = json.load(f)
NUM_CLASSES = len(CLASS_NAMES)

# =========================
#  YOLO / 분류기 로드
# =========================
_yolo = YOLO(str(YOLO_WEIGHTS)) if YOLO_WEIGHTS.exists() else None

CLS_ARCH = "tf_efficientnet_b4_ns"
_classifier = timm.create_model(CLS_ARCH, pretrained=False, num_classes=NUM_CLASSES)


def _load_state_dict_safely(model: nn.Module, weight_path: Path):
    """여러 형태(state_dict, model 등) 체크포인트를 안전하게 로드"""
    raw = torch.load(weight_path, map_location="cpu")
    sd = raw
    if isinstance(raw, dict):
        for k in (
            "state_dict",
            "model",
            "net",
            "module",
            "weights",
            "checkpoint",
            "ema_state_dict",
            "ema",
        ):
            if k in raw and isinstance(raw[k], dict):
                sd = raw[k]
                break

    new_sd = {}
    for k, v in sd.items():
        if isinstance(v, torch.Tensor):
            k2 = k
            if k2.startswith("model."):
                k2 = k2[6:]
            if k2.startswith("module."):
                k2 = k2[7:]
            new_sd[k2] = v
    try:
        model.load_state_dict(new_sd, strict=True)
    except Exception:
        model.load_state_dict(new_sd, strict=False)


_load_state_dict_safely(_classifier, CLS_WEIGHTS)
_classifier.eval().to(DEVICE)

# =========================
#  공통 전처리
# =========================
_base_tf = transforms.Compose(
    [
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        ),
    ]
)


@torch.no_grad()
def _predict_probs(pil: Image.Image) -> np.ndarray:
    """단일 이미지 확률 벡터(np.array: [C])"""
    x = _base_tf(pil).unsqueeze(0).to(DEVICE)
    logits = _classifier(x)
    probs = torch.softmax(logits, 1).squeeze(0).detach().cpu().numpy()
    return probs


@torch.no_grad()
def _predict_probs_tta(pil: Image.Image) -> np.ndarray:
    """TTA(horizontal flip) 평균 확률"""
    p1 = _predict_probs(pil)
    p2 = _predict_probs(pil.transpose(Image.FLIP_LEFT_RIGHT))
    return (p1 + p2) / 2.0


# =========================
#  AE(오토인코더) 관련
# =========================
class FeatureAE(nn.Module):
    """EfficientNet feature 벡터를 입력으로 받는 단순 AE"""

    def __init__(self, input_dim: int, hidden_dim: int = 512, bottleneck_dim: int = 128):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, bottleneck_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.decoder(z)


_ae_effnet: Optional[nn.Module] = None
_ae_feat_dim: Optional[int] = None
_ae_models: Dict[str, FeatureAE] = {}


def _get_ae_feature_extractor() -> Tuple[nn.Module, int]:
    """
    AE용 feature extractor (efficientnet_b4, classifier=Identity) lazy 로딩
    """
    global _ae_effnet, _ae_feat_dim
    if _ae_effnet is None:
        effnet = timm.create_model("efficientnet_b4", pretrained=True)
        feat_dim = effnet.classifier.in_features
        effnet.classifier = nn.Identity()
        effnet.to(DEVICE).eval()
        _ae_effnet, _ae_feat_dim = effnet, feat_dim
    return _ae_effnet, _ae_feat_dim  # type: ignore


def _get_ae_model_for_class(class_name: str) -> Tuple[Optional[FeatureAE], Optional[float]]:
    """
    특정 클래스용 AE 모델과 threshold 로딩
    weights/ae_<class>.pth, ae_<class>_threshold.txt 를 찾는다.
    """
    global _ae_models, _ae_feat_dim

    w_path = AE_WEIGHTS_DIR / f"ae_{class_name}.pth"
    t_path = AE_WEIGHTS_DIR / f"ae_{class_name}_threshold.txt"
    if not (w_path.exists() and t_path.exists()):
        return None, None

    if class_name not in _ae_models:
        effnet, feat_dim = _get_ae_feature_extractor()
        ckpt = torch.load(w_path, map_location=DEVICE)

        input_dim = ckpt.get("feat_dim", feat_dim)
        hidden_dim = ckpt.get("hidden_dim", 512)
        bottleneck_dim = ckpt.get("bottleneck_dim", 128)

        ae = FeatureAE(input_dim, hidden_dim, bottleneck_dim).to(DEVICE)
        ae.load_state_dict(ckpt["model"])
        ae.eval()
        _ae_models[class_name] = ae

    with open(t_path, "r", encoding="utf-8") as f:
        thr = float(f.read().strip())

    return _ae_models[class_name], thr


@torch.no_grad()
def _ae_check_crop(
    pil: Image.Image,
    class_name: str,
) -> Tuple[Optional[bool], Optional[float], Optional[float]]:
    """
    단일 crop에 대해:
    - EfficientNet-B4 feature 추출
    - 해당 class용 AE 재구성 오류 계산
    - threshold와 비교해 정상 여부 반환
    AE 가중치가 없으면 (None, None, None)
    """
    effnet, _ = _get_ae_feature_extractor()
    ae, thr = _get_ae_model_for_class(class_name)
    if ae is None or thr is None:
        return None, None, None

    x = _base_tf(pil).unsqueeze(0).to(DEVICE)
    feat = effnet(x)  # [1, D]
    recon = ae(feat)
    err = torch.mean((recon - feat) ** 2).item()
    ok = err < thr
    return ok, err, thr


# =========================
#  YOLO 박스 병합 
# =========================
def _merge_boxes_xyxy(
    boxes: np.ndarray,
    iou_thr: float = 0.80,
    keep_top: int = 20,
) -> np.ndarray:
    """
    boxes: (N,6) = [x1,y1,x2,y2, conf, cls]
    간단 NMS: IoU 기준으로 높은 conf 위주로 남김
    (여러 객체 살리기 위해 iou_thr 기본 0.80로 상향)
    """
    if boxes.size == 0:
        return boxes

    order = boxes[:, 4].argsort()[::-1]
    boxes = boxes[order]
    keep = []
    while len(boxes) > 0:
        cur = boxes[0:1]
        keep.append(cur)
        if len(boxes) == 1:
            break
        rest = boxes[1:]

        x1 = np.maximum(cur[:, 0], rest[:, 0])
        y1 = np.maximum(cur[:, 1], rest[:, 1])
        x2 = np.minimum(cur[:, 2], rest[:, 2])
        y2 = np.minimum(cur[:, 3], rest[:, 3])
        inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        area_cur = (cur[:, 2] - cur[:, 0]) * (cur[:, 3] - cur[:, 1])
        area_rest = (rest[:, 2] - rest[:, 0]) * (rest[:, 3] - rest[:, 1])
        iou = inter / (area_cur + area_rest - inter + 1e-9)
        boxes = rest[iou < iou_thr]
        if len(keep) >= keep_top:
            break
    return np.concatenate(keep, axis=0)


# =========================
#  최종 detect_food_labels
# =========================
@torch.no_grad()
def detect_food_labels(
    img_path: str,
    min_prob: float = 0.20,
    dedup: bool = False,
    yolo_conf: float = 0.25,
    yolo_iou: float = 0.80,
    min_box: int = 16,
    topk_limit: int = 5,
    merge_boxes: bool = False,
    aggregate: bool = False,
    require_ae: bool = False,  # AE 통과한 것만 인정할지 여부
) -> Dict[str, Any]:
    """
    aggregate=False  → 박스별 결과를 '그대로' 반환(같은 음식 2개면 2개로 보임)
    aggregate=True   → 라벨로 집계(기존 방식)

    require_ae=True  → AE 재구성 오류를 통과한 crop만 유효한 detection으로 인정
                       (해당 class용 AE 가 없으면 ae_ok=None 이고, 이 경우도 제외)
    """
    pil = Image.open(img_path).convert("RGB")
    W, H = pil.size

    # 1) YOLO 감지
    crops: List[Tuple[Image.Image, float, Tuple[int, int, int, int]]] = []
    detections: List[Dict[str, Any]] = []

    if _yolo is not None:
        rs = _yolo.predict(
            source=pil,
            imgsz=960,
            conf=yolo_conf,
            iou=yolo_iou,
            max_det=50,
            agnostic_nms=True,
            verbose=False,
        )
        r = rs[0]
        boxes = []
        if getattr(r, "boxes", None) is not None and len(r.boxes) > 0:
            xyxy = r.boxes.xyxy.cpu().numpy()
            conf = r.boxes.conf.cpu().numpy()
            cls  = r.boxes.cls.cpu().numpy()
            for (x1, y1, x2, y2), c, cl in zip(xyxy, conf, cls):
                x1 = int(max(0, min(x1, W - 1)))
                y1 = int(max(0, min(y1, H - 1)))
                x2 = int(max(0, min(x2, W)))
                y2 = int(max(0, min(y2, H)))
                if (x2 - x1) < min_box or (y2 - y1) < min_box:
                    continue
                boxes.append([x1, y1, x2, y2, float(c), float(cl)])

        if boxes:
            boxes = np.array(boxes, dtype=float)
            if merge_boxes:
                boxes = _merge_boxes_xyxy(boxes, iou_thr=0.85, keep_top=50)
            for x1, y1, x2, y2, c, _ in boxes:
                crops.append(
                    (
                        pil.crop((int(x1), int(y1), int(x2), int(y2))),
                        float(c),
                        (int(x1), int(y1), int(x2), int(y2)),
                    )
                )

    if not crops:
        crops = [(pil, 1.0, (0, 0, W, H))]

    per_label_scores: Dict[str, float] = {}
    per_label_counts: Dict[str, int] = {}
    items_raw: List[Dict[str, Any]] = []

    total = 0
    for crop, c, (x1, y1, x2, y2) in crops:
        probs = _predict_probs_tta(crop)
        idx = int(probs.argmax())
        lbl = CLASS_NAMES[idx]
        p = float(probs[idx])

        #AE로 한 번 더 검증
        ae_ok: Optional[bool] = None
        if require_ae:
            ok, err, thr = _ae_check_crop(crop, lbl)
            ae_ok = ok
            if not (ok is True):
                detections.append(
                    {
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "label": lbl,
                        "prob": p,
                        "yolo_conf": c,
                        "weight": 0.0,
                        "ae_ok": ae_ok,
                    }
                )
                continue

        area = (max(0, x2 - x1) * max(0, y2 - y1)) / max(1, W * H)
        w = (0.5 + 0.5 * min(1.0, c)) * (0.6 + 0.4 * area)

        det = {
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "label": lbl,
            "prob": p,
            "yolo_conf": c,
            "weight": w,
            "ae_ok": ae_ok,
        }
        detections.append(det)

        items_raw.append({"label": lbl, "confidence": p, "weight": w})
        if p >= min_prob:
            per_label_scores[lbl] = per_label_scores.get(lbl, 0.0) + (p * w)
            per_label_counts[lbl] = per_label_counts.get(lbl, 0) + 1
            total += 1

    # =========================
    #  aggregate=False 분기
    # =========================
    if not aggregate:
        kept = [d for d in detections if d["prob"] >= min_prob] or detections
        labels_list = (
            [d["label"] for d in kept]
            if not dedup
            else list(dict.fromkeys([d["label"] for d in kept]))
        )
        counts: Dict[str, int] = {}
        for d in kept:
            counts[d["label"]] = counts.get(d["label"], 0) + 1

        best: Dict[str, float] = {}
        for d in kept:
            best[d["label"]] = max(best.get(d["label"], 0.0), float(d["prob"]))
        items = [
            {"label": k, "confidence": v}
            for k, v in sorted(best.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "image_path": img_path,
            "labels": labels_list,
            "counts": counts,
            "num_detections": len(kept),
            "items": items,
            "detections": kept,  
        }

    # =========================
    #  aggregate=True 분기
    # =========================
    if not per_label_scores:
        items_raw.sort(key=lambda d: d["confidence"], reverse=True)
        take = min(len(items_raw), 2)
        selected = items_raw[:take]
        labels = [it["label"] for it in selected]
        if dedup:
            labels = list(dict.fromkeys(labels))
        counts: Dict[str, int] = {}
        for it in selected:
            counts[it["label"]] = counts.get(it["label"], 0) + 1
        items = [
            {"label": it["label"], "confidence": float(it["confidence"])}
            for it in selected
        ]
        return {
            "image_path": img_path,
            "labels": labels,
            "counts": counts,
            "num_detections": len(
                [d for d in detections if d["prob"] >= min_prob]
            ),
            "items": items,
            "detections": detections,
        }

    vals = np.array(list(per_label_scores.values()), float)
    m = float(vals.mean())
    s = float(vals.std())
    hard = float(vals.max()) * 0.55
    thr = max(hard, m + 0.5 * s)

    label_items = sorted(
        [{"label": k, "confidence": float(v)} for k, v in per_label_scores.items()],
        key=lambda d: d["confidence"],
        reverse=True,
    )
    filtered = [it for it in label_items if it["confidence"] >= thr] or label_items[:1]
    filtered = filtered[:topk_limit]

    labels = [it["label"] for it in filtered]
    if dedup:
        labels = list(dict.fromkeys(labels))

    return {
        "image_path": img_path,
        "labels": labels,
        "counts": per_label_counts,
        "num_detections": total,
        "items": filtered,
        "detections": detections,
    }
