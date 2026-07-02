FROM python:3.11-slim

# FFmpegおよび必須パッケージのインストール
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードのコピー
COPY server.py .

# ダウンロード一時フォルダの作成
RUN mkdir downloads

EXPOSE 8080

# UvicornでFastAPIを起動
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
