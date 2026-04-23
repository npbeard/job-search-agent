const els = {
  form: document.getElementById("source-form"),
  marketRefreshButton: document.getElementById("market-refresh-button"),
  profileInput: document.getElementById("profile-input"),
  jobsInput: document.getElementById("jobs-input"),
  contactsInput: document.getElementById("contacts-input"),
  status: document.getElementById("status-bar"),
  summary: document.getElementById("summary-grid"),
  jobs: document.getElementById("jobs-list"),
  searches: document.getElementById("searches-list"),
  drafts: document.getElementById("drafts-list"),
  companyFilter: document.getElementById("company-filter"),
  scoreFilter: document.getElementById("score-filter"),
  scoreFilterValue: document.getElementById("score-filter-value"),
};

let latestPayload = null;

function formatSalary(job) {
  if (job.min_salary_eur == null && job.max_salary_eur == null) return "Salary unknown";
  const low = (job.min_salary_eur ?? job.max_salary_eur).toLocaleString();
  const high = (job.max_salary_eur ?? job.min_salary_eur).toLocaleString();
  return `EUR ${low} - ${high}`;
}

function tag(label, variant = "") {
  return `<span class="tag ${variant}">${label}</span>`;
}

function renderSummary(payload) {
  const items = [
    { value: payload.summary.job_count, label: "ranked jobs" },
    { value: payload.summary.company_count, label: "companies" },
    { value: payload.summary.search_query_count, label: "search queries" },
    { value: payload.summary.outreach_count, label: "outreach pairings" },
  ];
  els.summary.innerHTML = items.map((item) => `
    <article class="summary-card">
      <strong>${item.value}</strong>
      <span>${item.label}</span>
    </article>
  `).join("");
}

function renderJobs(payload) {
  const minScore = Number(els.scoreFilter.value);
  const companyValue = els.companyFilter.value;
  els.scoreFilterValue.textContent = `${minScore.toFixed(2)}+`;
  const jobs = payload.ranked_jobs.filter((item) => item.score >= minScore)
    .filter((item) => companyValue === "all" || item.job.company === companyValue);
  els.jobs.innerHTML = jobs.map((item) => {
    const job = item.job;
    const reasons = item.reasons.slice(0, 5).map((reason) => tag(reason, "good")).join("");
    const skillTags = (job.skills || []).slice(0, 6).map((skill) => tag(skill)).join("");
    return `
      <article class="job-card">
        <div class="card-topline">
          <div>
            <h3>${job.title}</h3>
            <p class="muted">${job.company} · ${job.location}</p>
          </div>
          <span class="score-badge">${item.score.toFixed(2)}</span>
        </div>
        <div class="meta-row">
          ${tag(formatSalary(job))}
          ${tag(job.level)}
          ${tag(job.remote_type)}
          ${tag(`hours: ${job.hours_risk}`, job.hours_risk === "high" ? "warn" : "good")}
          ${tag(`${job.required_years_experience ?? "?"} yrs`)}
        </div>
        <div class="reason-row">${reasons}</div>
        <div class="reason-row">${skillTags}</div>
        <div class="reason-row"><a href="${job.url}" target="_blank" rel="noreferrer">Open role</a></div>
      </article>
    `;
  }).join("");
}

function renderCompanyFilter(payload) {
  const previous = els.companyFilter.value || "all";
  const options = ['<option value="all">All companies</option>']
    .concat(payload.companies.map((company) => `<option value="${company}">${company}</option>`));
  els.companyFilter.innerHTML = options.join("");
  els.companyFilter.value = payload.companies.includes(previous) ? previous : "all";
}

function renderSearches(payload) {
  els.searches.innerHTML = payload.contact_search_queries.slice(0, 12).map((item) => {
    const reasons = item.reasons.map((reason) => tag(reason, "good")).join("");
    return `
      <article class="contact-card">
        <div class="card-topline">
          <div>
            <h3>${item.persona}</h3>
            <p class="muted">${item.company} · ${item.job_title}</p>
          </div>
          <span class="score-badge">${item.score.toFixed(2)}</span>
        </div>
        <div class="meta-row">
          ${tag(item.query)}
        </div>
        <div class="reason-row">${reasons}</div>
        <div class="reason-row"><a href="${item.linkedin_url}" target="_blank" rel="noreferrer">Open LinkedIn search</a></div>
      </article>
    `;
  }).join("");
}

function renderDrafts(payload) {
  els.drafts.innerHTML = payload.outreach_drafts.slice(0, 6).map((item) => `
    <article class="draft-card">
      <div class="card-topline">
        <div>
          <h3>${item.contact_name}</h3>
          <p class="muted">${item.company} · ${item.job_title}</p>
        </div>
        <span class="score-badge">${item.score.toFixed(2)}</span>
      </div>
      <div class="meta-row">
        ${tag(item.subject)}
        <a href="${item.contact_url}" target="_blank" rel="noreferrer">Open contact</a>
      </div>
      <div class="draft-body">${item.message}</div>
    </article>
  `).join("");
}

function setStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.style.color = isError ? "#b42318" : "#667085";
}

async function loadDashboard() {
  const params = new URLSearchParams();
  if (els.profileInput.value.trim()) params.set("profile", els.profileInput.value.trim());
  if (els.jobsInput.value.trim()) params.set("jobs", els.jobsInput.value.trim());
  if (els.contactsInput.value.trim()) params.set("contacts", els.contactsInput.value.trim());
  setStatus("Loading dashboard...");
  const response = await fetch(`/api/dashboard?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    setStatus(payload.error || "Failed to load dashboard.", true);
    return;
  }
  latestPayload = payload;
  renderSummary(payload);
  renderCompanyFilter(payload);
  renderJobs(payload);
  renderSearches(payload);
  renderDrafts(payload);
  setStatus(`Loaded ${payload.summary.job_count} jobs across ${payload.summary.company_count} companies and generated ${payload.summary.search_query_count} referral searches.`);
}

async function refreshMarketData() {
  els.marketRefreshButton.disabled = true;
  setStatus("Refreshing live market data...");
  const response = await fetch("/api/refresh-market", { method: "POST" });
  const payload = await response.json();
  if (!response.ok) {
    els.marketRefreshButton.disabled = false;
    setStatus(payload.error || "Failed to refresh market data.", true);
    return;
  }
  if (!els.jobsInput.value.trim()) {
    els.jobsInput.value = "data/market_jobs.json";
  }
  setStatus(`Refreshed ${payload.merged_jobs} jobs across ${payload.companies.length} target companies. Reloading dashboard...`);
  await loadDashboard();
  els.marketRefreshButton.disabled = false;
}

function bootstrapDefaults() {
  els.profileInput.value = "";
  els.jobsInput.value = "";
  els.contactsInput.value = "";
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadDashboard();
});

els.scoreFilter.addEventListener("input", () => {
  if (latestPayload) renderJobs(latestPayload);
});

els.companyFilter.addEventListener("change", () => {
  if (latestPayload) renderJobs(latestPayload);
});

els.marketRefreshButton.addEventListener("click", () => {
  refreshMarketData().catch((error) => {
    els.marketRefreshButton.disabled = false;
    setStatus(error.message || "Failed to refresh market data.", true);
  });
});

bootstrapDefaults();
loadDashboard().catch((error) => {
  setStatus(error.message || "Failed to initialize dashboard.", true);
});
