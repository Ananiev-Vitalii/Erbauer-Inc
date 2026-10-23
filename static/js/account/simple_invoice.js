const SIMPLE_INVOICE_FAST_POLL_INTERVAL_MS = 2000;
const SIMPLE_INVOICE_SLOW_POLL_INTERVAL_MS = 5000;

const SIMPLE_INVOICE_FAST_POLL_DURATION_MS =
  30 * 1000;

const SIMPLE_INVOICE_PROCESSING_TIMEOUT_MS =
  5 * 60 * 1000;

const SIMPLE_INVOICE_POLL_GRACE_MS =
  10 * 1000;


function initSimpleInvoicePostalCodeInput(
  root = document
) {
  const postalCodeInput = root.querySelector(
    "#id_postal_code"
  );

  if (!postalCodeInput) {
    return;
  }

  const formatPostalCode = (value) => {
    let formattedValue = value
      .toUpperCase()
      .replace(
        /[^A-Z0-9]/g,
        ""
      )
      .slice(
        0,
        6
      );

    if (
      formattedValue.length
      > 3
    ) {
      formattedValue = (
        `${formattedValue.slice(0, 3)} `
        + formattedValue.slice(3)
      );
    }

    return formattedValue;
  };

  postalCodeInput.value =
    formatPostalCode(
      postalCodeInput.value
    );

  postalCodeInput.addEventListener(
    "input",
    () => {
      postalCodeInput.value =
        formatPostalCode(
          postalCodeInput.value
        );
    }
  );
}


function initSimpleInvoiceGstAccountNumberInput(
  root = document
) {
  const gstAccountNumberInput =
    root.querySelector(
      "#id_gst_account_number"
    );

  if (!gstAccountNumberInput) {
    return;
  }

  const formatGstAccountNumber = (
    value
  ) => {
    const formattedValue = value
      .toUpperCase()
      .replace(
        /[^A-Z0-9]/g,
        ""
      )
      .slice(
        0,
        15
      );

    if (
      formattedValue.length
      <= 9
    ) {
      return formattedValue;
    }

    return (
      `${formattedValue.slice(0, 9)} `
      + formattedValue.slice(9)
    );
  };

  gstAccountNumberInput.value =
    formatGstAccountNumber(
      gstAccountNumberInput.value
    );

  gstAccountNumberInput.addEventListener(
    "input",
    () => {
      gstAccountNumberInput.value =
        formatGstAccountNumber(
          gstAccountNumberInput.value
        );
    }
  );
}


function updateSelectOptions(
  select,
  options,
  selectedValue
) {
  if (!select) {
    return;
  }

  select.replaceChildren();

  options.forEach(
    (item) => {
      const option =
        document.createElement(
          "option"
        );

      option.value = String(
        item.value
      );

      option.textContent =
        item.label;

      option.selected = (
        String(item.value)
        === String(
          selectedValue
        )
      );

      select.appendChild(
        option
      );
    }
  );
}


function updateSimpleInvoicePeriodMessage(
  messageElement,
  message
) {
  if (!messageElement) {
    return;
  }

  if (!message) {
    messageElement.hidden = true;

    messageElement.textContent =
      "";

    return;
  }

  messageElement.textContent =
    message;

  messageElement.hidden = false;
}


function initSimpleInvoicePeriod(
  root = document
) {
  const container = root.matches?.(
    "#simple-invoice-form"
  )
    ? root
    : root.querySelector(
        "#simple-invoice-form"
      );

  if (!container) {
    return;
  }

  const form =
    container.querySelector(
      "[data-simple-invoice-form]"
    );

  if (!form) {
    return;
  }

  if (
    form.dataset.periodInitialized
    === "true"
  ) {
    return;
  }

  form.dataset.periodInitialized =
    "true";

  const previewUrl =
    container.dataset
      .periodPreviewUrl;

  const yearSelect =
    form.querySelector(
      "#id_invoice_year"
    );

  const monthSelect =
    form.querySelector(
      "#id_invoice_month"
    );

  const startDaySelect =
    form.querySelector(
      "#id_start_day"
    );

  const endDaySelect =
    form.querySelector(
      "#id_end_day"
    );

  const hoursInput =
    form.querySelector(
      "#id_hours"
    );

  const periodMessage =
    form.querySelector(
      "[data-invoice-period-message]"
    );

  const submitButton =
    form.querySelector(
      'button[type="submit"]'
    );

  if (
    !previewUrl
    || !yearSelect
    || !monthSelect
    || !startDaySelect
    || !endDaySelect
    || !hoursInput
  ) {
    return;
  }

  let activeController =
    null;

  const setSubmitAllowed = (
    allowed
  ) => {
    if (!submitButton) {
      return;
    }

    submitButton.dataset
      .periodAllowed =
        allowed
          ? "true"
          : "false";

    if (
      form.dataset.submitting
      === "true"
      || container.dataset
        .invoiceProcessing
        === "true"
    ) {
      submitButton.disabled =
        true;

      return;
    }

    submitButton.disabled =
      !allowed;
  };

  const showPeriodMessage = (
    message
  ) => {
    if (
      container.dataset
        .invoiceProcessing
      === "true"
    ) {
      updateSimpleInvoicePeriodMessage(
        periodMessage,
        ""
      );

      return;
    }

    updateSimpleInvoicePeriodMessage(
      periodMessage,
      message
    );
  };

  const refreshPeriod = async (
    {
      preserveHours = false,
    } = {}
  ) => {
    if (activeController) {
      activeController.abort();
    }

    activeController =
      new AbortController();

    setSubmitAllowed(
      false
    );

    const params =
      new URLSearchParams(
        {
          year:
            yearSelect.value,

          month:
            monthSelect.value,

          start_day:
            startDaySelect.value,

          end_day:
            endDaySelect.value,
        }
      );

    try {
      const response =
        await fetch(
          `${previewUrl}?${params.toString()}`,
          {
            method: "GET",

            headers: {
              "X-Requested-With":
                "XMLHttpRequest",

              Accept:
                "application/json",
            },

            credentials:
              "same-origin",

            cache:
              "no-store",

            signal:
              activeController.signal,
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
        || !data.success
      ) {
        if (!preserveHours) {
          hoursInput.value =
            "0.00";
        }

        showPeriodMessage(
          data.message
          || container.dataset
            .periodRequestErrorText
        );

        setSubmitAllowed(
          false
        );

        return;
      }

      updateSelectOptions(
        monthSelect,
        data.months,
        data.selected_month
      );

      updateSelectOptions(
        startDaySelect,
        data.days,
        data.selected_start_day
      );

      updateSelectOptions(
        endDaySelect,
        data.days,
        data.selected_end_day
      );

      if (!preserveHours) {
        hoursInput.value =
          data.hours;
      }

      showPeriodMessage(
        data.message
      );

      setSubmitAllowed(
        Boolean(
          data.can_submit
        )
      );

    } catch (error) {
      if (
        error.name
        === "AbortError"
      ) {
        return;
      }

      console.error(
        "Simple invoice period request failed:",
        error
      );

      if (!preserveHours) {
        hoursInput.value =
          "0.00";
      }

      showPeriodMessage(
        container.dataset
          .periodRequestErrorText
      );

      setSubmitAllowed(
        false
      );
    }
  };

  yearSelect.addEventListener(
    "change",
    () => {
      refreshPeriod();
    }
  );

  monthSelect.addEventListener(
    "change",
    () => {
      refreshPeriod();
    }
  );

  startDaySelect.addEventListener(
    "change",
    () => {
      refreshPeriod();
    }
  );

  endDaySelect.addEventListener(
    "change",
    () => {
      refreshPeriod();
    }
  );

  container.addEventListener(
    "simple-invoice:refresh-period",
    () => {
      refreshPeriod(
        {
          preserveHours: true,
        }
      );
    }
  );

  refreshPeriod(
    {
      preserveHours: true,
    }
  );
}


function updateSimpleInvoiceStatus(
  container,
  status,
  message
) {
  const statusMessage =
    container.querySelector(
      "[data-invoice-status-message]"
    );

  if (!statusMessage) {
    return;
  }

  statusMessage.hidden =
    false;

  statusMessage.classList.remove(
    "invoice-form-status--processing",
    "invoice-form-status--sent",
    "invoice-form-status--failed"
  );

  statusMessage.classList.add(
    `invoice-form-status--${status}`
  );

  statusMessage.replaceChildren();

  if (
    status === "processing"
  ) {
    const spinner =
      document.createElement(
        "span"
      );

    spinner.className =
      "invoice-status-spinner";

    spinner.setAttribute(
      "aria-hidden",
      "true"
    );

    statusMessage.appendChild(
      spinner
    );
  }

  const messageText =
    document.createElement(
      "span"
    );

  messageText.textContent =
    message;

  statusMessage.appendChild(
    messageText
  );
}


function initSimpleInvoiceStatus(
  root = document
) {
  const container = root.matches?.(
    "#simple-invoice-form"
  )
    ? root
    : root.querySelector(
        "#simple-invoice-form"
      );

  if (!container) {
    return;
  }

  const statusUrl =
    container.dataset.statusUrl;

  const downloadUrl =
    container.dataset.downloadUrl;

  if (
    !statusUrl
    || !downloadUrl
  ) {
    return;
  }

  if (
    container.dataset
      .pollingInitialized
    === "true"
  ) {
    return;
  }

  container.dataset
    .pollingInitialized =
      "true";

  container.dataset
    .invoiceProcessing =
      "true";

  const periodMessage =
    container.querySelector(
      "[data-invoice-period-message]"
    );

  const downloadButton =
    container.querySelector(
      "[data-invoice-download]"
    );

  const submitButton =
    container.querySelector(
      'button[type="submit"]'
    );

  updateSimpleInvoicePeriodMessage(
    periodMessage,
    ""
  );

  if (submitButton) {
    submitButton.disabled =
      true;
  }

  updateSimpleInvoiceStatus(
    container,
    "processing",
    container.dataset
      .processingText
  );

  if (downloadButton) {
    downloadButton.disabled =
      true;

    downloadButton.addEventListener(
      "click",
      () => {
        if (
          downloadButton.disabled
        ) {
          return;
        }

        window.location.assign(
          downloadUrl
        );
      }
    );
  }

  const pollingStartedAt =
    Date.now();

  const getNextPollDelay = () => {
    const elapsed =
      Date.now()
      - pollingStartedAt;

    if (
      elapsed
      < SIMPLE_INVOICE_FAST_POLL_DURATION_MS
    ) {
      return (
        SIMPLE_INVOICE_FAST_POLL_INTERVAL_MS
      );
    }

    return (
      SIMPLE_INVOICE_SLOW_POLL_INTERVAL_MS
    );
  };

  const getPollingElapsed = () => (
    Date.now()
    - pollingStartedAt
  );

  const pollingHardStop =
    SIMPLE_INVOICE_PROCESSING_TIMEOUT_MS
    + SIMPLE_INVOICE_POLL_GRACE_MS;

  const pollStatus = async () => {
    if (
      !container.isConnected
    ) {
      return;
    }

    try {
      const response =
        await fetch(
          statusUrl,
          {
            method: "GET",

            headers: {
              "X-Requested-With":
                "XMLHttpRequest",

              Accept:
                "application/json",
            },

            credentials:
              "same-origin",

            cache:
              "no-store",
          }
        );

      if (!response.ok) {
        throw new Error(
          "Invoice status request failed "
          + `with status ${response.status}.`
        );
      }

      const data =
        await response.json();

      if (
        !container.isConnected
      ) {
        return;
      }

      if (
        data.status === "sent"
        && data.can_download
      ) {
        container.dataset
          .invoiceProcessing =
            "false";

        if (downloadButton) {
          downloadButton.disabled =
            false;
        }

        updateSimpleInvoiceStatus(
          container,
          "sent",
          container.dataset
            .sentText
        );

        updateSimpleInvoicePeriodMessage(
          periodMessage,
          ""
        );

        if (submitButton) {
          submitButton.disabled =
            true;
        }

        container.dispatchEvent(
          new CustomEvent(
            "simple-invoice:refresh-period"
          )
        );

        return;
      }

      if (
        data.status === "failed"
      ) {
        container.dataset
          .invoiceProcessing =
            "false";

        updateSimpleInvoiceStatus(
          container,
          "failed",
          container.dataset
            .failedText
        );

        updateSimpleInvoicePeriodMessage(
          periodMessage,
          ""
        );

        container.dispatchEvent(
          new CustomEvent(
            "simple-invoice:refresh-period"
          )
        );

        return;
      }

      container.dataset
        .invoiceProcessing =
          "true";

      updateSimpleInvoiceStatus(
        container,
        "processing",
        container.dataset
          .processingText
      );

      updateSimpleInvoicePeriodMessage(
        periodMessage,
        ""
      );

      if (submitButton) {
        submitButton.disabled =
          true;
      }

    } catch (error) {
      console.error(
        "Simple invoice status request failed:",
        error
      );
    }

    if (
      getPollingElapsed()
      >= pollingHardStop
    ) {
      container.dataset
        .invoiceProcessing =
          "false";

      updateSimpleInvoiceStatus(
        container,
        "failed",
        container.dataset
          .timeoutText
      );

      updateSimpleInvoicePeriodMessage(
        periodMessage,
        ""
      );

      if (submitButton) {
        submitButton.disabled =
          true;
      }

      return;
    }

    window.setTimeout(
      pollStatus,
      getNextPollDelay()
    );
  };

  pollStatus();
}


function initSimpleInvoiceForm(
  root = document
) {
  const form =
    root.querySelector(
      "[data-simple-invoice-form]"
    );

  if (!form) {
    return;
  }

  if (
    form.dataset.initialized
    === "true"
  ) {
    return;
  }

  form.dataset.initialized =
    "true";

  form.dataset.submitting =
    "false";

  form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();

      const targetSelector =
        form.dataset.target;

      const target =
        document.querySelector(
          targetSelector
        );

      if (!target) {
        return;
      }

      const submitButton =
        form.querySelector(
          'button[type="submit"]'
        );

      if (
        submitButton?.dataset
          .periodAllowed
        === "false"
      ) {
        return;
      }

      const originalButtonText =
        submitButton
          ? submitButton.textContent
          : null;

      const loadingButtonText =
        submitButton?.dataset
          .loadingText
        || "Sending invoice...";

      form.dataset.submitting =
        "true";

      if (submitButton) {
        submitButton.disabled =
          true;

        submitButton.textContent =
          loadingButtonText;
      }

      try {
        const response =
          await fetch(
            form.action,
            {
              method:
                form.method,

              body:
                new FormData(
                  form
                ),

              headers: {
                "X-Requested-With":
                  "XMLHttpRequest",
              },

              credentials:
                "same-origin",
            }
          );

        if (!response.ok) {
          throw new Error(
            "Invoice form request failed "
            + `with status ${response.status}.`
          );
        }

        const html =
          await response.text();

        target.outerHTML =
          html;

        const updatedTarget =
          document.querySelector(
            targetSelector
          );

        if (updatedTarget) {
          initSimpleInvoicePostalCodeInput(
            updatedTarget
          );

          initSimpleInvoiceGstAccountNumberInput(
            updatedTarget
          );

          initSimpleInvoiceStatus(
            updatedTarget
          );

          initSimpleInvoicePeriod(
            updatedTarget
          );

          initSimpleInvoiceForm(
            updatedTarget
          );
        }

      } catch (error) {
        console.error(
          "Simple invoice form submit failed:",
          error
        );

        form.dataset.submitting =
          "false";

        if (submitButton) {
          submitButton.textContent =
            originalButtonText;

          submitButton.disabled = (
            submitButton.dataset
              .periodAllowed
            === "false"
          );
        }
      }
    }
  );
}


initSimpleInvoicePostalCodeInput();
initSimpleInvoiceGstAccountNumberInput();

initSimpleInvoiceStatus();

initSimpleInvoicePeriod();
initSimpleInvoiceForm();