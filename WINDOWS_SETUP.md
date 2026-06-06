# BatchDock — Windows Setup Guide

# 1. Install Python

Install Python 3.11 or newer.

Download:
https://www.python.org/downloads/windows/

Enable:
- Add Python to PATH

Verify:

```powershell
python --version
```

---

# 2. Extract the Project

Extract:

```text
batch_dock.zip
```

Open PowerShell in the extracted folder.

Example:

```powershell
cd C:\Users\YourName\Downloads\batch_dock
```

---

# 3. Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\activate
```

---

# 4. Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

---

# 5. Create the Environment File

```powershell
copy .env.example .env
```

---

# 6. Install Docker Desktop

Download:
https://www.docker.com/products/docker-desktop/

Verify:

```powershell
docker --version
```

---

# 7. Start Redis

```powershell
docker run -d --name batchdock-redis -p 6379:6379 redis:7
```

Verify:

```powershell
docker exec -it batchdock-redis redis-cli ping
```

Expected:

```text
PONG
```

---

# 8. Start the Celery Worker

Open a new PowerShell window.

```powershell
cd C:\Users\YourName\Downloads\batch_dock
.\.venv\Scripts\activate
celery -A make_celery.celery_app worker --loglevel=INFO --pool=solo
```

---

# 9. Start the Flask App

Open another PowerShell window.

```powershell
cd C:\Users\YourName\Downloads\batch_dock
.\.venv\Scripts\activate
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

# 10. Run a Demo Job

Queue a workload with:

```text
Steps: 10
Seconds per step: 1
Fail at step: 0
Start delay: 0
```

Expected flow:

```text
Waiting
→
In Progress
→
Finished
```

---

# 11. Run Tests

```powershell
pytest
```

Expected:

```text
13 passed
```

---

# 12. Stop Everything

Press:

```text
CTRL + C
```

inside:
- Redis terminal
- Worker terminal
- Flask terminal

---

# 13. Important Interview Framing

Describe BatchDock as:

```text
A local batch-processing dashboard inspired by research-computing workflows.
```

Do not describe it as:
- a production HPC scheduler
- a Slurm replacement
- a cluster orchestrator
