(() => {
  const byId = (id) => document.getElementById(id);
  const terminalStatuses = new Set(["finished", "failed", "cancelled"]);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Unexpected request error.");
    return data;
  }

  function badge(job) {
    return `<span class="badge badge-${escapeHtml(job.status)}">${escapeHtml(job.status_label)}</span>`;
  }

  function actionButtons(job) {
    const actions = [
      `<a class="button table-button" href="/jobs/${encodeURIComponent(job.id)}">View details</a>`,
    ];
    if (job.actions.can_retry) actions.push(`<button class="button table-button" data-action="retry" data-job-id="${escapeHtml(job.id)}">Retry</button>`);
    if (job.actions.can_cancel) actions.push(`<button class="button table-button warning" data-action="cancel" data-job-id="${escapeHtml(job.id)}">Cancel</button>`);
    if (job.actions.can_remove) actions.push(`<button class="button table-button danger" data-action="remove" data-job-id="${escapeHtml(job.id)}">Remove</button>`);
    return actions.join(" ");
  }

  function progressCell(job) {
    return `
      <div class="table-progress"><span style="width:${Number(job.progress)}%"></span></div>
      <small>${Number(job.progress)}% · ${escapeHtml(job.stage)}</small>
    `;
  }

  function renderJobs(jobs) {
    const body = byId("jobs-body");
    if (!body) return;
    if (!jobs.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-state">No jobs match the current view.</td></tr>';
      return;
    }
    body.innerHTML = jobs.map((job) => `
      <tr>
        <td><a class="job-link" href="/jobs/${encodeURIComponent(job.id)}">${escapeHtml(job.description)}</a><small class="mono">${escapeHtml(job.id)}</small></td>
        <td>${escapeHtml(job.task_type_label)}</td>
        <td>${badge(job)}</td>
        <td class="progress-column">${progressCell(job)}</td>
        <td>${escapeHtml(formatTime(job.created_at))}</td>
        <td class="actions-column">${actionButtons(job)}</td>
      </tr>
    `).join("");
  }

  function renderCounts(counts) {
    ["waiting", "in_progress", "finished", "failed", "cancelled"].forEach((status) => {
      const element = byId(`count-${status.replace("_", "-")}`);
      if (element) element.textContent = counts[status] ?? 0;
    });
  }

  async function loadJobs() {
    const search = byId("search-jobs")?.value.trim() || "";
    const status = byId("filter-status")?.value || "";
    const params = new URLSearchParams({ search, status });
    try {
      const data = await requestJson(`/api/jobs?${params.toString()}`);
      renderJobs(data.jobs);
      renderCounts(data.counts);
    } catch (error) {
      const body = byId("jobs-body");
      if (body) body.innerHTML = `<tr><td colspan="6" class="empty-state error-text">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  function renderWorkerStatus(status) {
    const card = byId("worker-card");
    if (!card) return;
    card.className = `worker-card ${status.available ? "available" : "unavailable"}`;
    const title = status.available
      ? `${status.worker_count} worker${status.worker_count === 1 ? "" : "s"} available`
      : "No worker reply received";
    const names = status.workers.length ? `<small>${status.workers.map(escapeHtml).join(", ")}</small>` : "";
    card.innerHTML = `
      <span class="status-dot"></span>
      <div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(status.message)}</p>${names}<small>Checked ${escapeHtml(formatTime(status.checked_at))}</small></div>
    `;
  }

  async function loadWorkerStatus() {
    try {
      const data = await requestJson("/api/worker-status");
      renderWorkerStatus(data.worker_status);
    } catch (error) {
      renderWorkerStatus({ available: false, worker_count: 0, workers: [], checked_at: new Date().toISOString(), message: error.message });
    }
  }

  async function submitJob(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const status = byId("form-status");
    const button = form.querySelector('button[type="submit"]');
    status.textContent = "Submitting…";
    status.className = "form-status";
    button.disabled = true;
    try {
      const data = await requestJson("/api/jobs", { method: "POST", body: new FormData(form) });
      status.textContent = `Queued ${data.job.id}.`;
      status.className = "form-status success-text";
      await loadJobs();
    } catch (error) {
      status.textContent = error.message;
      status.className = "form-status error-text";
    } finally {
      button.disabled = false;
    }
  }

  async function performAction(action, jobId) {
    const messages = {
      retry: "Queue a new retry job for this failed record?",
      cancel: "Cancel this waiting job? Running jobs cannot be cancelled from this dashboard.",
      remove: "Remove this terminal job record from local history?",
    };
    if (!window.confirm(messages[action])) return;

    const options = action === "remove" ? { method: "DELETE" } : { method: "POST" };
    const suffix = action === "remove" ? "" : `/${action}`;
    try {
      await requestJson(`/api/jobs/${encodeURIComponent(jobId)}${suffix}`, options);
      await loadJobs();
      if (byId("job-details-page")) {
        if (action === "remove") window.location.assign("/");
        else await loadJobDetails();
      }
    } catch (error) {
      window.alert(error.message);
    }
  }

  function handleActionClick(event) {
    const button = event.target.closest("[data-action][data-job-id]");
    if (!button) return;
    performAction(button.dataset.action, button.dataset.jobId);
  }

  function toggleTaskFields() {
    const isCsv = byId("task-type")?.value === "csv_summary";
    byId("demo-fields")?.classList.toggle("hidden", isCsv);
    byId("csv-fields")?.classList.toggle("hidden", !isCsv);
  }

  function renderEvents(events) {
    const list = byId("event-log");
    if (!list) return;
    list.innerHTML = events.map((event) => `
      <li class="event-${escapeHtml(event.level)}">
        <span>${escapeHtml(formatTime(event.time))}</span>
        <p>${escapeHtml(event.message)}</p>
      </li>
    `).join("");
  }

  function renderDetailActions(job) {
    const target = byId("detail-actions");
    if (!target) return;
    target.innerHTML = actionButtons(job);
  }

  function renderJobDetails(job) {
    byId("detail-description").textContent = job.description;
    byId("detail-status").outerHTML = `<span id="detail-status" class="badge badge-${escapeHtml(job.status)}">${escapeHtml(job.status_label)}</span>`;
    byId("detail-progress").textContent = `${job.progress}%`;
    byId("detail-progress-bar").style.width = `${job.progress}%`;
    byId("detail-stage").textContent = job.stage;
    byId("detail-type").textContent = job.task_type_label;
    byId("detail-celery-id").textContent = job.celery_task_id || "Pending assignment";
    byId("detail-created").textContent = formatTime(job.created_at);
    byId("detail-started").textContent = formatTime(job.started_at);
    byId("detail-completed").textContent = formatTime(job.completed_at);
    byId("detail-output").textContent = job.output ? JSON.stringify(job.output, null, 2) : "No output available yet.";
    byId("detail-error").textContent = job.error_message || "No failure recorded.";
    renderEvents(job.events);
    renderDetailActions(job);
  }

  async function loadJobDetails() {
    const page = byId("job-details-page");
    if (!page) return;
    try {
      const data = await requestJson(`/api/jobs/${encodeURIComponent(page.dataset.jobId)}`);
      renderJobDetails(data.job);
    } catch (error) {
      byId("detail-stage").textContent = error.message;
    }
  }

  function debounce(callback, delay = 250) {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => callback(...args), delay);
    };
  }

  document.addEventListener("DOMContentLoaded", () => {
    const form = byId("job-form");
    if (form) {
      form.addEventListener("submit", submitJob);
      byId("task-type").addEventListener("change", toggleTaskFields);
      byId("refresh-dashboard").addEventListener("click", loadJobs);
      byId("refresh-worker").addEventListener("click", loadWorkerStatus);
      byId("filter-status").addEventListener("change", loadJobs);
      byId("search-jobs").addEventListener("input", debounce(loadJobs));
      document.addEventListener("click", handleActionClick);
      toggleTaskFields();
      loadJobs();
      loadWorkerStatus();
      window.setInterval(loadJobs, 3000);
      window.setInterval(loadWorkerStatus, 12000);
    }

    if (byId("job-details-page")) {
      document.addEventListener("click", handleActionClick);
      loadJobDetails();
      window.setInterval(loadJobDetails, 2500);
    }
  });
})();
