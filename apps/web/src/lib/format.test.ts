import { describe, expect, it } from "vitest";

import { distance, duration, pace, wholeNumber } from "@/lib/format";

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
});
