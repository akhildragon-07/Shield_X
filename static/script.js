/**
 * Email Deliverability Checker - Client Application Logic
 * Vanilla JavaScript (zero external dependencies)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const emailInput = document.getElementById("emailInput");
  const emailCounter = document.getElementById("emailCounter");
  const checkBtn = document.getElementById("checkBtn");
  const btnSpinner = document.getElementById("btnSpinner");
  const btnIcon = document.getElementById("btnIcon");
  const btnText = document.getElementById("btnText");
  const loadSampleBtn = document.getElementById("loadSampleBtn");
  const clearInputBtn = document.getElementById("clearInputBtn");
  const errorAlert = document.getElementById("errorAlert");
  const errorMessage = document.getElementById("errorMessage");

  const loadingBanner = document.getElementById("loadingBanner");
  const resultsSection = document.getElementById("resultsSection");
  const countTotal = document.getElementById("countTotal");
  const countDeliverable = document.getElementById("countDeliverable");
  const countBounce = document.getElementById("countBounce");
  const countUnknown = document.getElementById("countUnknown");

  const resultsTableBody = document.getElementById("resultsTableBody");
  const resultsCountSubtitle = document.getElementById("resultsCountSubtitle");
  const downloadCsvBtn = document.getElementById("downloadCsvBtn");
  const clearResultsBtn = document.getElementById("clearResultsBtn");
  const tableSearchInput = document.getElementById("tableSearchInput");
  const filterPills = document.querySelectorAll(".filter-pill");

  // State
  let currentResults = [];
  let currentFilter = "all";
  let currentSearchQuery = "";
  const MAX_LIMIT = 100;

  // Sample addresses for testing all 3 categories
  const SAMPLE_EMAILS = [
    "contact@github.com",
    "invalid-format-missing-at-sign",
    "admin@cloudflare.com",
    "alice@definitely-does-not-exist-xyz9874321.org",
    "support@python.org",
    "double..dots@example.com",
    "info@wikipedia.org"
  ].join("\n");

  /**
   * Parse and extract unique non-empty email lines from input text
   */
  function extractEmails(text) {
    if (!text) return [];
    // Support newlines, commas, and semicolons as delimiters
    const rawTokens = text.replace(/,/g, "\n").replace(/;/g, "\n").split("\n");
    const seen = new Set();
    const result = [];

    for (let token of rawTokens) {
      const clean = token.trim();
      if (clean && !seen.has(clean)) {
        seen.add(clean);
        result.push(clean);
      }
    }
    return result;
  }

  /**
   * Update character / address counter in UI
   */
  function updateCounter() {
    const emails = extractEmails(emailInput.value);
    const count = emails.length;
    emailCounter.textContent = `${count} / ${MAX_LIMIT} addresses`;

    if (count > MAX_LIMIT) {
      emailCounter.classList.add("limit-exceeded");
      showError(`Maximum limit exceeded. You have entered ${count} unique addresses. Maximum allowed is ${MAX_LIMIT}.`);
      checkBtn.disabled = true;
    } else {
      emailCounter.classList.remove("limit-exceeded");
      hideError();
      checkBtn.disabled = false;
    }
  }

  /**
   * Show inline error notification
   */
  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.style.display = "flex";
  }

  /**
   * Hide error notification
   */
  function hideError() {
    errorAlert.style.display = "none";
    errorMessage.textContent = "";
  }

  /**
   * Set loading UI state during API verification
   */
  function setLoadingState(isLoading) {
    if (isLoading) {
      checkBtn.disabled = true;
      loadSampleBtn.disabled = true;
      clearInputBtn.disabled = true;
      emailInput.disabled = true;
      btnSpinner.style.display = "inline-block";
      btnIcon.style.display = "none";
      btnText.textContent = "Checking...";
      loadingBanner.style.display = "flex";
      hideError();
    } else {
      checkBtn.disabled = false;
      loadSampleBtn.disabled = false;
      clearInputBtn.disabled = false;
      emailInput.disabled = false;
      btnSpinner.style.display = "none";
      btnIcon.style.display = "inline-block";
      btnText.textContent = "Check Emails";
      loadingBanner.style.display = "none";
    }
  }

  /**
   * Generate status badge HTML element
   */
  function createStatusBadge(status) {
    const badge = document.createElement("span");
    badge.className = "badge";

    if (status === "Likely deliverable") {
      badge.classList.add("badge-deliverable");
      badge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg> Likely deliverable`;
    } else if (status === "Likely to bounce") {
      badge.classList.add("badge-bounce");
      badge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg> Likely to bounce`;
    } else {
      badge.classList.add("badge-unknown");
      badge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg> Unknown`;
    }
    return badge;
  }

  /**
   * Render the table rows according to active filter and search query
   */
  function renderTableRows() {
    resultsTableBody.innerHTML = "";

    const filtered = currentResults.filter(item => {
      // Status filter
      if (currentFilter !== "all" && item.status !== currentFilter) {
        return false;
      }
      // Search filter
      if (currentSearchQuery) {
        const q = currentSearchQuery.toLowerCase();
        const matchesEmail = item.email.toLowerCase().includes(q);
        const matchesDomain = (item.domain || "").toLowerCase().includes(q);
        const matchesReason = (item.reason || "").toLowerCase().includes(q);
        if (!matchesEmail && !matchesDomain && !matchesReason) {
          return false;
        }
      }
      return true;
    });

    resultsCountSubtitle.textContent = `Showing ${filtered.length} of ${currentResults.length} result(s)`;

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.style.textAlign = "center";
      td.style.padding = "32px";
      td.style.color = "var(--text-muted)";
      td.textContent = "No addresses match your filter criteria.";
      tr.appendChild(td);
      resultsTableBody.appendChild(tr);
      return;
    }

    filtered.forEach((item, index) => {
      const tr = document.createElement("tr");

      // Column 1: Index
      const tdIndex = document.createElement("td");
      tdIndex.textContent = String(index + 1);
      tdIndex.style.color = "var(--text-muted)";
      tr.appendChild(tdIndex);

      // Column 2: Email Address (safely escaped)
      const tdEmail = document.createElement("td");
      tdEmail.className = "email-cell";
      tdEmail.textContent = item.email;
      tr.appendChild(tdEmail);

      // Column 3: Status Badge
      const tdStatus = document.createElement("td");
      tdStatus.appendChild(createStatusBadge(item.status));
      tr.appendChild(tdStatus);

      // Column 4: Mail Server (MX)
      const tdMx = document.createElement("td");
      tdMx.className = "mx-cell";
      if (item.mx_host) {
        tdMx.textContent = item.mx_host;
      } else {
        tdMx.textContent = "—";
      }
      tr.appendChild(tdMx);

      // Column 5: Reason & Details
      const tdReason = document.createElement("td");
      tdReason.className = "reason-cell";
      tdReason.textContent = item.reason || "Validation completed.";
      tr.appendChild(tdReason);

      resultsTableBody.appendChild(tr);
    });
  }

  /**
   * Handle primary "Check Emails" submission
   */
  async function handleCheckEmails() {
    hideError();
    const emails = extractEmails(emailInput.value);

    if (emails.length === 0) {
      showError("Please enter at least one valid email address to verify.");
      emailInput.focus();
      return;
    }

    if (emails.length > MAX_LIMIT) {
      showError(`Batch size exceeded. You entered ${emails.length} addresses, but the maximum limit is ${MAX_LIMIT}.`);
      return;
    }

    setLoadingState(true);

    try {
      const response = await fetch("/api/check", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ emails: emails })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Server returned an error during verification.");
      }

      // Populate summary metrics
      countTotal.textContent = String(data.summary.total);
      countDeliverable.textContent = String(data.summary.deliverable);
      countBounce.textContent = String(data.summary.bounce);
      countUnknown.textContent = String(data.summary.unknown);

      // Store results
      currentResults = data.results || [];
      currentFilter = "all";
      currentSearchQuery = "";
      tableSearchInput.value = "";

      // Reset filter pills UI
      filterPills.forEach(pill => {
        if (pill.dataset.filter === "all") pill.classList.add("active");
        else pill.classList.remove("active");
      });

      renderTableRows();

      // Show results section and scroll smoothly into view
      resultsSection.style.display = "block";
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (err) {
      showError(err.message || "Failed to communicate with the verification server. Please try again.");
    } finally {
      setLoadingState(false);
    }
  }

  /**
   * Export results as CSV using backend endpoint
   */
  async function handleDownloadCsv() {
    if (!currentResults || currentResults.length === 0) {
      showError("No results available to download.");
      return;
    }

    try {
      const response = await fetch("/api/export-csv", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ results: currentResults })
      });

      if (!response.ok) {
        throw new Error("Failed to generate CSV export file.");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `email_deliverability_report_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      showError("Error exporting CSV: " + err.message);
    }
  }

  // Event Listeners
  emailInput.addEventListener("input", updateCounter);

  loadSampleBtn.addEventListener("click", () => {
    emailInput.value = SAMPLE_EMAILS;
    updateCounter();
    hideError();
  });

  clearInputBtn.addEventListener("click", () => {
    emailInput.value = "";
    updateCounter();
    hideError();
  });

  clearResultsBtn.addEventListener("click", () => {
    currentResults = [];
    resultsSection.style.display = "none";
    countTotal.textContent = "0";
    countDeliverable.textContent = "0";
    countBounce.textContent = "0";
    countUnknown.textContent = "0";
    resultsTableBody.innerHTML = "";
    hideError();
  });

  checkBtn.addEventListener("click", handleCheckEmails);
  downloadCsvBtn.addEventListener("click", handleDownloadCsv);

  // Filter Pill buttons
  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.dataset.filter;
      renderTableRows();
    });
  });

  // Table search input filter
  tableSearchInput.addEventListener("input", (e) => {
    currentSearchQuery = e.target.value.trim();
    renderTableRows();
  });

  // Initial counter setup
  updateCounter();
});
