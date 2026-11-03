import { FormControl, FormGroup } from '@angular/forms';

import {
  PromotionAction,
  PromotionBatch,
  PromotionCandidate,
  PromotionClassOption,
} from '../../core/api/promotion.api';

/** One student's row in the promotion table. */
export interface PromotionRowForm {
  action: FormControl<PromotionAction>;
  toClassId: FormControl<number>;
  toSectionId: FormControl<number>;
}

/** A candidate plus whether the user may act on it. Locked rows are shown, disabled and not sent. */
export interface PromotionRowView {
  candidate: PromotionCandidate;
  locked: boolean;
  lockKey: string | null;
}

/** Row controls, started from the server's suggestion. */
export function newRowGroup(candidate: PromotionCandidate): FormGroup<PromotionRowForm> {
  return new FormGroup<PromotionRowForm>({
    action: new FormControl<PromotionAction>(candidate.suggested_action, { nonNullable: true }),
    toClassId: new FormControl<number>(candidate.suggested_to_class_id ?? 0, {
      nonNullable: true,
    }),
    toSectionId: new FormControl<number>(0, { nonNullable: true }),
  });
}

/** Lock a row when the server would skip it or the user is not allowed to move it. */
export function rowViewOf(candidate: PromotionCandidate, isOwner: boolean): PromotionRowView {
  if (candidate.already_enrolled) {
    return { candidate, locked: true, lockKey: 'promotion.lock.alreadyEnrolled' };
  }
  if (candidate.needs_owner && !isOwner) {
    return { candidate, locked: true, lockKey: 'promotion.lock.ownerOnly' };
  }
  return { candidate, locked: false, lockKey: null };
}

/** Translation key for an action label. */
export function actionKey(action: PromotionAction): string {
  return `promotion.action.${action}`;
}

/** Label for a class in a select: "Class 6 · Primary". */
export function classOptionLabel(option: PromotionClassOption, withBranch: boolean): string {
  return withBranch ? `${option.name} · ${option.branch_name}` : option.name;
}

/** "Class 5 · A" or just the class, for a candidate's current place. */
export function currentPlace(candidate: PromotionCandidate): string {
  if (!candidate.from_class) return '';
  return candidate.from_section
    ? `${candidate.from_class} · ${candidate.from_section}`
    : candidate.from_class;
}

/** A batch counts as undone once the server has stamped it. */
export function isUndone(batch: PromotionBatch): boolean {
  return Boolean(batch.undone_at);
}

/** Undo is offered only once, and only until the undo window closes. */
export function canUndo(batch: PromotionBatch, nowMs: number = Date.now()): boolean {
  return !isUndone(batch) && Date.parse(batch.undo_until) > nowMs;
}

/** ISO date (YYYY-MM-DD) `days` after another, by calendar arithmetic in UTC. */
export function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
