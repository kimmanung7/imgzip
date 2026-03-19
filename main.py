from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os
import zipfile
import uuid
from pathlib import Path

app = FastAPI(title="Imgzip")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "YOUR_ACCESS_KEY_HERE")
UNSPLASH_API = "https://api.unsplash.com"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# job_id → { status, total, done, zip_path, error }
jobs: dict = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/start")
async def start_download(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    query = body.get("query", "").strip()
    count = min(int(body.get("count", 10)), 30)  # 최대 30장

    if not query:
        return {"error": "검색어를 입력해주세요"}

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "total": count, "done": 0, "zip_path": None, "error": None, "query": query}

    background_tasks.add_task(run_download, job_id, query, count)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "존재하지 않는 작업입니다"}
    return job


@app.get("/api/download/{job_id}")
async def download_zip(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return {"error": "아직 준비되지 않았습니다"}
    zip_path = job["zip_path"]
    return FileResponse(zip_path, media_type="application/zip", filename=f"{job['query']}.zip")


async def run_download(job_id: str, query: str, count: int):
    try:
        # 1. Unsplash에서 이미지 URL 목록 수집
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{UNSPLASH_API}/search/photos",
                params={
                    "query": query,
                    "per_page": count,
                    "page": 1,
                    "client_id": UNSPLASH_ACCESS_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

        if not results:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = "검색 결과가 없습니다"
            return

        # 2. 작업 폴더 생성
        job_dir = DOWNLOAD_DIR / query
        job_dir.mkdir(exist_ok=True)

        # 3. 이미지 개별 다운로드
        async with httpx.AsyncClient() as client:
            for i, photo in enumerate(results):
                img_url = photo["urls"]["regular"]
                photographer = photo["user"]["name"].replace(" ", "_")
                filename = f"{i+1:02d}_{photographer}_{photo['id']}.jpg"
                filepath = job_dir / filename

                img_resp = await client.get(img_url, timeout=30)
                img_resp.raise_for_status()
                filepath.write_bytes(img_resp.content)

                jobs[job_id]["done"] = i + 1

        # 4. ZIP 압축
        zip_path = DOWNLOAD_DIR / f"{query}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_file in job_dir.iterdir():
                zf.write(img_file, img_file.name)

        # 5. 임시 폴더 정리
        for f in job_dir.iterdir():
            f.unlink()
        job_dir.rmdir()

        jobs[job_id]["status"] = "done"
        jobs[job_id]["zip_path"] = str(zip_path)

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
