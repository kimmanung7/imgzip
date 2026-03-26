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
import random
import asyncio
from pathlib import Path

app = FastAPI(title="Imgzip")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PIXABAY_API_KEY     = os.getenv("PIXABAY_API_KEY", "")
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY", "")

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

jobs: dict = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/start")
async def start_download(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    query = body.get("query", "").strip()
    count = min(int(body.get("count", 10)), 500)

    if not query:
        return {"error": "검색어를 입력해주세요"}

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "total": count,
        "done": 0,
        "zip_path": None,
        "error": None,
        "query": query,
    }

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
    return FileResponse(
        job["zip_path"],
        media_type="application/zip",
        filename=f"{job['query']}.zip"
    )


# ── Unsplash ──────────────────────────────────────────────────────────────────
async def fetch_unsplash(client: httpx.AsyncClient, query: str, count: int) -> list:
    if not UNSPLASH_ACCESS_KEY:
        return []
    try:
        r = await client.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "page": 1, "client_id": UNSPLASH_ACCESS_KEY},
            timeout=15,
        )
        r.raise_for_status()
        total_pages = max(1, r.json().get("total_pages", 1))

        urls = []
        per_page = 30
        pages_needed = -(-count // per_page)

        for _ in range(pages_needed):
            page = random.randint(1, min(total_pages, 20))
            r = await client.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": per_page, "page": page, "client_id": UNSPLASH_ACCESS_KEY},
                timeout=15,
            )
            r.raise_for_status()
            for p in r.json().get("results", []):
                urls.append(p["urls"]["regular"])
            if len(urls) >= count:
                break

        return list(dict.fromkeys(urls))[:count]
    except Exception:
        return []


# ── Pixabay ───────────────────────────────────────────────────────────────────
async def fetch_pixabay(client: httpx.AsyncClient, query: str, count: int) -> list:
    if not PIXABAY_API_KEY:
        return []
    try:
        r = await client.get(
            "https://pixabay.com/api/",
            params={"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "page": 1, "image_type": "photo"},
            timeout=15,
        )
        r.raise_for_status()
        total_hits = r.json().get("totalHits", 0)
        total_pages = max(1, total_hits // 20)

        urls = []
        per_page = 20
        pages_needed = -(-count // per_page)

        for _ in range(pages_needed):
            page = random.randint(1, min(total_pages, 20))
            r = await client.get(
                "https://pixabay.com/api/",
                params={"key": PIXABAY_API_KEY, "q": query, "per_page": per_page, "page": page, "image_type": "photo"},
                timeout=15,
            )
            r.raise_for_status()
            for p in r.json().get("hits", []):
                urls.append(p["largeImageURL"])
            if len(urls) >= count:
                break

        return list(dict.fromkeys(urls))[:count]
    except Exception:
        return []


# ── Pexels ────────────────────────────────────────────────────────────────────
async def fetch_pexels(client: httpx.AsyncClient, query: str, count: int) -> list:
    if not PEXELS_API_KEY:
        return []
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        per_page = 80
        pages_needed = -(-count // per_page)

        urls = []
        for _ in range(pages_needed):
            page = random.randint(1, 20)
            r = await client.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "per_page": per_page, "page": page},
                timeout=15,
            )
            r.raise_for_status()
            for p in r.json().get("photos", []):
                urls.append(p["src"]["large"])
            if len(urls) >= count:
                break

        return list(dict.fromkeys(urls))[:count]
    except Exception:
        return []


# ── 메인 다운로드 작업 ─────────────────────────────────────────────────────────
async def run_download(job_id: str, query: str, count: int):
    try:
        async with httpx.AsyncClient() as client:
            unsplash_urls, pixabay_urls, pexels_urls = await asyncio.gather(
                fetch_unsplash(client, query, count),
                fetch_pixabay(client, query, count),
                fetch_pexels(client, query, count),
            )

        # 합치기 → 셔플 → 중복 제거 → count장 자르기
        all_urls = unsplash_urls + pixabay_urls + pexels_urls
        random.shuffle(all_urls)
        all_urls = list(dict.fromkeys(all_urls))[:count]

        if not all_urls:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = "검색 결과가 없습니다"
            return

        jobs[job_id]["total"] = len(all_urls)

        safe_query = query.replace("/", "_").replace("\\", "_")
        job_dir = DOWNLOAD_DIR / safe_query
        job_dir.mkdir(exist_ok=True)

        async with httpx.AsyncClient() as client:
            for i, url in enumerate(all_urls):
                try:
                    filename = f"{i+1:03d}_{safe_query}_{i}.jpg"
                    filepath = job_dir / filename
                    img_resp = await client.get(url, timeout=30, follow_redirects=True)
                    img_resp.raise_for_status()
                    filepath.write_bytes(img_resp.content)
                except Exception:
                    pass

                jobs[job_id]["done"] = i + 1

        zip_path = DOWNLOAD_DIR / f"{safe_query}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_file in job_dir.iterdir():
                zf.write(img_file, img_file.name)

        for f in job_dir.iterdir():
            f.unlink()
        job_dir.rmdir()

        jobs[job_id]["status"] = "done"
        jobs[job_id]["zip_path"] = str(zip_path)

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)