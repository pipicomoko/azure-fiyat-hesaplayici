/**
 * Client/server maliyet formullerinin test edilebilir JS aynasi.
 * Uygulama kodunu DEGISTIRMEZ; FastAPI fiyatlama modeliyle uyumlu birim testleri icin.
 */

function monthlyFromHourly(hourlyRate, hours = 730, quantity = 1) {
  const rate = Number(hourlyRate);
  const hrs = Number(hours);
  const qty = Number(quantity);
  if (![rate, hrs, qty].every((n) => Number.isFinite(n))) {
    throw new TypeError("Invalid numeric input");
  }
  if (hrs < 0 || qty < 0 || rate < 0) {
    throw new RangeError("Negative values are not allowed");
  }
  return rate * hrs * qty;
}

function yearlyFromMonthly(monthly) {
  const m = Number(monthly);
  if (!Number.isFinite(m)) throw new TypeError("Invalid monthly");
  return m * 12;
}

function applyDiscount(amount, percent) {
  const a = Number(amount);
  const p = percent === "" || percent === null || percent === undefined ? 0 : Number(percent);
  if (!Number.isFinite(a) || !Number.isFinite(p)) throw new TypeError("Invalid discount input");
  if (p < 0 || p > 100) throw new RangeError("Discount must be 0-100");
  return a * (1 - p / 100);
}

function formatCurrency(amount, currencyCode = "USD", locale = "tr-TR") {
  const n = Number(amount);
  if (!Number.isFinite(n)) throw new TypeError("Invalid amount");
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currencyCode}`;
  }
}

function validateEstimateName(name) {
  if (name === null || name === undefined) return { ok: false, reason: "null" };
  const trimmed = String(name).trim();
  if (!trimmed) return { ok: false, reason: "empty" };
  if (trimmed.length > 200) return { ok: false, reason: "too_long" };
  if (/[<>]/.test(trimmed)) return { ok: false, reason: "xss_chars" };
  return { ok: true, value: trimmed };
}

function validateHours(hours) {
  const n = Number(hours);
  if (!Number.isFinite(n)) return { ok: false, reason: "nan" };
  if (n < 0) return { ok: false, reason: "negative" };
  if (n > 8760 * 10) return { ok: false, reason: "unrealistic" };
  return { ok: true, value: n };
}

function parseRetailPriceItem(item) {
  if (!item || typeof item !== "object") throw new TypeError("Invalid API item");
  const price = Number(item.retailPrice);
  if (!Number.isFinite(price)) throw new TypeError("Missing retailPrice");
  return {
    productName: String(item.productName || ""),
    meterName: String(item.meterName || ""),
    retailPrice: price,
    type: String(item.type || "Consumption"),
    armSkuName: item.armSkuName ? String(item.armSkuName) : null,
  };
}

function sumLineItems(items) {
  if (!Array.isArray(items)) throw new TypeError("items must be array");
  return items.reduce((acc, it) => {
    const t = Number(it.aylik_tutar ?? it.monthly ?? 0);
    if (!Number.isFinite(t)) throw new TypeError("Invalid line amount");
    return acc + t;
  }, 0);
}

module.exports = {
  monthlyFromHourly,
  yearlyFromMonthly,
  applyDiscount,
  formatCurrency,
  validateEstimateName,
  validateHours,
  parseRetailPriceItem,
  sumLineItems,
};
