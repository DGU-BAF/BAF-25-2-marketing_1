from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from backend.database import Base, engine
import backend.models  
from backend.routes import auth, food_upload, report, dashboard 
try:
    from backend.routes import recommend as recommend_router
except ImportError:
    from backend.routes import recommend_route as recommend_router


app = FastAPI(
    title="FoodRec API",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

Base.metadata.create_all(bind=engine)

origins_env = os.getenv("FRONT_ORIGINS", "*")  
allow_origins = (
    [o.strip() for o in origins_env.split(",")] if origins_env and origins_env != "*" else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(food_upload.router)
app.include_router(dashboard.router)            
app.include_router(recommend_router.router)      
app.include_router(report.router)


@app.get("/")
def health():
    return {"status": "ok"}
