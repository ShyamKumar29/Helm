export function inr(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';
  if (abs >= 10000000) return `${sign}₹${(abs / 10000000).toFixed(2)} Cr`;
  if (abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(2)} L`;
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export function inrExact(amount: number): string {
  return `₹${Math.abs(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function bps(value: number): string {
  return `${value.toFixed(1)} bps/day`;
}

export function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function simDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
  });
}

// "YYYY-MM-DD" + N days -> "YYYY-MM-DD". No timezones anywhere (FINAL.md §8 conventions) —
// parse and format as plain UTC calendar dates, never a local-time Date shift.
export function addDaysIso(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
