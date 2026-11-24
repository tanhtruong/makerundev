export function roundHalfEven(value: number, digits = 0): number {
  const scale = 10 ** digits;
  const scaled = value * scale;
  const floor = Math.floor(scaled);
  const fraction = scaled - floor;
  if (fraction === 0.5) {
    return (floor % 2 === 0 ? floor : floor + 1) / scale;
  }
  return Math.round(scaled) / scale;
}

export function decimal(value: number, digits: number): string {
  return roundHalfEven(value, digits).toFixed(digits);
}

export function distance(metres: number): string {
  return `${decimal(metres / 1000, 2)} km`;
}

export function duration(seconds: number): string {
  const total = roundHalfEven(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = String(secs).padStart(2, "0");
  return hours ? `${hours}:${mm}:${ss}` : `${minutes}:${ss}`;
}

export function pace(secondsPerKm: number | null): string {
  return secondsPerKm === null ? "-" : `${duration(secondsPerKm)} /km`;
}

export function signed(value: number): string {
  const rounded = roundHalfEven(value);
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

const METRES_PER_MILE = 1609.344;
const NAMED_DISTANCES_M = new Map([
  [21097.5, "Half marathon"],
  [42195, "Marathon"],
]);

function sixSignificantDigits(value: number): string {
  return String(Number(value.toPrecision(6)));
}

export function distanceName(metres: number): string {
  const named = NAMED_DISTANCES_M.get(metres);
  if (named) {
    return named;
  }
  const miles = roundHalfEven(metres / METRES_PER_MILE, 6);
  if (miles >= 1 && Number.isInteger(miles)) {
    return miles === 1 ? "1 mile" : `${sixSignificantDigits(miles)} miles`;
  }
  return metres < 1000 ? `${sixSignificantDigits(metres)} m` : `${sixSignificantDigits(metres / 1000)} km`;
}

export function activityCount(count: number): string {
  return `${count} ${count === 1 ? "activity" : "activities"}`;
}

export function wholeNumber(value: number | null, unit = ""): string {
  if (value === null) {
    return "-";
  }
  return unit ? `${decimal(value, 0)} ${unit}` : decimal(value, 0);
}

const DAY: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" };
const TIME: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };
const days = new Map<string, Intl.DateTimeFormat>();
const times = new Map<string, Intl.DateTimeFormat>();

function inZone(formatters: Map<string, Intl.DateTimeFormat>, options: Intl.DateTimeFormatOptions, timeZone: string) {
  let formatter = formatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-GB", { ...options, timeZone });
    formatters.set(timeZone, formatter);
  }
  return formatter;
}

export function localDay(iso: string, timeZone: string): string {
  return inZone(days, DAY, timeZone).format(new Date(iso));
}

export function localTime(iso: string, timeZone: string): string {
  return inZone(times, TIME, timeZone).format(new Date(iso));
}

export function calendarDay(isoDate: string): string {
  return inZone(days, DAY, "UTC").format(new Date(`${isoDate}T00:00:00Z`));
}
