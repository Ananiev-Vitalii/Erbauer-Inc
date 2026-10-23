function initInvoiceHistoryFilters() {
  const periodForm = document.querySelector(
    "[data-invoice-history-period-form]"
  );
  const periodSelect = document.querySelector(
    "[data-invoice-history-period]"
  );

  const yearForm = document.querySelector(
    "[data-invoice-history-year-form]"
  );
  const yearSelect = document.querySelector(
    "[data-invoice-history-year]"
  );

  if (periodForm && periodSelect) {
    periodSelect.addEventListener("change", () => {
      if (periodSelect.value === "all") {
        window.location.assign(periodForm.action);
        return;
      }

      periodForm.submit();
    });
  }

  if (yearForm && yearSelect) {
    yearSelect.addEventListener("change", () => {
      if (!yearSelect.value) {
        window.location.assign(yearForm.action);
        return;
      }

      yearForm.submit();
    });
  }
}

initInvoiceHistoryFilters();