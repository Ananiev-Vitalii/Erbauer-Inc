function initWorkHours(root = document) {
  const content = root.matches?.(
    "[data-work-hours-content]"
  )
    ? root
    : root.querySelector(
        "[data-work-hours-content]"
      );

  if (!content) {
    return;
  }

  if (
    content.dataset.initialized
    === "true"
  ) {
    return;
  }

  content.dataset.initialized =
    "true";

  const refreshUrl =
    content.dataset.refreshUrl;

  const updateUrl =
    content.dataset.updateUrl;

  const requestErrorText =
    content.dataset.requestErrorText
    || "Unable to update work hours.";

  const invalidHoursText =
    content.dataset.invalidHoursText
    || (
      "Enter hours using numbers only, "
      + "from 0 to 24."
    );

  const maxHoursText =
    content.dataset.maxHoursText
    || (
      "Hours cannot exceed "
      + "24 hours per day."
    );

  const decimalHoursText =
    content.dataset.decimalHoursText
    || (
      "Hours can have at most "
      + "two decimal places."
    );

  const stepHoursText =
    content.dataset.stepHoursText
    || (
      "Hours must be entered "
      + "in 0.10-hour increments."
    );

  const monthSelect =
    content.querySelector(
      "[data-work-hours-month]"
    );

  const employeeSelect =
    content.querySelector(
      "[data-work-hours-employee]"
    );

  const feedback =
    content.querySelector(
      "[data-work-hours-feedback]"
    );

  const csrfInput =
    content.querySelector(
      '[name="csrfmiddlewaretoken"]'
    );

  const csrfToken =
    csrfInput?.value || "";

  let refreshController = null;

  const clearFeedback = () => {
    if (!feedback) {
      return;
    }

    feedback.hidden = true;
    feedback.textContent = "";

    feedback.classList.remove(
      "work-hours-feedback--error"
    );
  };

  const showError = (message) => {
    if (!feedback) {
      return;
    }

    feedback.textContent =
      message || requestErrorText;

    feedback.hidden = false;

    feedback.classList.add(
      "work-hours-feedback--error"
    );
  };

  /*
   * Only digits plus one decimal separator
   * are allowed to physically exist
   * inside the input.
   *
   * Examples:
   * 8
   * 8.5
   * 8,5
   * 24.00
   */
  const hasAllowedInputShape = (
    value
  ) => {
    if (value === "") {
      return true;
    }

    return (
      /^\d+(?:[.,]\d*)?$/
        .test(value)
    );
  };

  const getProspectiveValue = (
    input,
    insertedText
  ) => {
    const start =
      input.selectionStart
      ?? input.value.length;

    const end =
      input.selectionEnd
      ?? input.value.length;

    return (
      input.value.slice(
        0,
        start
      )
      + insertedText
      + input.value.slice(
        end
      )
    );
  };

  const validateHoursValue = (
    rawValue,
    {
      allowPartial = false,
    } = {}
  ) => {
    const value =
      rawValue.trim();

    if (value === "") {
      return {
        valid: true,
        message: "",
      };
    }

    const normalized =
      value.replace(
        ",",
        "."
      );

    if (
      !/^\d+(?:\.\d*)?$/
        .test(normalized)
    ) {
      return {
        valid: false,
        message:
          invalidHoursText,
      };
    }

    if (
      allowPartial
      && normalized.endsWith(".")
    ) {
      return {
        valid: true,
        message: "",
      };
    }

    const decimalParts =
      normalized.split(".");

    if (
      decimalParts.length === 2
      && decimalParts[1].length > 2
    ) {
      return {
        valid: false,
        message:
          decimalHoursText,
      };
    }

    const numericValue =
      Number(normalized);

    if (
      !Number.isFinite(
        numericValue
      )
    ) {
      return {
        valid: false,
        message:
          invalidHoursText,
      };
    }

    if (numericValue > 24) {
      return {
        valid: false,
        message:
          maxHoursText,
      };
    }

    /*
     * Work hours are entered only
     * in 0.10-hour increments.
     *
     * Multiplying by 10 avoids
     * common floating-point issues
     * when checking decimals.
     */
    const tenths =
      numericValue * 10;

    const isValidStep =
      Math.abs(
        tenths
        - Math.round(tenths)
      ) < 1e-9;

    if (!isValidStep) {
      return {
        valid: false,
        message:
          stepHoursText,
      };
    }

    return {
      valid: true,
      message: "",
    };
  };

  const setInputValidationState = (
    input,
    {
      allowPartial = false,
    } = {}
  ) => {
    const day =
      input.closest(
        "[data-work-hours-day]"
      );

    const result =
      validateHoursValue(
        input.value,
        {
          allowPartial,
        }
      );

    if (result.valid) {
      day?.classList.remove(
        "work-hours-day--error"
      );

      clearFeedback();

      return result;
    }

    day?.classList.add(
      "work-hours-day--error"
    );

    showError(
      result.message
    );

    return result;
  };

  const buildRefreshParams = () => {
    const params =
      new URLSearchParams();

    params.set(
      "month",
      monthSelect?.value || ""
    );

    params.set(
      "employee",
      employeeSelect?.value || ""
    );

    params.set(
      "partial",
      "1"
    );

    return params;
  };

  const updateBrowserUrl = (
    monthValue,
    employeeValue
  ) => {
    const url = new URL(
      window.location.href
    );

    url.searchParams.set(
      "month",
      monthValue
    );

    url.searchParams.set(
      "employee",
      employeeValue
    );

    url.searchParams.delete(
      "partial"
    );

    window.history.replaceState(
      {},
      "",
      url
    );
  };

  const refreshCalendars =
    async () => {
      if (
        !refreshUrl
        || !monthSelect
        || !employeeSelect
      ) {
        return;
      }

      if (refreshController) {
        refreshController.abort();
      }

      refreshController =
        new AbortController();

      const selectedMonth =
        monthSelect.value;

      const selectedEmployee =
        employeeSelect.value;

      monthSelect.disabled = true;
      employeeSelect.disabled = true;

      clearFeedback();

      const params =
        buildRefreshParams();

      try {
        const response =
          await fetch(
            `${refreshUrl}?${params.toString()}`,
            {
              method: "GET",
              headers: {
                "X-Requested-With":
                  "XMLHttpRequest",
              },
              credentials:
                "same-origin",
              cache:
                "no-store",
              signal:
                refreshController.signal,
            }
          );

        if (!response.ok) {
          throw new Error(
            "Work hours request failed "
            + `with status ${response.status}.`
          );
        }

        const html =
          await response.text();

        if (!content.isConnected) {
          return;
        }

        content.outerHTML = html;

        updateBrowserUrl(
          selectedMonth,
          selectedEmployee
        );

        const updatedContent =
          document.querySelector(
            "[data-work-hours-content]"
          );

        if (updatedContent) {
          initWorkHours(
            updatedContent
          );
        }

      } catch (error) {
        if (
          error.name === "AbortError"
        ) {
          return;
        }

        console.error(
          "Work hours refresh failed:",
          error
        );

        monthSelect.disabled = false;
        employeeSelect.disabled = false;

        showError(
          requestErrorText
        );
      }
    };

  monthSelect?.addEventListener(
    "change",
    refreshCalendars
  );

  employeeSelect?.addEventListener(
    "change",
    refreshCalendars
  );

  const inputs =
    content.querySelectorAll(
      "[data-work-hours-input]"
    );

  inputs.forEach((input) => {
    input.dataset.lastAllowedValue =
      input.value;

    /*
     * Desktop keyboard protection.
     *
     * Letters, arithmetic operators,
     * scientific notation, minus, plus,
     * equals etc. never enter the input.
     */
    input.addEventListener(
      "keydown",
      (event) => {
        if (
          event.ctrlKey
          || event.metaKey
          || event.altKey
        ) {
          return;
        }

        if (
          event.key === "Enter"
        ) {
          event.preventDefault();

          input.blur();

          return;
        }

        if (
          event.key.length !== 1
        ) {
          return;
        }

        if (
          !/[\d.,]/.test(
            event.key
          )
        ) {
          event.preventDefault();

          showError(
            invalidHoursText
          );

          return;
        }

        const prospectiveValue =
          getProspectiveValue(
            input,
            event.key
          );

        if (
          prospectiveValue.length > 5
          || !hasAllowedInputShape(
            prospectiveValue
          )
        ) {
          event.preventDefault();

          showError(
            invalidHoursText
          );
        }
      }
    );

    /*
     * beforeinput also protects mobile
     * keyboards and browsers where keydown
     * is not enough.
     */
    input.addEventListener(
      "beforeinput",
      (event) => {
        if (
          !event.inputType
            ?.startsWith("insert")
        ) {
          return;
        }

        if (
          event.inputType
          === "insertFromPaste"
        ) {
          return;
        }

        if (
          event.data === null
        ) {
          return;
        }

        const prospectiveValue =
          getProspectiveValue(
            input,
            event.data
          );

        if (
          prospectiveValue.length > 5
          || !hasAllowedInputShape(
            prospectiveValue
          )
        ) {
          event.preventDefault();

          showError(
            invalidHoursText
          );
        }
      }
    );

    /*
     * Reject invalid clipboard content
     * rather than transforming something
     * dangerous such as "9-9" into "99".
     */
    input.addEventListener(
      "paste",
      (event) => {
        const pastedText =
          event.clipboardData
            ?.getData("text")
            ?.trim()
          ?? "";

        const prospectiveValue =
          getProspectiveValue(
            input,
            pastedText
          );

        if (
          prospectiveValue.length > 5
          || !hasAllowedInputShape(
            prospectiveValue
          )
        ) {
          event.preventDefault();

          showError(
            invalidHoursText
          );
        }
      }
    );

    /*
     * Final fallback for unusual/mobile
     * browsers.
     *
     * If somehow an illegal character
     * reaches the input, restore the last
     * structurally valid value instead of
     * stripping characters and accidentally
     * creating another number.
     */
    input.addEventListener(
      "input",
      () => {
        if (
          input.value.length > 5
          || !hasAllowedInputShape(
            input.value
          )
        ) {
          input.value =
            input.dataset
              .lastAllowedValue
            ?? "";

          showError(
            invalidHoursText
          );

          return;
        }

        input.dataset.lastAllowedValue =
          input.value;

        setInputValidationState(
          input,
          {
            allowPartial: true,
          }
        );
      }
    );

    input.addEventListener(
      "change",
      async () => {
        if (!updateUrl) {
          return;
        }

        const day =
          input.closest(
            "[data-work-hours-day]"
          );

        const calendar =
          input.closest(
            "[data-work-hours-calendar]"
          );

        if (
          !day
          || !calendar
        ) {
          return;
        }

        const validation =
          setInputValidationState(
            input,
            {
              allowPartial: false,
            }
          );

        if (!validation.valid) {
          return;
        }

        const workDate =
          input.dataset.workDate;

        const attemptedValue =
          input.value;

        day.classList.remove(
          "work-hours-day--error"
        );

        day.classList.add(
          "work-hours-day--saving"
        );

        input.disabled = true;

        clearFeedback();

        const formData =
          new FormData();

        formData.append(
          "work_date",
          workDate
        );

        formData.append(
          "hours",
          attemptedValue
        );

        formData.append(
          "csrfmiddlewaretoken",
          csrfToken
        );

        try {
          const response =
            await fetch(
              updateUrl,
              {
                method: "POST",
                body: formData,
                headers: {
                  "X-Requested-With":
                    "XMLHttpRequest",
                  Accept:
                    "application/json",
                },
                credentials:
                  "same-origin",
              }
            );

          let data = null;

          try {
            data =
              await response.json();
          } catch {
            data = null;
          }

          if (
            !response.ok
            || !data?.success
          ) {
            throw new Error(
              data?.message
              || requestErrorText
            );
          }

          input.value =
            data.hours || "";

          input.dataset.lastAllowedValue =
            input.value;

          day.classList.toggle(
            "work-hours-day--filled",
            Boolean(
              data.has_hours
            )
          );

          day.classList.remove(
            "work-hours-day--error"
          );

          const total =
            calendar.querySelector(
              "[data-month-total]"
            );

          if (total) {
            total.textContent =
              data.month_total;
          }

          clearFeedback();

        } catch (error) {
          console.error(
            "Work hours update failed:",
            error
          );

          /*
           * Server-rejected values stay visible
           * so the employee can correct them.
           */
          input.value =
            attemptedValue;

          input.dataset.lastAllowedValue =
            attemptedValue;

          day.classList.add(
            "work-hours-day--error"
          );

          showError(
            error.message
            || requestErrorText
          );

        } finally {
          day.classList.remove(
            "work-hours-day--saving"
          );

          input.disabled = false;
        }
      }
    );
  });
}


initWorkHours();