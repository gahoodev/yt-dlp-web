import os
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="yt-dlp Quickline Backend")

# CORS設定（GitLab Pagesからのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 運用に合わせてGitLab PagesのURLに絞るとより安全です
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 保存先と公開用ディレクトリの作成
OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ジョブの状態をメモリ管理（簡易版キャッシュ）
jobs = {}

class DownloadRequest(BaseModel):
    url: str
    mode: str = "video"
    retries: int = 3
    audioBitrate: int = 192

class YtDlpLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"[yt-dlp ERROR] {msg}")

def progress_hook(d, job_id):
    if job_id not in jobs:
        return
    
    status = d.get('status')
    if status == 'downloading':
        # 進捗率の計算
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        progress = (downloaded / total * 100) if total > 0 else 0
        
        # 速度とETAのパース
        speed_bytes = d.get('speed', 0)
        speed = f"{speed_bytes / 1024 / 1024:.1f} MB/s" if speed_bytes else "-"
        eta_sec = d.get('eta', 0)
        eta = f"{eta_sec}s" if eta_sec else "-"
        
        jobs[job_id].update({
            "status": "downloading",
            "progress": round(progress, 1),
            "speed": speed,
            "eta": eta,
            "message": f"ダウンロード中... ({d.get('filename', '').split('/')[-1]})"
        })
    elif status == 'finished':
        jobs[job_id].update({
            "status": "processing",
            "progress": 95,
            "message": "後処理中（FFmpegによる変換など）..."
        })

def run_yt_dlp(job_id, req: DownloadRequest):
    ydl_opts = {
        'outtmpl': os.path.join(OUTPUT_DIR, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: progress_hook(d, job_id)],
        'retries': req.retries,
        'logger': YtDlpLogger(),
        'impersonate': 'chrome',
        'color': 'no_color',
        'postprocessors': []
    }

    if req.mode == "video":
        ydl_opts["format"] = "bv*+ba/b"
    elif req.mode == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': str(req.audioBitrate)
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            
            # 完了したファイル情報の構築
            files = []
            if 'requested_downloads' in info:
                for dl in info['requested_downloads']:
                    filepath = dl.get('filepath')
                    if filepath and os.path.exists(filepath):
                        filename = os.path.basename(filepath)
                        files.append({
                            "name": filename,
                            "url": f"/files/{filename}",
                            "size": os.path.getsize(filepath)
                        })
            else:
                filepath = ydl.prepare_filename(info)
                # 音声変換された場合は拡張子をmp3に差し替えてチェック
                if req.mode == "audio":
                    filepath = os.path.splitext(filepath)[0] + ".mp3"
                if os.path.exists(filepath):
                    filename = os.path.basename(filepath)
                    files.append({
                        "name": filename,
                        "url": f"/files/{filename}",
                        "size": os.path.getsize(filepath)
                    })

            jobs[job_id].update({
                "status": "done",
                "progress": 100,
                "speed": "-",
                "eta": "-",
                "message": "ダウンロードが完了しました！",
                "files": files
            })
    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error": str(e),
            "message": "エラーが発生しました。"
        })

@app.post("/api/jobs")
def create_job(req: DownloadRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "speed": "-",
        "eta": "-",
        "message": "ジョブを開始します...",
        "files": []
    }
    # バックグラウンド処理としてyt-dlpを実行
    background_tasks.add_task(run_yt_dlp, job_id, req)
    return {"id": job_id}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

# ダウンロード完了したファイルを静的配信する
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)