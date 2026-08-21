function applyTheme(theme) {
  const resolvedTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", resolvedTheme);
  document.documentElement.setAttribute("data-bs-theme", resolvedTheme);
  localStorage.setItem("theme-preference", resolvedTheme);

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    const label = button.querySelector(".theme-toggle-label");
    const darkLabel = button.dataset.themeLabelDark || "Dark";
    const lightLabel = button.dataset.themeLabelLight || "Light";
    button.setAttribute("aria-pressed", String(resolvedTheme === "dark"));
    if (label) {
      label.textContent = resolvedTheme === "light" ? darkLabel : lightLabel;
    }
  });
}

function initializeThemeToggle() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(currentTheme === "pink" ? "light" : currentTheme);

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    if (button.dataset.themeReady === "true") {
      return;
    }
    button.addEventListener("click", () => {
      const activeTheme = document.documentElement.getAttribute("data-theme") || "light";
      applyTheme(activeTheme === "light" ? "dark" : "light");
    });
    button.dataset.themeReady = "true";
  });
}

function formatCurrency(amount, currencyCode) {
  const lang = (document.documentElement.lang || "tr").toLowerCase().startsWith("en")
    ? "en-US"
    : "tr-TR";
  try {
    return new Intl.NumberFormat(lang, {
      style: "currency",
      currency: currencyCode || "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch (_err) {
    return `${amount.toFixed(2)} ${currencyCode || "USD"}`;
  }
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

function filtreleUrunListesi(query) {
  const q = (query || "").toLowerCase().trim();
  document.querySelectorAll("#urun-listesi .product-picker__row").forEach((row) => {
    const haystack = row.getAttribute("data-urun-adi") || "";
    row.style.display = !q || haystack.includes(q) ? "" : "none";
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

function vmComboToggle(comboId) {
  const combo = document.getElementById(comboId);
  if (!combo) return;
  const dropdown = combo.querySelector(".vm-combo-dropdown");
  const isOpen = dropdown.style.display !== "none";
  document.querySelectorAll(".vm-combo-dropdown").forEach((d) => {
    d.style.display = "none";
  });
  if (!isOpen) {
    dropdown.style.display = "block";
    const search = dropdown.querySelector(".vm-combo-search");
    if (search) {
      search.value = "";
      vmComboFiltrele(search);
      search.focus();
    }
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
    li.style.display = !aranan || metni.includes(aranan) ? "" : "none";
  });
}

function vmComboSec(comboId, li) {
  const combo = document.getElementById(comboId);
  if (!combo) return;
  const deger = li.dataset.value;
  const etiket = li.textContent;
  combo.querySelector(".vm-combo-label").textContent = etiket;
  combo.querySelectorAll("li").forEach((el) => el.classList.remove("selected"));
  li.classList.add("selected");
  const hiddenSelect = combo.querySelector(".vm-combo-hidden");
  hiddenSelect.value = deger;
  hiddenSelect.dispatchEvent(new Event("change", { bubbles: true }));
  combo.querySelector(".vm-combo-dropdown").style.display = "none";
}

document.addEventListener(
  "change",
  (e) => {
    if (e.target.classList?.contains("vm-combo-search")) {
      e.stopPropagation();
    }
  },
  true,
);

document.addEventListener("keydown", (e) => {
  if (!e.target.classList?.contains("vm-combo-search")) return;
  const combo = e.target.closest(".vm-combo");
  if (!combo) return;
  if (e.key === "Escape") {
    e.preventDefault();
    const dropdown = combo.querySelector(".vm-combo-dropdown");
    if (dropdown) dropdown.style.display = "none";
    return;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    const ilkEslesme = Array.from(combo.querySelectorAll(".vm-combo-list li")).find(
      (li) => li.style.display !== "none",
    );
    if (ilkEslesme) vmComboSec(combo.id, ilkEslesme);
  }
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".vm-combo")) {
    document.querySelectorAll(".vm-combo-dropdown").forEach((d) => {
      d.style.display = "none";
    });
  }
});
