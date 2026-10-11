# Clique, for hosts that run containers (Railway, Render, Fly.io...). No packages to install:
# the server uses only Python's standard library, and the website is plain files (no build step).
FROM python:3.12-slim

# CLIQUE_ENV=production makes the server refuse to start without your own ADMIN_PASSWORD.
# DATA_DIR is where the database lives: attach a persistent volume at /data on your host.
ENV CLIQUE_ENV=production \
    DATA_DIR=/data \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The commit this image was built from, for GET /api/salud (Render gives RENDER_GIT_COMMIT by itself).
ARG CLIQUE_COMMIT=""
ENV CLIQUE_COMMIT=${CLIQUE_COMMIT}

WORKDIR /app
COPY server.py ./
COPY backend ./backend
COPY static ./static

# The host provides PORT. Stay a single copy: the database is one file and lives in memory.
CMD ["python3", "server.py"]
