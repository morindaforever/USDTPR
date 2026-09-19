# Local setup used for Section 1 verification (macOS, Intel)

This machine had no Python, Git CLI tools, Homebrew, or Docker installed, so
Section 1 was verified with a fully user-space toolchain (no admin rights):

## Toolchain

- **Miniforge** installed to `~/miniforge3` (conda installer, no admin).
- Conda env at `~/miniforge3/envs/usdt` containing:
  - Python 3.11.16
  - PostgreSQL 16.15 (`postgres`, `psql`, `pg_ctl`, `initdb`)
  - Redis 8.10.1 (`redis-server`, `redis-cli`)
  - All Python deps from `backend/requirements.txt` (installed with the
    env's pip, so no global site-packages are touched).

## Exact commands used

```bash
# One-time toolchain
curl -fsSL -o /tmp/miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh
bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
~/miniforge3/bin/conda create -y -p ~/miniforge3/envs/usdt -c conda-forge --override-channels python=3.11 postgresql=16
~/miniforge3/bin/conda install -y -p ~/miniforge3/envs/usdt -c conda-forge --override-channels redis-server
~/miniforge3/envs/usdt/bin/pip install -r backend/requirements.txt

# PostgreSQL (data dir in home, trust auth for local dev)
~/miniforge3/envs/usdt/bin/initdb -D ~/pgdata_usdt -U usdt_platform --auth=trust --encoding=UTF8
~/miniforge3/envs/usdt/bin/pg_ctl -D ~/pgdata_usdt -l ~/pgdata_usdt.log -o "-p 5432" start
~/miniforge3/envs/usdt/bin/createdb -U usdt_platform -h localhost usdt_platform

# Redis
~/miniforge3/envs/usdt/bin/redis-server --daemonize yes --port 6379

# Backend
cd backend && cp .env.example .env
~/miniforge3/envs/usdt/bin/python manage.py migrate
~/miniforge3/envs/usdt/bin/python manage.py runserver 127.0.0.1:8000

# Celery worker
~/miniforge3/envs/usdt/bin/python -m celery -A config worker -l info --pool=solo

# Frontend
cd frontend && npm install && npm run dev
```

## Everyday shortcuts

With the env on your PATH this reduces to the standard commands in the
root `README.md`. To activate the env in a shell:

```bash
conda activate ~/miniforge3/envs/usdt
```

## Notes

- Docker is not installed on this machine, so `docker-compose.yml` is
  provided but was validated by review, not by a live `docker compose up`.
- Git: `/usr/local/bin/git` exists (2.33.0) but Apple's Command Line Tools
  stubs shadow `git` on PATH; use `/usr/local/bin/git` or install CLT when
  initializing the repository.
