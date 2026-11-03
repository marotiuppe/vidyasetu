import { AdmissionStatus, DOCUMENT_MAX_BYTES } from '../../core/api/admissions.api';

/**
 * Status moves the staff screens offer. Mirrors the server rules (others are refused with 409).
 * `enrolled` is reached only through Convert to student.
 */
export const ALLOWED_TRANSITIONS: Record<AdmissionStatus, AdmissionStatus[]> = {
  enquiry: ['applied', 'rejected'],
  applied: ['admitted', 'rejected'],
  admitted: ['rejected'],
  enrolled: [],
  rejected: ['enquiry'],
};

/** Translation key for an application status (English text: `admissions.status.<status>`). */
export function statusKey(status: AdmissionStatus): string {
  return `admissions.status.${status}`;
}

/** Translation key for the button that moves an application to a status. */
export function actionKey(status: AdmissionStatus): string {
  return `admissions.action.${status}`;
}

/** Translation key for where an application came from. */
export function sourceKey(source: string): string {
  return `admissions.source.${source}`;
}

/** Badge colour class for a status. */
export function statusBadge(status: AdmissionStatus): string {
  switch (status) {
    case 'enrolled':
      return 'badge-success';
    case 'applied':
      return 'badge-warn';
    case 'rejected':
      return 'badge-danger';
    case 'admitted':
      return '';
    case 'enquiry':
      return 'badge-muted';
  }
}

/** File extension used when a document is saved to disk. */
export function extensionFor(contentType: string): string {
  switch (contentType) {
    case 'application/pdf':
      return '.pdf';
    case 'image/png':
      return '.png';
    case 'image/jpeg':
      return '.jpg';
    default:
      return '';
  }
}

/** Size in KB or MB for display (no locale needed). */
export function sizeText(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Whether a picked file is within the type and size limits (quick check; the server checks again). */
export function fileProblem(file: File, allowedTypes: readonly string[]): 'type' | 'size' | null {
  if (!allowedTypes.includes(file.type)) return 'type';
  if (file.size > DOCUMENT_MAX_BYTES) return 'size';
  return null;
}
