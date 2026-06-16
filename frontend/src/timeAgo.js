// Format an ISO timestamp as a compact "time ago" string (e.g. "2 hours ago").
//
// The backend sends UTC timestamps with a trailing "Z" so `new Date()` parses
// them in the right zone. We pick the largest unit that fits and never show a
// raw date — that's a hard requirement of the feed.

const UNITS = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["week", 60 * 60 * 24 * 7],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
];

export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";

  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 45) return "just now";

  for (const [name, size] of UNITS) {
    const value = Math.floor(seconds / size);
    if (value >= 1) {
      return `${value} ${name}${value === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}
