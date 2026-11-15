const MS_PER_DAY = 86_400_000;

export function fmt(value: number | null | undefined, lang: string, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(lang, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Fecha local en formato ISO (YYYY-MM-DD), sin desfase por zona horaria. */
export function toISODate(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseISODate(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

export function addDays(iso: string, days: number): string {
  const date = parseISODate(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function addMonths(iso: string, months: number): string {
  const date = parseISODate(iso);
  date.setUTCMonth(date.getUTCMonth() + months);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(startISO: string, endISO: string): number {
  return Math.round(
    (parseISODate(endISO).getTime() - parseISODate(startISO).getTime()) / MS_PER_DAY,
  );
}

/** Numero con signo explícito para Z/T-scores. */
export function signed(value: number | null | undefined, lang: string, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const text = fmt(value, lang, digits);
  return value > 0 ? `+${text}` : text;
}

/** Fecha y hora local a partir de un ISO sin zona (lo que envía el backend). */
export function formatDateTime(iso: string, lang: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(lang, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function todayISO(): string {
  return toISODate(new Date());
}
