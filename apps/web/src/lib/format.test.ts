import { describe, expect, it, vi } from "vitest";

import {
  calendarDay,
  centimetres,
  decimal,
  decoupling,
  distance,
  distanceName,
  duration,
  pace,
  perKg,
  signed,
  wholeNumber,
  zoneRange,
} from "@/lib/format";

describe("formatting matches makerundev.format", () => {
  it.each([
    [3000, "3.00 km"],
    [1125, "1.12 km"],
    [21370.4, "21.37 km"],
    [999, "1.00 km"],
  ])("distance(%s) is %s", (metres, expected) => {
    expect(distance(metres)).toBe(expected);
  });

  it.each([
    [0, "0:00"],
    [59.5, "1:00"],
    [60.5, "1:00"],
    [61.5, "1:02"],
    [3599.5, "1:00:00"],
    [7060.4, "1:57:40"],
  ])("duration(%s) is %s", (seconds, expected) => {
    expect(duration(seconds)).toBe(expected);
  });

  it.each([
    [null, "-"],
    [333.3, "5:33 /km"],
    [288.5, "4:48 /km"],
    [3599.6, "1:00:00 /km"],
  ])("pace(%s) is %s", (secondsPerKm, expected) => {
    expect(pace(secondsPerKm)).toBe(expected);
  });

  it.each([
    [140.5, "140"],
    [141.5, "142"],
    [null, "-"],
  ])("wholeNumber(%s) is %s", (value, expected) => {
    expect(wholeNumber(value)).toBe(expected);
  });

  it.each([
    [52.25, "52.2"],
    [47.54, "47.5"],
  ])("decimal(%s, 1) is %s", (value, expected) => {
    expect(decimal(value, 1)).toBe(expected);
  });

  it.each([
    [0.4, "0"],
    [-0.4, "0"],
    [0.5, "0"],
    [2.5, "+2"],
    [3.5, "+4"],
    [-2.5, "-2"],
    [-3.6, "-4"],
    [12, "+12"],
  ])("signed(%s) is %s", (value, expected) => {
    expect(signed(value)).toBe(expected);
  });

  it.each([
    [400, "400 m"],
    [402.5, "402.5 m"],
    [1000, "1 km"],
    [1609.344, "1 mile"],
    [3218.688, "2 miles"],
    [11265.408, "7 miles"],
    [15000, "15 km"],
    [21097.5, "Half marathon"],
    [42195, "Marathon"],
  ])("distanceName(%s) is %s", (metres, expected) => {
    expect(distanceName(metres)).toBe(expected);
  });

  it.each([
    [4.75, "+4.8%"],
    [0, "+0.0%"],
    [-2.04, "-2.0%"],
    [null, "-"],
  ])("decoupling(%s) is %s", (value, expected) => {
    expect(decoupling(value)).toBe(expected);
  });

  it.each([
    [250 / 70, "3.57 W/kg"],
    [234 / 70, "3.34 W/kg"],
  ])("perKg(%s) is %s", (value, expected) => {
    expect(perKg(value)).toBe(expected);
  });

  it.each([
    [85, "8.5 cm"],
    [84, "8.4 cm"],
  ])("centimetres(%s) is %s", (millimetres, expected) => {
    expect(centimetres(millimetres)).toBe(expected);
  });

  it.each([
    [null, 110, "up to 110 bpm"],
    [111, 134, "111-134 bpm"],
    [135, null, "135 bpm and up"],
  ])("zoneRange(%s, %s) is %s", (low, high, expected) => {
    expect(zoneRange(low, high)).toBe(expected);
  });
});

describe("calendar dates", () => {
  it("shows a calendar date as the date it names, also in a zone behind UTC", async () => {
    expect([calendarDay("2026-03-01"), calendarDay("2026-12-31")]).toEqual(["1 Mar 2026", "31 Dec 2026"]);
    const zone = process.env.TZ;
    process.env.TZ = "America/Los_Angeles";
    try {
      vi.resetModules();
      const behindUtc = await import("@/lib/format");
      expect(behindUtc.calendarDay("2026-03-01")).toBe("1 Mar 2026");
    } finally {
      process.env.TZ = zone;
      vi.resetModules();
    }
  });
});
