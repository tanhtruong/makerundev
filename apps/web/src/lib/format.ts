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

function fixed(value: number, digits: number): string {
  return roundHalfEven(value, digits).toFixed(digits);
}

export function distance(metres: number): string {
  return `${fixed(metres / 1000, 2)} km`;
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

export function wholeNumber(value: number | null, unit = ""): string {
  if (value === null) {
    return "-";
  }
  return unit ? `${fixed(value, 0)} ${unit}` : fixed(value, 0);
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
