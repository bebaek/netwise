export function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });
}
