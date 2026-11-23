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

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

export function localDay(iso: string): string {
  return DAY.format(new Date(iso));
}

export function localTime(iso: string): string {
  return TIME.format(new Date(iso));
}
