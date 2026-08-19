function applyTheme(theme) {
  const resolvedTheme = theme === "dark" ? "dark" : theme === "pink" ? "pink" : "light";
  document.documentElement.setAttribute("data-theme", resolvedTheme);
  document.documentElement.setAttribute("data-bs-theme", resolvedTheme);
  localStorage.setItem("theme-preference", resolvedTheme);

  const nextTheme =
    resolvedTheme === "light" ? "dark" : resolvedTheme === "dark" ? "pink" : "light";

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    const label = button.querySelector(".theme-toggle-label");
    const icon = button.querySelector(".theme-toggle-icon");
    const darkLabel = button.dataset.themeLabelDark || "Dark";
    const lightLabel = button.dataset.themeLabelLight || "Light";
    const pinkLabel = button.dataset.themeLabelPink || "Pink";

    button.setAttribute("aria-pressed", String(resolvedTheme !== "light"));
    if (label) {
      label.textContent =
        nextTheme === "dark"
          ? darkLabel
          : nextTheme === "pink"
            ? pinkLabel
            : lightLabel;
    }
    if (icon) {
      icon.textContent = nextTheme === "pink" ? "●" : nextTheme === "light" ? "☀" : "◑";
    }
  });
}

function initializeThemeToggle() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(currentTheme);

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    if (button.dataset.themeReady === "true") {
      return;
    }

    button.addEventListener("click", () => {
      const activeTheme = document.documentElement.getAttribute("data-theme") || "light";
      const nextTheme =
        activeTheme === "light" ? "dark" : activeTheme === "dark" ? "pink" : "light";
      applyTheme(nextTheme);
    });
    button.dataset.themeReady = "true";
  });
}

function syncSummaryTotals() {
  const total = document.getElementById("tahmin-toplam");
  const yearly = document.getElementById("tahmin-yillik-toplam");
  const sidebarTotal = document.getElementById("sidebar-aylik-toplam");
  const sidebarYearly = document.getElementById("sidebar-yillik-toplam");

  if (total && sidebarTotal) {
    sidebarTotal.textContent = total.textContent;
  }
  if (yearly && sidebarYearly) {
    sidebarYearly.textContent = yearly.textContent;
  }
}

function initializeDetailsState() {
  document.querySelectorAll("[data-details-key]").forEach((details) => {
    if (details.dataset.detailsReady === "true") {
      return;
    }

    details.addEventListener("toggle", () => {
      const key = details.dataset.detailsKey;
      const container = details.closest(".tahmin-kalemi");
      if (!key || !container) {
        return;
      }

      const input = container.querySelector(`[data-details-state-input="${key}"]`);
      if (input) {
        input.value = details.open ? "true" : "false";
      }
    });
    details.dataset.detailsReady = "true";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initializeThemeToggle();
  initializeDetailsState();
  syncSummaryTotals();
});

document.body.addEventListener("htmx:afterSwap", () => {
  initializeThemeToggle();
  initializeDetailsState();
  syncSummaryTotals();
});

document.body.addEventListener("htmx:afterSettle", syncSummaryTotals);

// ── VM Searchable Select ──────────────────────────────────────────────────────
function vmSelectFiltrele(input) {
  const selectId = input.dataset.target;
  const select = document.getElementById(selectId);
  if (!select) return;
  const aranan = input.value.toLowerCase().trim();
  Array.from(select.options).forEach((opt) => {
    const eslesir = !aranan || opt.text.toLowerCase().includes(aranan) || opt.value.toLowerCase().includes(aranan);
    opt.hidden = !eslesir;
  });
  // Seçili öğe gizlendiyse ilk görüneni seç
  const secili = select.options[select.selectedIndex];
  if (secili && secili.hidden) {
    const ilk = Array.from(select.options).find((o) => !o.hidden);
    if (ilk) {
      select.value = ilk.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
}

function vmSelectSecimGuncelle(select) {
  // Listbox (size>1) seçimi HTMX change trigger'ı için form change olayı üretir
  select.dispatchEvent(new Event("change", { bubbles: true }));
}
