from fastapi import APIRouter
from app.modules.indexing import index_all
from app.modules.rag import query_rag

router = APIRouter()

@router.get("/index")
def index():
    index_all()
    return {"status": "indexed"}

@router.post("/query")
def query(payload: dict):
    return query_rag(payload)