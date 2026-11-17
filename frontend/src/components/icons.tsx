import type { Mode } from "../api/types";

/** Small stroke icons (24px grid, currentColor). Decorative unless given a title. */
type IconName =
  | Mode
  | "swap"
  | "arrow"
  | "mic"
  | "camera"
  | "send"
  | "check"
  | "alert"
  | "clock"
  | "leaf"
  | "shield"
  | "plan"
  | "ticket"
  | "chat"
  | "pulse"
  | "close"
  | "chevron";

const PATHS: Record<IconName, string> = {
  flight: "M2 16l8-3V7.5a2 2 0 0 1 4 0V13l8 3v2l-8-2v3.5l2.5 1.5v1.5L12 21l-4.5 1.5V21L10 19.5V16l-8 2z",
  train: "M7 3h10a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zM4 11h16M8 15h.01M16 15h.01M7 21l2-3M17 21l-2-3",
  bus: "M6 3h12a2 2 0 0 1 2 2v12H4V5a2 2 0 0 1 2-2zM4 10h16M7 21v-4M17 21v-4M7.5 14h.01M16.5 14h.01",
  cab: "M5 17h14v-5l-2-5H7l-2 5zM3 12h18M7.5 15h.01M16.5 15h.01M7 20v-3M17 20v-3M10 4h4v3",
  rapido: "M5 18a3 3 0 1 0 0-.01M19 18a3 3 0 1 0 0-.01M5 18l4-7h5l3 7M9 11l-1-3H5M14 11l2-4h3",
  metro: "M6 4h12a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6a2 2 0 0 1 2-2zM4 10h16M9 21l1.5-3M15 21l-1.5-3M12 4v6",
  walk: "M13 4a1.5 1.5 0 1 0 0 .01M10 21l2-6 2 2v4M9 11l3-3 3 3 2 1M12 8l-1 5",
  swap: "M7 4v16M7 4L4 7M7 4l3 3M17 20V4M17 20l-3-3M17 20l3-3",
  arrow: "M4 12h15M14 6l6 6-6 6",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  camera: "M4 8h3l2-3h6l2 3h3v11H4zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  send: "M4 12l16-8-6 16-3-7z",
  check: "M5 12l5 5L20 7",
  alert: "M12 3l10 18H2zM12 10v5M12 18h.01",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  leaf: "M5 19C5 10 11 5 20 4c0 9-5 15-14 15zM5 19l7-7",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  plan: "M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12zM12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  ticket: "M3 7h18v3a2 2 0 0 0 0 4v3H3v-3a2 2 0 0 0 0-4zM14 7v10",
  chat: "M4 5h16v11H9l-5 4z",
  pulse: "M3 12h4l2-6 4 12 2-6h6",
  close: "M6 6l12 12M18 6L6 18",
  chevron: "M9 6l6 6-6 6",
};

export function Icon({ name, size = 18, title }: { name: IconName; size?: number; title?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      className="icon"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
