const issueList = document.querySelector("#issue-list");
const emptyState = document.querySelector("#empty-state");
const loadError = document.querySelector("#load-error");
const form = document.querySelector("#new-issue-form");
const formFeedback = document.querySelector("#form-feedback");
const nameInput = document.querySelector("#reporter-name");
const statusFilters = document.querySelectorAll(".filter-tab");
const categoryFilters = document.querySelectorAll(".category-chip");
const searchInput = document.querySelector("#search");

let issues = [];
let activeStatus = "all";
let activeCategory = "all";
let savedName = "";
try {
  savedName = localStorage.getItem("fixfirst-name") || "";
} catch (error) {
  console.warn("Could not read the saved name from browser storage.", error);
}
nameInput.value = savedName;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function statusLabel(status) {
  return { open: "Needs help", in_progress: "In progress", resolved: "Resolved" }[status];
}

function relativeDate(value) {
  const hours = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 3600000));
  if (hours < 1) return "Just reported";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data;
}

function renderIssue(issue) {
  const names = issue.participants.slice(0, 3);
  const avatarNames = names.map((name) => `<i title="${escapeHtml(name)}">${escapeHtml(name.charAt(0).toUpperCase())}</i>`).join("");
  const extraCount = Math.max(issue.participants.length - names.length, 0);
  const joined = savedName && issue.participants.some((name) => name.toLowerCase() === savedName.toLowerCase());
  const isReporter = savedName && issue.reporters.some((name) => name.toLowerCase() === savedName.toLowerCase());
  const canUpdate = joined || isReporter;
  const statusOptions = ["open", "in_progress", "resolved"].map((status) =>
    `<option value="${status}" ${issue.status === status ? "selected" : ""}>${statusLabel(status)}</option>`
  ).join("");
  const priorityTone = issue.priority_score >= 70 ? "priority-high" : issue.priority_score >= 40 ? "priority-medium" : "priority-low";
  const action = issue.status === "resolved"
    ? `<span class="resolved-note">Community solved this ✳</span>`
    : joined
      ? `<span class="joined-note">✓ You’re helping</span>`
      : `<button class="join-button" data-join="${issue.id}">Join in <span aria-hidden="true">↗</span></button>`;

  return `<article class="issue-card">
    <div class="card-topline"><span class="issue-category">${escapeHtml(issue.category)}</span><span class="issue-age">${relativeDate(issue.created_at)}</span></div>
    <h3>${escapeHtml(issue.title)}</h3>
    <p class="issue-description">${escapeHtml(issue.description)}</p>
    <div class="issue-location"><span aria-hidden="true">⌖</span> ${escapeHtml(issue.location)}</div>
    <div class="impact-details"><span>Urgency <b>${issue.severity}/5</b></span><span><b>${issue.people_affected.toLocaleString()}</b> ${issue.people_affected === 1 ? "neighbor reported" : "neighbors reported"}</span></div>
    <div class="priority-row"><span class="priority-label ${priorityTone}"><i></i> Priority ${issue.priority_score}</span><span class="status-pill status-${issue.status}">${statusLabel(issue.status)}</span></div>
    <div class="card-bottom"><div class="volunteers">${avatarNames}${extraCount ? `<i class="avatar-more">+${extraCount}</i>` : ""}<span>${issue.participants.length} ${issue.participants.length === 1 ? "neighbor" : "neighbors"} helping</span></div>${action}</div>
    ${canUpdate && issue.status !== "resolved" ? `<div class="status-editor"><label for="status-${issue.id}">Update progress</label><select id="status-${issue.id}" data-status-select="${issue.id}">${statusOptions}</select><button data-update="${issue.id}">Save</button></div>` : ""}
  </article>`;
}

function renderIssues() {
  const query = searchInput.value.trim().toLowerCase();
  const visible = issues.filter((issue) => {
    if (issue.status === "resolved") return false;
    const matchesStatus = activeStatus === "all" || issue.status === activeStatus;
    const matchesCategory = activeCategory === "all" || issue.category === activeCategory;
    const searchable = `${issue.title} ${issue.description} ${issue.location} ${issue.category}`.toLowerCase();
    return matchesStatus && matchesCategory && searchable.includes(query);
  });
  issueList.innerHTML = visible.map(renderIssue).join("");
  emptyState.hidden = visible.length > 0;
  document.querySelector("#all-count").textContent = issues.length;
}

async function loadIssues() {
  loadError.hidden = true;
  try {
    issues = await request("/api/issues");
    renderIssues();
  } catch (error) {
    loadError.textContent = error.message;
    loadError.hidden = false;
  }
}

function getName() {
  const name = nameInput.value.trim();
  if (!name) throw new Error("Please enter your name first.");
  savedName = name;
  try {
    localStorage.setItem("fixfirst-name", name);
  } catch (error) {
    console.warn("Could not save the name to browser storage.", error);
  }
  return name;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector("[type=submit]");
  submitButton.disabled = true;
  formFeedback.hidden = true;
  try {
    const values = Object.fromEntries(new FormData(form).entries());
    values.reporter_name = getName();
    values.severity = Number(values.severity);
    const result = await request("/api/issues", { method: "POST", body: JSON.stringify(values) });
    form.reset();
    nameInput.value = savedName;
    document.querySelector("#severity").value = "3";
    formFeedback.textContent = result.merged_report
      ? `Your report was added to this existing issue. ${result.people_affected} neighbors have reported it.`
      : "Your issue is live. Thanks for looking out for your community!";
    formFeedback.className = "form-feedback success";
    formFeedback.hidden = false;
    await loadIssues();
    document.querySelector("#issues").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    formFeedback.textContent = error.message;
    formFeedback.className = "form-feedback error";
    formFeedback.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});

statusFilters.forEach((button) => button.addEventListener("click", () => {
  statusFilters.forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  activeStatus = button.dataset.status;
  renderIssues();
}));

categoryFilters.forEach((button) => button.addEventListener("click", () => {
  categoryFilters.forEach((item) => item.classList.remove("selected"));
  button.classList.add("selected");
  activeCategory = button.dataset.category;
  renderIssues();
}));

searchInput.addEventListener("input", renderIssues);

async function saveIssueStatus(issueId, status, control) {
  control.disabled = true;
  try {
    getName();
    const result = await request(`/api/issues/${issueId}/status`, {
      method: "PATCH", body: JSON.stringify({ name: savedName, status }),
    });
    if (result.deleted) {
      issues = issues.filter((issue) => issue.id !== Number(issueId));
      renderIssues();
    } else {
      await loadIssues();
    }
  } catch (error) {
    window.alert(error.message);
    const issue = issues.find((item) => item.id === Number(issueId));
    if (control.matches("[data-status-select]") && issue) {
      control.value = issue.status;
    }
    control.disabled = false;
  }
}

issueList.addEventListener("change", (event) => {
  const statusSelect = event.target.closest("[data-status-select]");
  if (statusSelect && statusSelect.value === "resolved") {
    saveIssueStatus(statusSelect.dataset.statusSelect, "resolved", statusSelect);
  }
});

issueList.addEventListener("click", async (event) => {
  const joinButton = event.target.closest("[data-join]");
  const updateButton = event.target.closest("[data-update]");
  if (joinButton) {
    joinButton.disabled = true;
    try {
      getName();
      await request(`/api/issues/${joinButton.dataset.join}/join`, {
        method: "POST", body: JSON.stringify({ name: savedName }),
      });
      await loadIssues();
    } catch (error) {
      window.alert(error.message);
      joinButton.disabled = false;
    }
  }
  if (updateButton) {
    const issueId = updateButton.dataset.update;
    const status = document.querySelector(`[data-status-select="${issueId}"]`).value;
    await saveIssueStatus(issueId, status, updateButton);
  }
});

loadIssues();
