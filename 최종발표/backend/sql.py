
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Row

DB_USER = os.getenv("DB_USER", "app")
DB_PASS = os.getenv("DB_PASS", "apppw")
DB_HOST = os.getenv("DB_HOST", "localhost")  
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "foodrec")

ENGINE: Engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4",
    pool_pre_ping=True, future=True
)

def fetch_one(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with ENGINE.connect() as conn:
        row: Optional[Row] = conn.execute(text(sql), params or {}).fetchone()
        return dict(row._mapping) if row else None

def fetch_all(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    with ENGINE.connect() as conn:
        rows = conn.execute(text(sql), params or {}).fetchall()
        return [dict(r._mapping) for r in rows]
