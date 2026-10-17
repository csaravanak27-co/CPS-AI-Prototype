FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

# Runtime libraries required by PySide6 in a minimal Linux image.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       libdbus-1-3 \
       libegl1 \
       libfontconfig1 \
       libgl1 \
       libglib2.0-0 \
       libx11-xcb1 \
       libxkbcommon0 \
       libxkbcommon-x11-0 \
       libxcb-cursor0 \
       libxcb-icccm4 \
       libxcb-image0 \
       libxcb-keysyms1 \
       libxcb-randr0 \
       libxcb-render-util0 \
       libxcb-shape0 \
       libxcb-shm0 \
       libxcb-xfixes0 \
       libxcb-xinerama0 \
       libxcb-xkb1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock

COPY . .
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation -e . \
    && python -m compileall -q backend cps app.py desktop scripts

EXPOSE 8899
CMD ["python", "-m", "backend.server"]
