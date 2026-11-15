// Frontend logic: loads data from the FastAPI backend and draws the job cards.

// Address of the backend. Change it here if the API runs on another host or port.
const API_BASE = window.location.protocol.startsWith("http")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// Elements of the page that the script works with
const candidateSelect = document.getElementById("candidate-select");
const profileBox = document.getElementById("profile");
const tabs = document.querySelectorAll(".tab");
const filtersForm = document.getElementById("filters");
const categorySelect = document.getElementById("filter-category");
const typeSelect = document.getElementById("filter-type");
const remoteCheckbox = document.getElementById("filter-remote");
const statusLine = document.getElementById("status");
const messageBox = document.getElementById("message");
const results = document.getElementById("results");

// Current state of the page
let candidates = [];           // loaded once from GET /candidates
let candidateId = null;        // id of the selected candidate
let view = "recommendations";  // "recommendations" or "jobs"
let latestRequest = 0;         // number of the newest request (older answers are ignored)

// Readable names for the criteria in the score breakdown
const CRITERION_LABELS = {
  skills: "Skills",
  interests: "Interests",
  audience: "Study area",
  year_of_study: "Year of study",
  employment_type: "Employment type",
  schedule: "Working hours",
  work_mode: "Work mode",
  distance: "Distance",
  salary: "Salary",
  availability: "Open positions and deadline",
};

// ---------- Talking to the API ----------

// GET a path from the API and return the JSON. Throws an Error with a readable message.
async function fetchJson(path) {
  let response;
  try {
    response = await fetch(API_BASE + path);
  } catch (error) {
    // fetch() itself fails only when the server cannot be reached at all
    throw new Error(`Cannot reach the API at ${API_BASE}. Check that the backend is running.`);
  }
  if (!response.ok) {
    // FastAPI sends errors as {"detail": "..."}
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return response.json();
}

// Turn the filter controls into a query string, e.g. "category=Design&remote_only=true"
function filterQuery() {
  const params = new URLSearchParams();
  if (categorySelect.value) params.set("category", categorySelect.value);
  if (typeSelect.value) params.set("employment_type", typeSelect.value);
  if (remoteCheckbox.checked) params.set("remote_only", "true");
  return params.toString();
}

// ---------- Loading, error and empty states ----------

// kind is "loading", "error" or "empty". If retry is given, a "Try again" button is added.
function showMessage(kind, text, retry) {
  results.innerHTML = "";
  messageBox.className = "message " + kind;
  messageBox.textContent = text;
  if (retry) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Try again";
    button.addEventListener("click", retry);
    messageBox.appendChild(button);
  }
  messageBox.hidden = false;
}

function hideMessage() {
  messageBox.hidden = true;
}

// ---------- Formatting helpers ----------

// Text from the database is escaped before it is put into HTML (protection against XSS).
function escapeHtml(text) {
  const replacements = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(text).replace(/[&<>"']/g, (character) => replacements[character]);
}

function formatMoney(amount) {
  return amount.toLocaleString("en-US");   // 45000 -> "45,000"
}

function formatSalary(min, max) {
  if (min === null && max === null) return "Not listed";
  if (min !== null && max !== null) return `${formatMoney(min)} to ${formatMoney(max)} MKD / month`;
  return `${formatMoney(min !== null ? min : max)} MKD / month`;
}

// Whole days from today until the date (negative when the date has passed)
function daysUntil(isoDate) {
  const target = new Date(isoDate + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target - today) / (24 * 60 * 60 * 1000));
}

function formatDeadline(isoDate) {
  const text = new Date(isoDate + "T00:00:00").toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });
  const days = daysUntil(isoDate);
  if (days < 0) return `${text} (passed)`;
  if (days === 0) return `${text} (today)`;
  return `${text} (${days} ${days === 1 ? "day" : "days"} left)`;
}

// [["Location", "Skopje"], ["Salary", "..."]] -> HTML list of label + value pairs
function factsList(pairs) {
  const rows = pairs.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`);
  return `<dl class="facts">${rows.join("")}</dl>`;
}

// ---------- Drawing the cards ----------

function recommendationCard(item) {
  let level = "low";
  if (item.score >= 75) level = "high";
  else if (item.score >= 50) level = "medium";

  let place = item.location_name;
  if (item.work_mode === "Remote") place = `Remote (employer in ${item.location_name})`;
  else if (item.distance_km !== null) place = `${item.location_name}, ${item.distance_km} km away`;

  const breakdown = item.score_breakdown
    .map((row) => `<li><span>${CRITERION_LABELS[row.criterion]}</span><span>${row.points} / ${row.max_points}</span></li>`)
    .join("");

  return `
    <article class="card">
      <div class="score ${level}">
        <strong>${item.score}</strong>
        <span>of 100</span>
      </div>
      <div class="card-body">
        <h2>${escapeHtml(item.title)}</h2>
        <p class="employer">${escapeHtml(item.employer)}, ${escapeHtml(item.category)}</p>
        <p class="tags">
          <span class="tag">${escapeHtml(item.employment_type)}</span>
          <span class="tag">${escapeHtml(item.work_mode)}</span>
        </p>
        ${factsList([
          ["Location", place],
          ["Salary", formatSalary(item.salary_min, item.salary_max)],
          ["Apply by", formatDeadline(item.application_deadline)],
          ["Open positions", item.available_positions],
        ])}
        <p class="reason">${escapeHtml(item.reason)}</p>
        <details>
          <summary>How this score was calculated</summary>
          <ul class="breakdown">${breakdown}</ul>
        </details>
      </div>
    </article>`;
}

function jobCard(job) {
  // A job is closed when the deadline has passed or no position is left.
  const closed = job.available_positions === 0 || daysUntil(job.application_deadline) < 0;

  return `
    <article class="card ${closed ? "is-closed" : ""}">
      <div class="card-body">
        <h2>${escapeHtml(job.title)}</h2>
        <p class="employer">${escapeHtml(job.employer)}, ${escapeHtml(job.category)}</p>
        <p class="tags">
          <span class="tag">${escapeHtml(job.employment_type)}</span>
          <span class="tag">${escapeHtml(job.work_mode)}</span>
          ${closed ? '<span class="tag closed">Closed</span>' : ""}
        </p>
        ${factsList([
          ["Location", job.location_name],
          ["Salary", formatSalary(job.salary_min, job.salary_max)],
          ["Apply by", formatDeadline(job.application_deadline)],
          ["Open positions", `${job.available_positions} of ${job.vacancies}`],
          ["Required skills", job.required_skills.join(", ")],
          ["Open to", job.target_audience],
        ])}
      </div>
    </article>`;
}

// Short description of the selected candidate above the results
function renderProfile() {
  const candidate = candidates.find((person) => person.id === candidateId);
  if (!candidate || view !== "recommendations") {
    profileBox.hidden = true;
    return;
  }
  const year = candidate.year_of_study >= 5 ? "recent graduate" : `year ${candidate.year_of_study}`;
  profileBox.innerHTML =
    `<strong>${escapeHtml(candidate.name)}</strong>, ${escapeHtml(candidate.study_area)} (${year}). ` +
    `Skills: ${escapeHtml(candidate.skills.join(", "))}. ` +
    `Interested in ${escapeHtml(candidate.interests.join(", "))}. ` +
    `Looking for ${escapeHtml(candidate.preferred_employment_type)}, ${escapeHtml(candidate.preferred_work_mode)}, ` +
    `from ${formatMoney(candidate.min_salary)} MKD / month, ` +
    `available ${candidate.available_from.slice(0, 5)} to ${candidate.available_to.slice(0, 5)}.`;
  profileBox.hidden = false;
}

// ---------- Loading data ----------

// Load recommendations or jobs (depending on the selected view) and show them.
async function loadResults() {
  const requestNumber = ++latestRequest;
  const currentView = view;
  const query = filterQuery();

  renderProfile();
  statusLine.textContent = "";

  if (currentView === "recommendations" && candidateId === null) {
    showMessage("empty", "There are no candidates in the database yet. Run the seed script first.");
    return;
  }

  let path = currentView === "recommendations" ? `/recommendations/${candidateId}` : "/jobs";
  if (query) path += "?" + query;

  showMessage("loading", "Loading…");
  try {
    const data = await fetchJson(path);
    if (requestNumber !== latestRequest) return;   // a newer request was started, ignore this answer

    const items = currentView === "recommendations" ? data.recommendations : data;
    if (items.length === 0) {
      showMessage("empty", "No jobs match these filters. Clear a filter to see more.");
      return;
    }

    hideMessage();
    if (currentView === "recommendations") {
      statusLine.textContent = `${items.length} recommendations for ${data.candidate_name}, best match first.`;
      results.innerHTML = items.map(recommendationCard).join("");
    } else {
      statusLine.textContent = `${items.length} jobs.`;
      results.innerHTML = items.map(jobCard).join("");
    }
  } catch (error) {
    if (requestNumber !== latestRequest) return;
    showMessage("error", error.message, loadResults);
  }
}

// Runs once when the page opens: fill the candidate selector, then load the results.
async function loadCandidates() {
  showMessage("loading", "Loading candidates…");
  try {
    candidates = await fetchJson("/candidates");
  } catch (error) {
    showMessage("error", error.message, loadCandidates);
    return;
  }

  candidateSelect.innerHTML =
    '<option value="" disabled>Choose a candidate</option>' +
    candidates
      .map((person) => `<option value="${person.id}">${escapeHtml(person.name)} (${escapeHtml(person.study_area)})</option>`)
      .join("");

  // Use candidate_id from the address (index.html?candidate_id=1), otherwise the first candidate.
  const idFromUrl = Number(new URLSearchParams(window.location.search).get("candidate_id"));
  if (idFromUrl) candidateId = idFromUrl;
  else if (candidates.length > 0) candidateId = candidates[0].id;

  // If the id from the address does not exist, no option is selected and the API answers "Candidate not found".
  const exists = candidates.some((person) => person.id === candidateId);
  candidateSelect.value = exists ? String(candidateId) : "";

  loadResults();
}

// ---------- Reacting to the user ----------

candidateSelect.addEventListener("change", () => {
  candidateId = Number(candidateSelect.value);
  // Keep the address in sync with the selection, so the page can be reloaded or shared.
  try {
    history.replaceState(null, "", "?candidate_id=" + candidateId);
  } catch (error) {
    // Some browsers do not allow this for pages opened directly from disk. Not a problem.
  }
  loadResults();
});

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    view = tab.dataset.view;
    tabs.forEach((other) => other.classList.toggle("active", other === tab));
    loadResults();
  });
});

// Any change of a filter reloads the results from the API.
filtersForm.addEventListener("change", loadResults);
// "Clear filters": the browser resets the fields right after this event, so wait a moment.
filtersForm.addEventListener("reset", () => setTimeout(loadResults, 0));

loadCandidates();
