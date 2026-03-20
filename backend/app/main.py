from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.modules.vector_store import load_index

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ THIS LINE IS CRITICAL
app.include_router(router)


@app.get("/")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    load_index()
    print("✅ FAISS index + metadata loaded")