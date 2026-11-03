"""Pure result arithmetic: no database, no HTTP. Every percentage is a Decimal rounded to two
places (half up) before it is compared with a grade band or a pass mark, so the number a parent
reads is the number that was graded.

Rules (all in one place so the report, the progress view and the class summary agree):
- An exam's marks give percent = marks * 100 / max_marks. An absent student scores 0.
- Exam weights: when the exams of a term add up to 100, they are used as weights; otherwise every
  exam weighs 1 (equal). A subject's term percent is the weighted mean over the exams that have
  a mark recorded. `complete` says whether every visible exam of that subject has a mark.
- Term weights work the same way over the terms of the year.
- A term total is the mean of the scholastic subject percents (co-scholastic subjects are shown
  but do not count). The annual figures are the term-weighted means of the term figures.
- A scholastic subject with a percent below the scale's pass percent fails. A term or annual
  result fails when any scholastic subject fails.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_DP = Decimal("0.01")
_HUNDRED = Decimal(100)
_ONE = Decimal(1)


def q2(value: Decimal) -> Decimal:
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ExamRef:
    id: int
    term_id: int
    name: str
    max_marks: int
    weight: int
    published: bool


@dataclass(frozen=True)
class TermRef:
    id: int
    name: str
    sequence: int
    weight: int


@dataclass(frozen=True)
class SubjectRef:
    id: int
    name: str
    code: str | None
    scholastic: bool


@dataclass(frozen=True)
class MarkRef:
    marks: Decimal | None
    absent: bool


@dataclass(frozen=True)
class BandRef:
    min_percent: int
    grade: str
    grade_point: Decimal | None
    remark: str | None


@dataclass(frozen=True)
class ScaleRef:
    pass_percent: int
    bands: tuple[BandRef, ...]


def band_for(scale: ScaleRef, percent: Decimal | None) -> BandRef | None:
    """The band with the highest minimum that the percent reaches (None when no percent)."""
    if percent is None:
        return None
    for band in sorted(scale.bands, key=lambda b: b.min_percent, reverse=True):
        if percent >= band.min_percent:
            return band
    return None


def _uses_weights(weights: Iterable[int]) -> bool:
    return sum(weights) == 100


def exam_percent(exam: ExamRef, mark: MarkRef | None) -> Decimal | None:
    if mark is None:
        return None
    if mark.absent:
        return Decimal(0)
    if mark.marks is None:
        return None
    return q2(mark.marks * _HUNDRED / Decimal(exam.max_marks))


@dataclass(frozen=True)
class ExamEntry:
    exam: ExamRef
    weight: Decimal
    mark: MarkRef | None
    percent: Decimal | None


@dataclass(frozen=True)
class SubjectTerm:
    subject: SubjectRef
    entries: tuple[ExamEntry, ...]
    percent: Decimal | None
    complete: bool

    def result(self, scale: ScaleRef) -> str | None:
        if not self.subject.scholastic or self.percent is None:
            return None
        return "fail" if self.percent < scale.pass_percent else "pass"


def subject_term(
    subject: SubjectRef,
    term_exams: list[ExamRef],
    visible: list[ExamRef],
    marks: Mapping[tuple[int, int], MarkRef],
) -> SubjectTerm:
    """One subject in one term. `term_exams` decides the weighting, `visible` the exams counted."""
    exam_weights_on = _uses_weights(e.weight for e in term_exams)
    entries: list[ExamEntry] = []
    for exam in visible:
        weight = Decimal(exam.weight) if exam_weights_on else _ONE
        mark = marks.get((exam.id, subject.id))
        entries.append(ExamEntry(exam, weight, mark, exam_percent(exam, mark)))
    counted = [e for e in entries if e.percent is not None]
    percent: Decimal | None = None
    if counted:
        total_weight = sum((e.weight for e in counted), Decimal(0))
        numerator = sum(
            (e.weight * e.percent for e in counted if e.percent is not None), Decimal(0)
        )
        percent = q2(numerator / total_weight)
    complete = bool(entries) and len(counted) == len(entries)
    return SubjectTerm(subject, tuple(entries), percent, complete)


@dataclass(frozen=True)
class TermCalc:
    term: TermRef
    exam_weighting: str  # "weighted" or "equal"
    subjects: tuple[SubjectTerm, ...]
    total: Decimal | None
    complete: bool
    result: str | None

    def subject_percent(self, subject_id: int) -> Decimal | None:
        for s in self.subjects:
            if s.subject.id == subject_id:
                return s.percent
        return None


def term_calc(
    term: TermRef,
    term_exams: list[ExamRef],
    visible: list[ExamRef],
    subjects: list[SubjectRef],
    marks: Mapping[tuple[int, int], MarkRef],
    scale: ScaleRef,
) -> TermCalc:
    weighted = _uses_weights(e.weight for e in term_exams)
    rows = tuple(subject_term(s, term_exams, visible, marks) for s in subjects)
    scholastic = [r for r in rows if r.subject.scholastic and r.percent is not None]
    total: Decimal | None = None
    if scholastic:
        total = q2(
            sum((r.percent for r in scholastic if r.percent is not None), Decimal(0))
            / Decimal(len(scholastic))
        )
    complete = all(r.complete for r in rows) and bool(rows)
    failed = any(r.result(scale) == "fail" for r in rows)
    result = "fail" if failed else ("pass" if total is not None else None)
    return TermCalc(
        term=term,
        exam_weighting="weighted" if weighted else "equal",
        subjects=rows,
        total=total,
        complete=complete,
        result=result,
    )


@dataclass(frozen=True)
class AnnualSubject:
    subject: SubjectRef
    percent: Decimal | None

    def result(self, scale: ScaleRef) -> str | None:
        if not self.subject.scholastic or self.percent is None:
            return None
        return "fail" if self.percent < scale.pass_percent else "pass"


@dataclass(frozen=True)
class AnnualCalc:
    term_weighting: str
    subjects: tuple[AnnualSubject, ...]
    total: Decimal | None
    result: str | None


def annual_calc(
    terms: list[TermCalc],
    all_term_weights: list[int],
    subjects: list[SubjectRef],
    scale: ScaleRef,
) -> AnnualCalc:
    """Term-weighted annual figures over the included terms.

    `all_term_weights` (every term of the year) decides between weighted and equal weights.
    """
    weighted = _uses_weights(all_term_weights)

    def weight_of(term: TermCalc) -> Decimal:
        return Decimal(term.term.weight) if weighted else _ONE

    def blend(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
        if not pairs:
            return None
        total_weight = sum((w for w, _ in pairs), Decimal(0))
        return q2(sum((w * v for w, v in pairs), Decimal(0)) / total_weight)

    annual_subjects: list[AnnualSubject] = []
    for subject in subjects:
        pairs: list[tuple[Decimal, Decimal]] = []
        for term in terms:
            value = term.subject_percent(subject.id)
            if value is not None:
                pairs.append((weight_of(term), value))
        annual_subjects.append(AnnualSubject(subject, blend(pairs)))
    total = blend([(weight_of(t), t.total) for t in terms if t.total is not None])
    subject_rows = tuple(annual_subjects)
    failed = any(s.result(scale) == "fail" for s in subject_rows)
    result = "fail" if failed else ("pass" if total is not None else None)
    return AnnualCalc(
        term_weighting="weighted" if weighted else "equal",
        subjects=subject_rows,
        total=total,
        result=result,
    )


def competition_rank(totals: Mapping[int, Decimal], student_id: int) -> int | None:
    """1-based rank by total, highest first; equal totals share a rank (1, 1, 3)."""
    mine = totals.get(student_id)
    if mine is None:
        return None
    return 1 + sum(1 for value in totals.values() if value > mine)
