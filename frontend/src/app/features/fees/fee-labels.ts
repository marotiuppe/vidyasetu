import { InvoiceStatus, PaymentMethod } from '../../core/api/fees.api';

const METHODS: Record<PaymentMethod, string> = {
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
  bank: 'Bank transfer',
  cheque: 'Cheque',
  online: 'Online',
};

const STATUSES: Record<InvoiceStatus, string> = {
  unpaid: 'Unpaid',
  partial: 'Partly paid',
  paid: 'Paid',
  cancelled: 'Cancelled',
};

/** Translation lookup, as `I18n.t` (pass `i18n.t` so the label follows the language). */
export type Translate = (key: string) => string;

const METHOD_KEYS: Record<PaymentMethod, string> = {
  cash: 'fees.setup.method.cash',
  upi: 'fees.setup.method.upi',
  card: 'fees.setup.method.card',
  bank: 'fees.setup.method.bank',
  cheque: 'fees.setup.method.cheque',
  online: 'fees.setup.method.online',
};

const STATUS_KEYS: Record<InvoiceStatus, string> = {
  unpaid: 'fees.setup.status.unpaid',
  partial: 'fees.setup.status.partial',
  paid: 'fees.setup.status.paid',
  cancelled: 'fees.setup.status.cancelled',
};

export function methodLabel(method: PaymentMethod): string {
  return METHODS[method] ?? method;
}

export function invoiceStatusLabel(status: InvoiceStatus): string {
  return STATUSES[status] ?? status;
}

/** Translated payment method label. */
export function methodText(method: PaymentMethod, t: Translate): string {
  const key = METHOD_KEYS[method];
  return key ? t(key) : method;
}

/** Translated invoice status label. */
export function invoiceStatusText(status: InvoiceStatus, t: Translate): string {
  const key = STATUS_KEYS[status];
  return key ? t(key) : status;
}

/** Badge class for an invoice status; the text label always carries the meaning. */
export function invoiceStatusClass(status: InvoiceStatus): string {
  switch (status) {
    case 'paid':
      return 'badge-success';
    case 'partial':
      return 'badge-warn';
    case 'cancelled':
      return 'badge-muted';
    default:
      return 'badge-danger';
  }
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/** Today as YYYY-MM-DD in the browser's local time. */
export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function monthStartIso(): string {
  return `${todayIso().slice(0, 8)}01`;
}

/** "Class 5 - A" style label. */
export function classSection(className: string | null, sectionName: string | null): string {
  if (!className) return 'Not enrolled';
  return sectionName ? `${className} - ${sectionName}` : className;
}

/** Translated "Class 5 - A" style label; the class and section names are server data. */
export function classSectionText(
  className: string | null,
  sectionName: string | null,
  t: Translate,
): string {
  if (!className) return t('fees.setup.picker.notEnrolled');
  return sectionName ? `${className} - ${sectionName}` : className;
}

/** Current value of the input or select that raised the event. */
export function value(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value;
}
