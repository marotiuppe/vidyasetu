import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.fees import service
from app.modules.fees.models import PaymentMethod, PaymentStatus
from app.modules.fees.receipt import build_receipt_pdf
from app.modules.fees.schemas import (
    CancelRequest,
    CollectionOut,
    DuesOut,
    GenerateRequest,
    GenerateResult,
    HeadCreate,
    HeadOut,
    HeadUpdate,
    InvoiceCreate,
    InvoiceDetail,
    InvoicePage,
    InvoiceUpdate,
    PaymentCreate,
    PaymentOut,
    PaymentPage,
    ReverseRequest,
    StructureImportRequest,
    StructureImportResult,
    StructureItemOut,
    StructureReplace,
    StudentFees,
)
from app.modules.settings.deps import require_feature
from app.modules.users.models import Role

router = APIRouter(tags=["fees"], dependencies=[Depends(require_feature("fees"))])

_MANAGERS = (Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.ACCOUNTANT)
# Super admin may read (always empty: no school data) but never write.
_managers = Depends(require_roles(*_MANAGERS))
_payers = Depends(require_roles(*_MANAGERS, Role.CLERK))
_readers = Depends(require_roles(*_MANAGERS, Role.CLERK, Role.HEADMASTER, Role.SUPER_ADMIN))
_reporters = Depends(require_roles(*_MANAGERS, Role.HEADMASTER, Role.SUPER_ADMIN))
# Parents and students: only their own children's fees / receipts (scoped in the service).
_family_too = Depends(
    require_roles(*_MANAGERS, Role.CLERK, Role.HEADMASTER, Role.PARENT, Role.STUDENT)
)

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


# ---- heads ----


@router.get("/fees/heads", response_model=list[HeadOut], dependencies=[_readers])
async def list_heads(db: DbSession, actor: CurrentUser) -> list[HeadOut]:
    return [HeadOut.model_validate(h) for h in await service.list_heads(db, actor)]


@router.post(
    "/fees/heads",
    response_model=HeadOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_managers],
)
async def create_head(data: HeadCreate, db: DbSession, actor: CurrentUser) -> HeadOut:
    return HeadOut.model_validate(await service.create_head(db, actor, data))


@router.patch("/fees/heads/{head_id}", response_model=HeadOut, dependencies=[_managers])
async def update_head(head_id: int, data: HeadUpdate, db: DbSession, actor: CurrentUser) -> HeadOut:
    return HeadOut.model_validate(await service.update_head(db, actor, head_id, data))


# ---- structure ----


@router.get("/fees/structure", response_model=list[StructureItemOut], dependencies=[_readers])
async def get_structure(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    class_id: int | None = None,
) -> list[StructureItemOut]:
    return await service.list_structure(db, actor, academic_year_id, class_id)


@router.post(
    "/fees/structure/import", response_model=StructureImportResult, dependencies=[_managers]
)
async def import_structure(
    data: StructureImportRequest, db: DbSession, actor: CurrentUser
) -> StructureImportResult:
    return await service.import_structure(db, actor, data)


@router.put("/fees/structure", response_model=list[StructureItemOut], dependencies=[_managers])
async def replace_structure(
    data: StructureReplace, db: DbSession, actor: CurrentUser
) -> list[StructureItemOut]:
    return await service.replace_structure(db, actor, data)


# ---- invoices ----


@router.post("/fees/invoices/generate", response_model=GenerateResult, dependencies=[_managers])
async def generate_invoices(
    data: GenerateRequest, db: DbSession, actor: CurrentUser
) -> GenerateResult:
    return await service.generate_invoices(db, actor, data)


@router.post(
    "/fees/invoices",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_managers],
)
async def create_invoice(data: InvoiceCreate, db: DbSession, actor: CurrentUser) -> InvoiceDetail:
    return await service.create_invoice(db, actor, data)


@router.get("/fees/invoices", response_model=InvoicePage, dependencies=[_readers])
async def list_invoices(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    student_id: int | None = None,
    status: Annotated[str | None, Query(pattern="^(unpaid|partial|paid|cancelled)$")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    overdue: bool | None = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> InvoicePage:
    f = service.InvoiceFilters(
        academic_year_id=academic_year_id,
        class_id=class_id,
        section_id=section_id,
        student_id=student_id,
        status=status,
        q=q,
        overdue=overdue,
    )
    return await service.list_invoices(db, actor, f, page, page_size)


@router.get("/fees/invoices/{invoice_id}", response_model=InvoiceDetail, dependencies=[_readers])
async def get_invoice(invoice_id: int, db: DbSession, actor: CurrentUser) -> InvoiceDetail:
    return await service.get_invoice(db, actor, invoice_id)


@router.patch("/fees/invoices/{invoice_id}", response_model=InvoiceDetail, dependencies=[_managers])
async def update_invoice(
    invoice_id: int, data: InvoiceUpdate, db: DbSession, actor: CurrentUser
) -> InvoiceDetail:
    return await service.update_invoice(db, actor, invoice_id, data)


@router.post(
    "/fees/invoices/{invoice_id}/cancel", response_model=InvoiceDetail, dependencies=[_managers]
)
async def cancel_invoice(
    invoice_id: int, data: CancelRequest, db: DbSession, actor: CurrentUser
) -> InvoiceDetail:
    return await service.cancel_invoice(db, actor, invoice_id, data)


@router.post(
    "/fees/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_payers],
)
async def record_payment(
    invoice_id: int, data: PaymentCreate, db: DbSession, actor: CurrentUser
) -> PaymentOut:
    return await service.record_payment(db, actor, invoice_id, data)


# ---- payments ----


@router.get("/fees/payments", response_model=PaymentPage, dependencies=[_readers])
async def list_payments(
    db: DbSession,
    actor: CurrentUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    method: PaymentMethod | None = None,
    invoice_id: int | None = None,
    student_id: int | None = None,
    status: PaymentStatus | None = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> PaymentPage:
    return await service.list_payments(
        db,
        actor,
        date_from=date_from,
        date_to=date_to,
        method=method,
        invoice_id=invoice_id,
        student_id=student_id,
        pay_status=status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/fees/payments/{payment_id}/reverse", response_model=PaymentOut, dependencies=[_managers]
)
async def reverse_payment(
    payment_id: int, data: ReverseRequest, db: DbSession, actor: CurrentUser
) -> PaymentOut:
    return await service.reverse_payment(db, actor, payment_id, data)


@router.get("/fees/payments/{payment_id}/receipt.pdf", dependencies=[_family_too])
async def receipt_pdf(payment_id: int, db: DbSession, actor: CurrentUser) -> Response:
    data = await service.receipt_data(db, actor, payment_id)
    safe_no = re.sub(r"[^A-Za-z0-9_-]", "", data["receipt_no"])
    return Response(
        content=build_receipt_pdf(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{safe_no}.pdf"'},
    )


# ---- dues and collection ----


@router.get("/fees/dues", response_model=DuesOut, dependencies=[_readers])
async def dues(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    branch_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    min_balance_paise: Annotated[int, Query(ge=0)] = 0,
) -> DuesOut:
    return await service.dues(
        db, actor, academic_year_id, branch_id, class_id, section_id, min_balance_paise
    )


@router.get("/fees/dues/export", dependencies=[_readers])
async def dues_export(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    branch_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    min_balance_paise: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    content = await service.dues_csv(
        db, actor, academic_year_id, branch_id, class_id, section_id, min_balance_paise
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fee-dues.csv"'},
    )


@router.get("/fees/collection", response_model=CollectionOut, dependencies=[_reporters])
async def collection(
    db: DbSession,
    actor: CurrentUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    branch_id: int | None = None,
) -> CollectionOut:
    return await service.collection(db, actor, date_from, date_to, branch_id)


# ---- student view ----


@router.get("/students/{student_id}/fees", response_model=StudentFees, dependencies=[_family_too])
async def student_fees(student_id: int, db: DbSession, actor: CurrentUser) -> StudentFees:
    return await service.student_fees(db, actor, student_id)
