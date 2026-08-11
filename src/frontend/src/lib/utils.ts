export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffMin = Math.floor((Date.now() - then) / 60_000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const hours = Math.floor(diffMin / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || value < 0) return 'Unknown size';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = value / 1024;
  let unit = units[0];
  for (let i = 1; i < units.length && size >= 1024; i += 1) {
    size /= 1024;
    unit = units[i];
  }
  return `${size >= 10 ? size.toFixed(1) : size.toFixed(2)} ${unit}`;
}

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Trigger a browser download of an authenticated same-origin URL. */
export function downloadFile(url: string): void {
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean).slice(0, 2);
  const result = parts.map((p) => p.charAt(0).toUpperCase()).join('');
  return result || '?';
}
