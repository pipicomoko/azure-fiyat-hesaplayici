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

// ── VM Combo (tıklayınca açılan arama dropdown) ───────────────────────────────
function vmComboToggle(comboId) {
  const combo = document.getElementById(comboId);
  if (!combo) return;
  const dropdown = combo.querySelector(".vm-combo-dropdown");
  const isOpen = dropdown.style.display !== "none";
  // Diğer açık combo'ları kapat
  document.querySelectorAll(".vm-combo-dropdown").forEach((d) => {
    d.style.display = "none";
  });
  if (!isOpen) {
    dropdown.style.display = "block";
    const search = dropdown.querySelector(".vm-combo-search");
    if (search) { search.value = ""; vmComboFiltrele(search); search.focus(); }
    // Seçili öğeye scroll
    const secili = dropdown.querySelector("li.selected");
    if (secili) secili.scrollIntoView({ block: "nearest" });
  }
}

function vmComboFiltrele(input) {
  const dropdown = input.closest(".vm-combo-dropdown");
  if (!dropdown) return;
  const aranan = input.value.toLowerCase().trim();
  dropdown.querySelectorAll("li").forEach((li) => {
    const metni = li.textContent.toLowerCase();
    li.style.display = (!aranan || metni.includes(aranan)) ? "" : "none";
  });
}

function vmComboSec(comboId, li) {
  const combo = document.getElementById(comboId);
  if (!combo) return;
  const deger = li.dataset.value;
  const etiket = li.textContent;
  // Label güncelle
  combo.querySelector(".vm-combo-label").textContent = etiket;
  // Seçili class
  combo.querySelectorAll("li").forEach((el) => el.classList.remove("selected"));
  li.classList.add("selected");
  // Hidden select güncelle ve HTMX change tetikle
  const hiddenSelect = combo.querySelector(".vm-combo-hidden");
  hiddenSelect.value = deger;
  hiddenSelect.dispatchEvent(new Event("change", { bubbles: true }));
  // Dropdown kapat
  combo.querySelector(".vm-combo-dropdown").style.display = "none";
}

// Dışarı tıklayınca combo'ları kapat
document.addEventListener("click", (e) => {
  if (!e.target.closest(".vm-combo")) {
    document.querySelectorAll(".vm-combo-dropdown").forEach((d) => {
      d.style.display = "none";
    });
  }
});
