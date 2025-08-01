from fastapi import FastAPI
from .database import engine
from . import models
from .routers import auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BlackHeart Game API")

app.include_router(auth.router)

@app.get("/")
def read_root():
    return {"Project": "BlackHeart", "Status": "Development"}