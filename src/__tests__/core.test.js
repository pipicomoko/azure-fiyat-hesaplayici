const {
  monthlyFromHourly,
  yearlyFromMonthly,
  applyDiscount,
  formatCurrency,
  validateEstimateName,
  validateHours,
  parseRetailPriceItem,
  sumLineItems,
} = require("../cost-core");

describe("Cost calculation formula", () => {
  test("hourly * 730 hours matches Azure monthly default", () => {
    expect(monthlyFromHourly(0.096, 730, 1)).toBeCloseTo(70.08, 2);
  });

  test("quantity multiplies monthly cost", () => {
    expect(monthlyFromHourly(0.1, 730, 3)).toBeCloseTo(219.0, 2);
  });

  test("yearly = monthly * 12", () => {
    expect(yearlyFromMonthly(100)).toBe(1200);
  });

  test("Windows+SQL style sum of components", () => {
    const compute = monthlyFromHourly(0.12, 730);
    const os = monthlyFromHourly(0.092, 730);
    const sql = monthlyFromHourly(0.4, 730);
    expect(compute + os + sql).toBeCloseTo(446.76, 2);
  });
});

describe("Input validation logic", () => {
  test("estimate name required", () => {
    expect(validateEstimateName("")).toEqual({ ok: false, reason: "empty" });
    expect(validateEstimateName("   ")).toEqual({ ok: false, reason: "empty" });
    expect(validateEstimateName(null).ok).toBe(false);
  });

  test("estimate name accepts normal values", () => {
    expect(validateEstimateName("E2E-Test")).toEqual({ ok: true, value: "E2E-Test" });
  });

  test("rejects XSS-ish angle brackets", () => {
    expect(validateEstimateName("<script>").reason).toBe("xss_chars");
  });

  test("hours validation", () => {
    expect(validateHours(730).ok).toBe(true);
    expect(validateHours(-1).reason).toBe("negative");
    expect(validateHours("abc").reason).toBe("nan");
    expect(validateHours(0).ok).toBe(true);
  });
});

describe("Price formatter", () => {
  test("formats USD in tr-TR", () => {
    const out = formatCurrency(70.08, "USD", "tr-TR");
    expect(out).toMatch(/70[,.]08/);
    expect(out).toMatch(/\$|USD|US\$/);
  });

  test("invalid amount throws", () => {
    expect(() => formatCurrency(NaN)).toThrow(TypeError);
  });
});

describe("API response parsing", () => {
  test("parses retail price item", () => {
    const parsed = parseRetailPriceItem({
      productName: "Virtual Machines Dv3 Series",
      meterName: "D2 v3",
      retailPrice: 0.12,
      type: "Consumption",
      armSkuName: "Standard_D2_v3",
    });
    expect(parsed.retailPrice).toBe(0.12);
    expect(parsed.armSkuName).toBe("Standard_D2_v3");
  });

  test("rejects missing price", () => {
    expect(() => parseRetailPriceItem({ productName: "x" })).toThrow();
  });

  test("sums line items", () => {
    expect(sumLineItems([{ aylik_tutar: 10 }, { monthly: 5.5 }])).toBeCloseTo(15.5);
  });
});

describe("Edge cases", () => {
  test("0 hours => 0 cost", () => {
    expect(monthlyFromHourly(1.5, 0, 1)).toBe(0);
  });

  test("max discount 100% => 0", () => {
    expect(applyDiscount(200, 100)).toBe(0);
  });

  test("negative rate throws", () => {
    expect(() => monthlyFromHourly(-1, 730)).toThrow(RangeError);
  });

  test("special chars in name", () => {
    expect(validateEstimateName("Test & Co. #1").ok).toBe(true);
  });

  test("discount out of range", () => {
    expect(() => applyDiscount(10, 101)).toThrow(RangeError);
    expect(() => applyDiscount(10, -1)).toThrow(RangeError);
  });
});
