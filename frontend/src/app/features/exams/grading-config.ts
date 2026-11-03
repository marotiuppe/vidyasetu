import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';

import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { ExamsApi, GradeBand, GradeScale, num } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError } from './exam-labels';

type BandGroup = FormGroup<{
  min_percent: FormControl<number>;
  grade: FormControl<string>;
  grade_point: FormControl<number | null>;
  remark: FormControl<string>;
}>;

/**
 * The grading scale of the branch: percent bands with grade, grade point and remark, plus the
 * pass mark. The server checks that the bands are coherent; this screen keeps the editing simple.
 */
@Component({
  selector: 'sms-grading-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './grading-config.html',
  styleUrl: './exams-table.css',
})
export class GradingConfig {
  private readonly api = inject(ExamsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(50)]],
    pass_percent: [33, [Validators.required, Validators.min(0), Validators.max(100)]],
    bands: this.fb.array<BandGroup>([]),
  });

  constructor() {
    this.load();
  }

  protected get bands() {
    return this.form.controls.bands;
  }

  /** A band that starts at 0 must exist, or students below the lowest mark have no grade. */
  protected hasZeroBand(): boolean {
    return this.bands.controls.some((c) => c.controls.min_percent.value === 0);
  }

  protected addBand(): void {
    this.bands.push(this.newBand(0, '', null, ''));
    this.saved.set(false);
  }

  protected removeBand(index: number): void {
    this.bands.removeAt(index);
    this.saved.set(false);
  }

  protected save(): void {
    this.error.set(null);
    this.saved.set(false);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const bands: GradeBand[] = v.bands.map((b) => ({
      min_percent: b.min_percent,
      grade: b.grade.trim(),
      grade_point: b.grade_point,
      remark: b.remark.trim() || null,
    }));
    this.saving.set(true);
    this.api.saveGrading({ name: v.name.trim(), pass_percent: v.pass_percent, bands }).subscribe({
      next: (scale) => {
        this.saving.set(false);
        this.saved.set(true);
        this.apply(scale);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.error.set(message);
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.api.grading().subscribe({
      next: (scale) => {
        this.apply(scale);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private apply(scale: GradeScale): void {
    this.form.controls.name.setValue(scale.name);
    this.form.controls.pass_percent.setValue(scale.pass_percent);
    this.bands.clear();
    for (const b of scale.bands) {
      this.bands.push(this.newBand(b.min_percent, b.grade, num(b.grade_point), b.remark ?? ''));
    }
  }

  private newBand(min: number, grade: string, point: number | null, remark: string): BandGroup {
    return this.fb.group({
      min_percent: this.fb.control(min, [
        Validators.required,
        Validators.min(0),
        Validators.max(100),
      ]),
      grade: this.fb.control(grade, [Validators.required, Validators.maxLength(10)]),
      grade_point: this.fb.control<number | null>(point, [Validators.min(0), Validators.max(10)]),
      remark: this.fb.control(remark, [Validators.maxLength(60)]),
    });
  }
}
