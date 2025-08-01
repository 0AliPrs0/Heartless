from fastapi import FastAPI
# from .database import engine
from . import models

# models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BlackHeart Game API")

@app.get("/")
def read_root():
    return {"Project": "BlackHeart", "Status": "Development"}