# BatchDock Manual Verification Checklist

Run these checks after unpacking the repository on macOS.

## Fresh installation

- [ ] `python3 --version` reports Python 3.11 or newer.
- [ ] `python3 -m venv .venv` creates the virtual environment.
- [ ] `source .venv/bin/activate` activates it.
- [ ] `python -m pip install -r requirements-dev.txt` completes successfully.
- [ ] `cp .env.example .env` creates local configuration.

## Redis

- [ ] Start Redis locally or run `./scripts/start_redis_docker.sh`.
- [ ] Run `redis-cli ping` for a local installation or `docker exec -it batchdock-redis redis-cli ping` for Docker.
- [ ] Confirm the reply is `PONG`.

## Worker and web app

- [ ] In terminal 2, run `celery -A make_celery.celery_app worker --loglevel=INFO --pool=solo`.
- [ ] Confirm the worker lists `batchdock.run_demo_workload` and `batchdock.analyze_csv_file`.
- [ ] In terminal 3, run `python app.py`.
- [ ] Open `http://127.0.0.1:5000`.
- [ ] Confirm the worker card reports at least one worker reply.

## Successful timed workload

- [ ] Submit a timed workload with 8 steps, 1 second per step, no start delay, and failure step 0.
- [ ] Confirm a waiting or in-progress record appears.
- [ ] Open job details.
- [ ] Confirm the progress bar and stage text update.
- [ ] Confirm the final state becomes **Finished**.
- [ ] Confirm the output includes `steps_completed` and `seconds_per_step`.

## Controlled failure and retry

- [ ] Submit a timed workload with 6 steps and failure step 3.
- [ ] Confirm the job becomes **Failed**.
- [ ] Open job details and confirm the message identifies the controlled failure step.
- [ ] Click **Retry** and confirm a new linked job record appears.
- [ ] Confirm the deliberate failure control is disabled for the retry and the rerun can finish.

## Waiting-job cancellation

- [ ] Submit a timed workload with a 20-second start delay.
- [ ] Click **Cancel** before execution starts.
- [ ] Confirm the record becomes **Cancelled**.
- [ ] Confirm the event log explains that cancellation was requested while waiting.

## CSV summary

- [ ] Choose **CSV summary analysis**.
- [ ] Upload `sample_data/example_metrics.csv`.
- [ ] Confirm the job finishes.
- [ ] Confirm the output reports 5 rows, 5 columns, and numeric summaries.
- [ ] Try an empty CSV and confirm the failure message is understandable.
- [ ] Try a non-CSV extension and confirm the form rejects it.

## Dashboard behavior

- [ ] Search for part of a description.
- [ ] Search for a local job ID.
- [ ] Filter by **Finished**, **Failed**, and **Cancelled**.
- [ ] Click **Refresh queue**.
- [ ] Remove a terminal record.
- [ ] Confirm an active job cannot be removed.
- [ ] Confirm empty or invalid submissions produce readable messages.

## Automated suite

- [ ] Run `./scripts/run_tests.sh`.
- [ ] Confirm all tests pass.

## Codebase inspection

- [ ] Confirm `.env` is ignored by Git.
- [ ] Confirm no real credentials are present.
- [ ] Confirm Redis settings come from environment variables.
- [ ] Confirm README commands match your local run sequence.
- [ ] Confirm the footer and README describe the app as a local learning project, not a real HPC scheduler.
