import { describe, expect, it } from "vitest";

import { addDays, daysBetween, fmt, toISODate } from "../lib/format";

describe("format", () => {
  it("formatea segun el idioma", () => {
    expect(fmt(1.5, "es", 1)).toBe("1,5");
    expect(fmt(1.5, "en", 1)).toBe("1.5");
    expect(fmt(null, "es")).toBe("—");
  });

  it("suma dias sin desfase de zona horaria", () => {
    expect(addDays("2026-07-01", 15)).toBe("2026-07-16");
    expect(addDays("2026-12-25", 10)).toBe("2027-01-04");
  });

  it("calcula dias entre fechas ISO", () => {
    expect(daysBetween("2026-07-01", "2026-07-31")).toBe(30);
  });

  it("convierte Date a ISO local", () => {
    expect(toISODate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
