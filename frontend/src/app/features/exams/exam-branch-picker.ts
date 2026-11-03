import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';

import { ExamBranchService } from '../../core/api/exam-branch.service';
import { I18n } from '../../core/i18n/i18n';
import { FeeLookups } from '../fees/fee-lookups';
import { fieldValue } from './exam-labels';

/**
 * Branch choice for school-wide accounts on the exam screens. Renders nothing for branch-level
 * users. Place it as the first field of a `.toolbar`.
 */
@Component({
  selector: 'sms-exam-branch-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: [':host { display: contents; }'],
  template: `
    @if (scope.needsPick()) {
      <label class="field">
        {{ i18n.t('exams.branch.label') }}
        <select class="input" (change)="pick($event)">
          <option value="0">{{ i18n.t('exams.branch.choose') }}</option>
          @for (b of lookups.branches(); track b.id) {
            <option [value]="b.id" [selected]="b.id === scope.picked()">{{ b.name }}</option>
          }
        </select>
      </label>
    }
  `,
})
export class ExamBranchPicker {
  protected readonly scope = inject(ExamBranchService);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  constructor() {
    if (!this.scope.needsPick()) return;
    this.lookups.loadBranches();
    effect(() => {
      const list = this.lookups.branches();
      const picked = this.scope.picked();
      if (!list.length) return;
      if (picked !== null && !list.some((b) => b.id === picked)) this.scope.pick(null);
      else if (picked === null && list.length === 1) this.scope.pick(list[0].id);
    });
  }

  protected pick(event: Event): void {
    const id = Number(fieldValue(event));
    this.scope.pick(id || null);
  }
}
