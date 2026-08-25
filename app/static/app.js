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

function initializeRaporExport() {
  document.querySelectorAll("[data-rapor-export]").forEach((bar) => {
    if (bar.dataset.raporReady === "true") {
      return;
    }

    const hepsiniBtn = bar.querySelector("[data-rapor-hepsini]");
    const exportBtn = bar.querySelector("[data-rapor-export-secilen]");
    const tablo =
      bar.parentElement?.querySelector("[data-rapor-tablo]") ||
      document.querySelector("[data-rapor-tablo]");
    const hepsiniCb = tablo
      ? tablo.querySelector("[data-rapor-hepsini-cb]")
      : document.querySelector("[data-rapor-hepsini-cb]");
    const labelTemplate = bar.dataset.labelTemplate || "Export selected ({n})";
    const exportUrl = bar.dataset.exportUrl || "/raporlar/excel";

    function secilenKutular() {
      const kok = tablo || document;
      return Array.from(kok.querySelectorAll("[data-rapor-sec]")).filter((cb) => {
        const satir = cb.closest("tr");
        return !satir || satir.style.display !== "none";
      });
    }

    function secilenIdler() {
      return secilenKutular()
        .filter((cb) => cb.checked)
        .map((cb) => cb.value)
        .filter(Boolean);
    }

    function guncelle() {
      const idler = secilenIdler();
      const n = idler.length;
      const kutular = secilenKutular();
      if (exportBtn) {
        exportBtn.textContent = labelTemplate.replace("{n}", String(n));
        exportBtn.disabled = n === 0;
        exportBtn.setAttribute("aria-disabled", n === 0 ? "true" : "false");
      }
      if (hepsiniBtn) {
        hepsiniBtn.disabled = kutular.length === 0;
      }
      if (hepsiniCb && kutular.length) {
        hepsiniCb.checked = n === kutular.length && n > 0;
        hepsiniCb.indeterminate = n > 0 && n < kutular.length;
      } else if (hepsiniCb) {
        hepsiniCb.checked = false;
        hepsiniCb.indeterminate = false;
      }
    }

    function hepsiniSec() {
      secilenKutular().forEach((cb) => {
        cb.checked = true;
      });
      guncelle();
    }

    function exportSecilen() {
      const idler = secilenIdler();
      if (!idler.length) {
        return;
      }
      const params = new URLSearchParams();
      const kisi = bar.dataset.filtreKisi || "";
      const birim = bar.dataset.filtreBirim || "";
      const baslangic = bar.dataset.filtreBaslangic || "";
      const bitis = bar.dataset.filtreBitis || "";
      if (kisi) params.set("kisi", kisi);
      if (birim) params.set("birim", birim);
      if (baslangic) params.set("baslangic", baslangic);
      if (bitis) params.set("bitis", bitis);
      idler.forEach((id) => params.append("ids", id));
      window.location.href = `${exportUrl}?${params.toString()}`;
    }

    if (hepsiniBtn) {
      hepsiniBtn.addEventListener("click", hepsiniSec);
    }
    if (exportBtn) {
      exportBtn.addEventListener("click", exportSecilen);
    }
    if (hepsiniCb) {
      hepsiniCb.addEventListener("change", () => {
        const isaretle = hepsiniCb.checked;
        secilenKutular().forEach((cb) => {
          cb.checked = isaretle;
        });
        guncelle();
      });
    }
    const kok = tablo || document;
    kok.querySelectorAll("[data-rapor-sec]").forEach((cb) => {
      cb.addEventListener("change", guncelle);
    });

    // Istemci tarafi filtre (gecmis arama) sonrasi sayaci guncelle
    document.addEventListener("gecmis-filtre-degisti", guncelle);

    guncelle();
    bar.dataset.raporReady = "true";
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

function afhIsoTarih(d) {
  const yil = d.getFullYear();
  const ay = String(d.getMonth() + 1).padStart(2, "0");
  const gun = String(d.getDate()).padStart(2, "0");
  return `${yil}-${ay}-${gun}`;
}

function afhBirAyOnce(d) {
  let yil = d.getFullYear();
  let ay = d.getMonth() - 1;
  if (ay < 0) {
    ay = 11;
    yil -= 1;
  }
  const sonGun = new Date(yil, ay + 1, 0).getDate();
  const gun = Math.min(d.getDate(), sonGun);
  return new Date(yil, ay, gun);
}

function afhVarsayilanTarihAraligi(refDate) {
  const kaynak = refDate ? new Date(refDate) : new Date();
  const bitis = new Date(kaynak.getFullYear(), kaynak.getMonth(), kaynak.getDate());
  return {
    baslangic: afhIsoTarih(afhBirAyOnce(bitis)),
    bitis: afhIsoTarih(bitis),
  };
}

function afhTarihFiltreTuru(input) {
  if (!input || String(input.type).toLowerCase() !== "date") {
    return null;
  }
  const anahtar = `${input.name || ""} ${input.id || ""}`.toLowerCase();
  if (anahtar.includes("baslangic")) return "baslangic";
  if (anahtar.includes("bitis")) return "bitis";
  return null;
}

function afhBosTarihFiltreleriniDoldur() {
  const aralik = afhVarsayilanTarihAraligi();
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    if (input.value) {
      return;
    }
    const tur = afhTarihFiltreTuru(input);
    if (tur === "baslangic") {
      input.value = aralik.baslangic;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } else if (tur === "bitis") {
      input.value = aralik.bitis;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
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

let _departmanComboSayac = 0;

function comboNormalize(deger) {
  return String(deger || "")
    .toLocaleLowerCase("tr-TR")
    .trim();
}

function initializeDepartmanCombo() {
  document.querySelectorAll("[data-departman-combo]").forEach((kok) => {
    if (kok.dataset.comboReady === "true") {
      return;
    }
    kok.dataset.comboReady = "true";
    setupDepartmanCombo(kok);
  });
}

function setupDepartmanCombo(kok) {
  const native = kok.querySelector("select[name='birim']");
  const input = kok.querySelector("[role='combobox']");
  const list = kok.querySelector("[role='listbox']");
  if (!native || !input || !list) {
    return;
  }

  _departmanComboSayac += 1;
  const uid = `departman-combo-${_departmanComboSayac}`;
  list.id = uid + "-list";
  input.setAttribute("aria-controls", list.id);
  const options = Array.from(list.querySelectorAll("[role='option']"));
  options.forEach((opt, i) => {
    opt.id = `${uid}-opt-${i}`;
  });

  native.setAttribute("tabindex", "-1");
  native.setAttribute("aria-hidden", "true");
  kok.classList.add("is-ready");

  let activeIndex = -1;

  function gorunenSecenekler() {
    return options.filter((opt) => !opt.hidden);
  }

  function seciliEtiket() {
    const secili = native.options[native.selectedIndex];
    return secili ? secili.textContent : input.dataset.emptyLabel || "";
  }

  function kapat(digerleriniDe) {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    kok.classList.remove("is-open");
    if (digerleriniDe) {
      document.querySelectorAll("[data-departman-combo].is-open").forEach((diger) => {
        if (diger !== kok) {
          const digerInput = diger.querySelector("[role='combobox']");
          const digerList = diger.querySelector("[role='listbox']");
          if (digerList) digerList.hidden = true;
          if (digerInput) {
            digerInput.setAttribute("aria-expanded", "false");
            digerInput.removeAttribute("aria-activedescendant");
          }
          diger.classList.remove("is-open");
        }
      });
    }
  }

  function aktifYap(opt) {
    options.forEach((el) => el.classList.remove("is-active"));
    if (!opt) {
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    opt.classList.add("is-active");
    activeIndex = options.indexOf(opt);
    input.setAttribute("aria-activedescendant", opt.id);
    opt.scrollIntoView({ block: "nearest" });
  }

  function filtrele(sorgu, hepsiniGoster) {
    const q = comboNormalize(sorgu);
    options.forEach((opt) => {
      const eslesir =
        hepsiniGoster ||
        !q ||
        comboNormalize(opt.dataset.label).includes(q) ||
        comboNormalize(opt.dataset.value).includes(q);
      opt.hidden = !eslesir;
    });
  }

  function ac(hepsiniGoster) {
    document.querySelectorAll("[data-departman-combo].is-open").forEach((diger) => {
      if (diger !== kok) {
        const digerInput = diger.querySelector("[role='combobox']");
        const digerList = diger.querySelector("[role='listbox']");
        if (digerList) digerList.hidden = true;
        if (digerInput) {
          digerInput.setAttribute("aria-expanded", "false");
          digerInput.removeAttribute("aria-activedescendant");
        }
        diger.classList.remove("is-open");
      }
    });
    filtrele(hepsiniGoster ? "" : input.value, Boolean(hepsiniGoster));
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    kok.classList.add("is-open");
    const gorunen = gorunenSecenekler();
    const mevcut = options.find(
      (opt) => opt.dataset.value === native.value && !opt.hidden,
    );
    aktifYap(mevcut || gorunen[0] || null);
  }

  function uygula(opt) {
    if (!opt) {
      return;
    }
    native.value = opt.dataset.value || "";
    native.dispatchEvent(new Event("change", { bubbles: true }));
    input.value = opt.dataset.label || "";
    options.forEach((el) => {
      el.setAttribute("aria-selected", el === opt ? "true" : "false");
    });
    kapat(false);
  }

  function yazilanlaEsle() {
    const aktif = options.find((opt) => opt.classList.contains("is-active") && !opt.hidden);
    if (!list.hidden && aktif) {
      uygula(aktif);
      return;
    }
    const q = comboNormalize(input.value);
    if (!q || q === comboNormalize(input.dataset.emptyLabel)) {
      const tumu = options.find((opt) => opt.dataset.value === "");
      uygula(tumu);
      return;
    }
    const adaylar = options.filter(
      (opt) =>
        comboNormalize(opt.dataset.label).includes(q) ||
        comboNormalize(opt.dataset.value).includes(q),
    );
    const tam = adaylar.find(
      (opt) =>
        comboNormalize(opt.dataset.label) === q || comboNormalize(opt.dataset.value) === q,
    );
    if (tam) {
      uygula(tam);
    } else if (adaylar.length === 1) {
      uygula(adaylar[0]);
    } else {
      input.value = seciliEtiket();
      kapat(false);
    }
  }

  input.addEventListener("click", () => {
    if (list.hidden) {
      ac(true);
    }
  });

  input.addEventListener("input", () => {
    ac(false);
    const gorunen = gorunenSecenekler();
    aktifYap(gorunen[0] || null);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      input.value = seciliEtiket();
      kapat(false);
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (list.hidden) {
        ac(true);
        return;
      }
      const gorunen = gorunenSecenekler();
      if (!gorunen.length) {
        return;
      }
      const mevcut = gorunen.findIndex((opt) => opt.classList.contains("is-active"));
      let sonraki = mevcut;
      if (e.key === "ArrowDown") {
        sonraki = mevcut < gorunen.length - 1 ? mevcut + 1 : 0;
      } else {
        sonraki = mevcut > 0 ? mevcut - 1 : gorunen.length - 1;
      }
      aktifYap(gorunen[sonraki]);
      return;
    }
    if (e.key === "Enter") {
      if (!list.hidden) {
        e.preventDefault();
        const aktif = options.find((opt) => opt.classList.contains("is-active") && !opt.hidden);
        if (aktif) {
          uygula(aktif);
        } else {
          yazilanlaEsle();
        }
      }
      return;
    }
    if (e.key === "Tab") {
      if (!list.hidden) {
        yazilanlaEsle();
      }
    }
  });

  list.addEventListener("mousedown", (e) => {
    const opt = e.target.closest("[role='option']");
    if (!opt) {
      return;
    }
    e.preventDefault();
    uygula(opt);
  });

  input.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!kok.contains(document.activeElement)) {
        if (!list.hidden) {
          yazilanlaEsle();
        }
      }
    }, 0);
  });

  const form = kok.closest("form");
  if (form) {
    form.addEventListener("submit", yazilanlaEsle);
  }
}

document.addEventListener("click", (e) => {
  document.querySelectorAll("[data-departman-combo].is-open").forEach((kok) => {
    if (!kok.contains(e.target)) {
      const input = kok.querySelector("[role='combobox']");
      if (input) {
        input.dispatchEvent(new Event("blur"));
      }
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  initializeThemeToggle();
  initializeDetailsState();
  initializeRaporExport();
  initializeDepartmanCombo();
  afhBosTarihFiltreleriniDoldur();
  syncSummaryTotals();
});

document.body.addEventListener("htmx:afterSwap", () => {
  initializeThemeToggle();
  initializeDetailsState();
  initializeRaporExport();
  initializeDepartmanCombo();
  afhBosTarihFiltreleriniDoldur();
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
