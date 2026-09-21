from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.books import router as books_router
from app.api.imports import router as imports_router
from app.api.items import router as items_router
from app.api.library import router as library_router
from app.api.practice import router as practice_router
from app.api.progress import router as progress_router
from app.api.study import router as study_router
from app.api.vocabulary_order import router as vocabulary_order_router

app = FastAPI(title="Japanese Mastery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://japanesemastery.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books_router)
app.include_router(items_router)
app.include_router(library_router)
app.include_router(practice_router)
app.include_router(progress_router)
app.include_router(imports_router)
app.include_router(study_router)
app.include_router(vocabulary_order_router)


@app.get("/health")
def health():
    return {"ok": True}
