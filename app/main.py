from fastapi import FastAPI
from .database import engine
from . import models
from .routers import auth, games

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BlackHeart Game API")

app.include_router(auth.router)
app.include_router(games.router)

@app.get("/")
def read_root():
    return {"Project": "BlackHeart", "Status": "Development"}