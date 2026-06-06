# BatchDock macOS

## Requirements

Install:

- Python 3.11 or newer
- Either Docker Desktop **or** a local Redis installation

## 1. Unpack the archive

```bash
unzip batch_dock.zip
cd batch_dock
```

## 2. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

## 3. Start Redis

```bash
./scripts/start_redis_docker.sh
docker exec -it batchdock-redis redis-cli ping
```

Expected reply:

```text
PONG
```

## 4. Start the worker

Open a new terminal in `batch_dock`:

```bash
source .venv/bin/activate
celery -A make_celery.celery_app worker --loglevel=INFO --pool=solo
```

Keep this terminal running.

## 5. Start the dashboard

Open another terminal in `batch_dock`:

```bash
source .venv/bin/activate
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 6. Verify the project

Run the environment helper:

```bash
./scripts/check_environment.sh
```

Run automated tests:

```bash
./scripts/run_tests.sh
```

Then follow `MANUAL_TESTING.md` for the browser walkthrough.

## Local configuration

The default `.env` file works for a normal local run. Change values only when needed:

```text
SECRET_KEY=replace-this-with-a-random-local-development-value
REDIS_URL=redis://localhost:6379/0
DATABASE_PATH=instance/batchdock.sqlite3
UPLOAD_FOLDER=instance/uploads
WORKER_PING_TIMEOUT=0.5
JOB_HISTORY_LIMIT=100
FLASK_DEBUG=1
```

Replace the example `SECRET_KEY` before sharing or deploying the app anywhere. Do not commit `.env`.
