document.addEventListener("DOMContentLoaded", function () {
  const phoneInput = document.querySelector(".contacts__input--phone");
  if (!phoneInput) return;

  const formatCanadianPhone = (value) => {
    const digits = value.replace(/\D/g, "").slice(0, 10);

    if (digits.length === 0) return "";
    if (digits.length < 4) return `(${digits}`;
    if (digits.length < 7) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
  };

  phoneInput.addEventListener("input", function (event) {
    event.target.value = formatCanadianPhone(event.target.value);
  });

  phoneInput.addEventListener("paste", function (event) {
    event.preventDefault();
    const pasted = (event.clipboardData || window.clipboardData).getData("text");
    phoneInput.value = formatCanadianPhone(pasted);
  });
});