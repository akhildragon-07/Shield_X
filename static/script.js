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
  const pctDeliverable = document.getElementById("pctDeliverable");
  const pctBounce = document.getElementById("pctBounce");
  const pctUnknown = document.getElementById("pctUnknown");

  const resultsTableBody = document.getElementById("resultsTableBody");
  const resultsCountSubtitle = document.getElementById("resultsCountSubtitle");
  const downloadCsvBtn = document.getElementById("downloadCsvBtn");
  const clearResultsBtn = document.getElementById("clearResultsBtn");
  const tableSearchInput = document.getElementById("tableSearchInput");
  const tabBtns = document.querySelectorAll(".tab-btn");
  const kpiCards = document.querySelectorAll(".kpi-card");
  const chipBtns = document.querySelectorAll(".chip-btn");

  let currentResults = [];
  let currentFilter = "all";
  let currentSearchQuery = "";
  const MAX_LIMIT = 100;

  const SAMPLE_EMAILS = [
    "support@github.com",
    "contact@python.org",
    "invalid-format-no-at-sign",
    "admin@cloudflare.com",
    "user@definitely-does-not-exist-xyz9874321.org",
    "test..double.dots@example.com",
    "info@wikipedia.org"
  ].join("\n");

  function extractEmails(text) {
    if (!text) return [];
    const tokens = text.replace(/,/g, "\n").replace(/;/g, "\n").split("\n");
    const seen = new Set();
    const result = [];

    for (let token of tokens) {
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
      showError(`Maximum limit exceeded. You entered ${count} addresses (maximum allowed is ${MAX_LIMIT}).`);
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

  function copyTextToClipboard(text, btnElement) {
    navigator.clipboard.writeText(text).then(() => {
      const originalHtml = btnElement.innerHTML;
      btnElement.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      `;
      setTimeout(() => {
        btnElement.innerHTML = originalHtml;
      }, 1500);
    }).catch(() => {});
  }

  function renderTableRows() {
    resultsTableBody.innerHTML = "";

    const filtered = currentResults.filter(item => {
      if (currentFilter !== "all" && item.status !== currentFilter) {
        return false;
      }
      if (currentSearchQuery) {
        const q = currentSearchQuery.toLowerCase();
        const matchEmail = item.email.toLowerCase().includes(q);
        const matchDomain = (item.domain || "").toLowerCase().includes(q);
        const matchReason = (item.reason || "").toLowerCase().includes(q);
        if (!matchEmail && !matchDomain && !matchReason) {
          return false;
        }
      }
      return true;
    });

    resultsCountSubtitle.textContent = `${filtered.length} of ${currentResults.length} result(s)`;

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.style.textAlign = "center";
      td.style.padding = "36px";
      td.style.color = "var(--slate-400)";
      td.textContent = "No email addresses match your filter.";
      tr.appendChild(td);
      resultsTableBody.appendChild(tr);
      return;
    }

    filtered.forEach((item, index) => {
      const tr = document.createElement("tr");

      // Column 1: Index
      const tdIndex = document.createElement("td");
      tdIndex.style.textAlign = "center";
      tdIndex.style.color = "var(--slate-400)";
      tdIndex.style.fontSize = "0.75rem";
      tdIndex.textContent = String(index + 1);
      tr.appendChild(tdIndex);

      // Column 2: Email Address + Copy icon
      const tdEmail = document.createElement("td");
      const emailCol = document.createElement("div");
      emailCol.className = "email-col";

      const emailSpan = document.createElement("span");
      emailSpan.className = "email-text";
      emailSpan.textContent = item.email;
      emailCol.appendChild(emailSpan);

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "copy-mini-btn";
      copyBtn.title = "Copy email address";
      copyBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      `;
      copyBtn.addEventListener("click", () => copyTextToClipboard(item.email, copyBtn));
      emailCol.appendChild(copyBtn);

      tdEmail.appendChild(emailCol);
      tr.appendChild(tdEmail);

      // Column 3: Status Badge
      const tdStatus = document.createElement("td");
      tdStatus.appendChild(createStatusBadge(item.status));
      tr.appendChild(tdStatus);

      // Column 4: Mail Server (MX)
      const tdMx = document.createElement("td");
      if (item.mx_host) {
        const mxBadge = document.createElement("span");
        mxBadge.className = "mx-badge";
        mxBadge.textContent = item.mx_host;
        tdMx.appendChild(mxBadge);
      } else {
        tdMx.textContent = "—";
        tdMx.style.color = "var(--slate-400)";
      }
      tr.appendChild(tdMx);

      // Column 5: Reason & Details
      const tdReason = document.createElement("td");
      tdReason.className = "reason-text";
      tdReason.textContent = item.reason || "Checked.";
      tr.appendChild(tdReason);

      resultsTableBody.appendChild(tr);
    });
  }

  function setActiveFilter(filterName) {
    currentFilter = filterName;
    tabBtns.forEach(btn => {
      if (btn.dataset.filter === filterName) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
    renderTableRows();
  }

  async function handleCheckEmails() {
    hideError();
    const emails = extractEmails(emailInput.value);

    if (emails.length === 0) {
      showError("Please enter at least one email address to check.");
      emailInput.focus();
      return;
    }

    if (emails.length > MAX_LIMIT) {
      showError(`Batch size exceeded. You entered ${emails.length} addresses, but the maximum is ${MAX_LIMIT}.`);
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
        throw new Error(data.error || "Server error while evaluating emails.");
      }

      const total = data.summary.total || 0;
      const deliverable = data.summary.deliverable || 0;
      const bounce = data.summary.bounce || 0;
      const unknown = data.summary.unknown || 0;

      countTotal.textContent = String(total);
      countDeliverable.textContent = String(deliverable);
      countBounce.textContent = String(bounce);
      countUnknown.textContent = String(unknown);

      // Calculate percentages
      pctDeliverable.textContent = total > 0 ? `${Math.round((deliverable / total) * 100)}% of total` : "0% of total";
      pctBounce.textContent = total > 0 ? `${Math.round((bounce / total) * 100)}% of total` : "0% of total";
      pctUnknown.textContent = total > 0 ? `${Math.round((unknown / total) * 100)}% of total` : "0% of total";

      currentResults = data.results || [];
      currentSearchQuery = "";
      tableSearchInput.value = "";
      setActiveFilter("all");

      resultsSection.style.display = "block";
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (err) {
      showError(err.message || "Could not complete deliverability verification.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadCsv() {
    if (!currentResults || currentResults.length === 0) {
      showError("No results available to export.");
      return;
    }

    try {
      const res = await fetch("/api/export-csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: currentResults })
      });

      if (!res.ok) {
        throw new Error("Failed to generate CSV export file.");
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

  // Event Listeners
  emailInput.addEventListener("input", updateCounter);

  // Quick insert chip buttons
  chipBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const email = btn.dataset.email;
      const currentVal = emailInput.value.trim();
      if (!currentVal) {
        emailInput.value = email;
      } else {
        emailInput.value = currentVal + "\n" + email;
      }
      updateCounter();
      hideError();
    });
  });

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
    pctDeliverable.textContent = "0% of total";
    pctBounce.textContent = "0% of total";
    pctUnknown.textContent = "0% of total";
    resultsTableBody.innerHTML = "";
    hideError();
  });

  checkBtn.addEventListener("click", handleCheckEmails);
  downloadCsvBtn.addEventListener("click", handleDownloadCsv);

  // Filter tabs
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      setActiveFilter(btn.dataset.filter);
    });
  });

  // Clicking a KPI card filters the table directly
  kpiCards.forEach(card => {
    card.addEventListener("click", () => {
      const filter = card.dataset.filter;
      if (filter) {
        setActiveFilter(filter);
        resultsTableBody.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });

  // Table search input
  tableSearchInput.addEventListener("input", (e) => {
    currentSearchQuery = e.target.value.trim();
    renderTableRows();
  });

  updateCounter();
});
