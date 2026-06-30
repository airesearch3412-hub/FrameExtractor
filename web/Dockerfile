# FrameExtractor 網站版 — 生產映像
# build context 必須是 repo 根目錄（才能 COPY 根目錄的 deduper.py）：
#   docker build -f web/Dockerfile -t frameextractor-web .
#   docker build -f web/Dockerfile --build-arg INSTALL_CLIP=1 -t frameextractor-web .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    FE_DATA_DIR=/data \
    PIP_NO_CACHE_DIR=1

# 系統依賴：ffmpeg（影片解碼）、libglib2.0-0（opencv-python-headless 執行期所需）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先裝基礎依賴（不含 CLIP），最大化 layer cache
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install -r /app/web/requirements.txt

# 選用：CLIP / torch（ultra 等級語意去重）。預設不裝以保持映像精簡。
#   --build-arg INSTALL_CLIP=1 才會安裝重依賴
ARG INSTALL_CLIP=0
COPY web/requirements-clip.txt /app/web/requirements-clip.txt
RUN if [ "$INSTALL_CLIP" = "1" ]; then \
        pip install -r /app/web/requirements-clip.txt; \
    fi

# 應用程式碼：重用根目錄 deduper.py + web 套件
COPY deduper.py /app/deduper.py
COPY web /app/web

EXPOSE 8000
VOLUME ["/data"]

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
