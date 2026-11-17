const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export const formatInr = (n: number) => inr.format(n);

const timeFmt = new Intl.DateTimeFormat("en-IN", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Kolkata",
});
const dayFmt = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "Asia/Kolkata",
});

export const formatTime = (iso: string) => timeFmt.format(new Date(iso));
export const formatDay = (iso: string) => dayFmt.format(new Date(iso));

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h} h ${String(m).padStart(2, "0")} min` : `${m} min`;
}

export const LABEL_TEXT: Record<string, string> = {
  recommended: "Recommended",
  fastest: "Fastest",
  cheapest: "Cheapest",
  greenest: "Greenest",
  most_reliable: "Most reliable",
};

export const MODE_TEXT: Record<string, string> = {
  flight: "Flight",
  train: "Train",
  bus: "Bus",
  cab: "Cab",
  rapido: "Rapido",
  metro: "Metro",
  walk: "Walk",
};
