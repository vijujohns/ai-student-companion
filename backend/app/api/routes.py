from fastapi import APIRouter, UploadFile, File
from app.modules.ingestion import process_pdf
from app.modules.indexing import index_documents
from app.modules.rag import query_rag

router = APIRouter()

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    path = f"data/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())
    process_pdf(path)
    return {"status": "uploaded"}

@router.post("/index")
def index():
    index_documents()
    return {"status": "indexed"}

@router.post("/query")
def query(payload: dict):
    return query_rag(payload)
