import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { FormArray, FormGroup, ReactiveFormsModule } from '@angular/forms';

import {
  PROMOTION_ACTIONS,
  PromotionAction,
  PromotionClassOption,
  PromotionSection,
} from '../../core/api/promotion.api';
import { I18n } from '../../core/i18n/i18n';
import { formatPaise } from '../../core/ui/money';
import {
  PromotionRowForm,
  PromotionRowView,
  actionKey,
  classOptionLabel,
  currentPlace,
} from './promotion-model';

/** One row per student: the action, and the class and section to move to. */
@Component({
  selector: 'sms-promotion-table',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './promotion-table.html',
  styleUrl: './promotion-table.css',
})
export class PromotionTable {
  protected readonly i18n = inject(I18n);

  readonly views = input.required<PromotionRowView[]>();
  readonly rows = input.required<FormArray<FormGroup<PromotionRowForm>>>();
  readonly classOptions = input.required<PromotionClassOption[]>();
  readonly sections = input.required<PromotionSection[]>();
  /** The class the students are promoted from; detained students stay in it. */
  readonly fromClassId = input.required<number>();
  /** Whether to show the branch next to each class (school owners see every branch). */
  readonly showBranch = input(false);

  protected readonly actions: PromotionAction[] = PROMOTION_ACTIONS;
  protected readonly money = formatPaise;
  protected readonly actionKey = actionKey;
  protected readonly place = currentPlace;

  protected classLabel(option: PromotionClassOption): string {
    return classOptionLabel(option, this.showBranch());
  }

  /** A new action or class makes the chosen section stale, so it goes back to "any section". */
  protected resetSection(index: number): void {
    this.rows().at(index).controls.toSectionId.setValue(0);
  }

  /** Sections for the class a row moves into (or stays in, when detained). */
  protected sectionsFor(index: number): PromotionSection[] {
    const group = this.rows().at(index);
    const classId =
      group.controls.action.value === 'detained'
        ? this.fromClassId()
        : group.controls.toClassId.value;
    return classId ? this.sections().filter((s) => s.class_id === classId) : [];
  }

  /** A promotion with no class is flagged on its row. */
  protected missingTarget(index: number): boolean {
    const group = this.rows().at(index);
    return group.controls.action.value === 'promoted' && group.controls.toClassId.value === 0;
  }
}
