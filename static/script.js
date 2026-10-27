document.addEventListener("DOMContentLoaded", () => {
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

  let currentResults = [];
  let currentFilter = "all";
  let currentSearchQuery = "";
  const MAX_LIMIT = 100;

  const SAMPLE_EMAILS = [
    "contact@github.com",
    "invalid-format-missing-at-sign",
    "admin@cloudflare.com",
    "alice@definitely-does-not-exist-xyz9874321.org",
    "support@python.org",
    "double..dots@example.com",
    "info@wikipedia.org"
  ].join("\n");

  function extractEmails(text) {
    if (!text) return [];
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

  function updateCounter() {
    const emails = extractEmails(emailInput.value);
    const count = emails.length;
    emailCounter.textContent = `${count} / ${MAX_LIMIT} addresses`;

    if (count > MAX_LIMIT) {
      emailCounter.classList.add("limit-exceeded");
      showError(`Batch size exceeded (${count} emails). Maximum allowed is ${MAX_LIMIT}.`);
      checkBtn.disabled = true;
    } else {
      emailCounter.classList.remove("limit-exceeded");
      hideError();
      checkBtn.disabled = false;
    }
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.style.display = "flex";
  }

  function hideError() {
    errorAlert.style.display = "none";
    errorMessage.textContent = "";
  }

  function setLoading(loading) {
    if (loading) {
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

  function renderTableRows() {
    resultsTableBody.innerHTML = "";

    const filtered = currentResults.filter(item => {
      if (currentFilter !== "all" && item.status !== currentFilter) {
        return false;
      }
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
      td.textContent = "No matching addresses found.";
      tr.appendChild(td);
      resultsTableBody.appendChild(tr);
      return;
    }

    filtered.forEach((item, index) => {
      const tr = document.createElement("tr");

      const tdIndex = document.createElement("td");
      tdIndex.textContent = String(index + 1);
      tdIndex.style.color = "var(--text-muted)";
      tr.appendChild(tdIndex);

      const tdEmail = document.createElement("td");
      tdEmail.className = "email-cell";
      tdEmail.textContent = item.email;
      tr.appendChild(tdEmail);

      const tdStatus = document.createElement("td");
      tdStatus.appendChild(createStatusBadge(item.status));
      tr.appendChild(tdStatus);

      const tdMx = document.createElement("td");
      tdMx.className = "mx-cell";
      tdMx.textContent = item.mx_host || "—";
      tr.appendChild(tdMx);

      const tdReason = document.createElement("td");
      tdReason.className = "reason-cell";
      tdReason.textContent = item.reason || "Checked.";
      tr.appendChild(tdReason);

      resultsTableBody.appendChild(tr);
    });
  }

  async function handleCheckEmails() {
    hideError();
    const emails = extractEmails(emailInput.value);

    if (emails.length === 0) {
      showError("Please enter at least one email address.");
      emailInput.focus();
      return;
    }

    if (emails.length > MAX_LIMIT) {
      showError(`Maximum limit is ${MAX_LIMIT} emails.`);
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails: emails })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to check emails.");
      }

      countTotal.textContent = String(data.summary.total);
      countDeliverable.textContent = String(data.summary.deliverable);
      countBounce.textContent = String(data.summary.bounce);
      countUnknown.textContent = String(data.summary.unknown);

      currentResults = data.results || [];
      currentFilter = "all";
      currentSearchQuery = "";
      tableSearchInput.value = "";

      filterPills.forEach(pill => {
        if (pill.dataset.filter === "all") pill.classList.add("active");
        else pill.classList.remove("active");
      });

      renderTableRows();
      resultsSection.style.display = "block";
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (err) {
      showError(err.message || "Something went wrong while connecting to the server.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadCsv() {
    if (!currentResults || currentResults.length === 0) {
      showError("No results to download.");
      return;
    }

    try {
      const res = await fetch("/api/export-csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: currentResults })
      });

      if (!res.ok) {
        throw new Error("CSV generation failed.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `email_deliverability_report.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      showError("Error downloading CSV: " + err.message);
    }
  }

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

  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.dataset.filter;
      renderTableRows();
    });
  });

  tableSearchInput.addEventListener("input", (e) => {
    currentSearchQuery = e.target.value.trim();
    renderTableRows();
  });

  updateCounter();
});
