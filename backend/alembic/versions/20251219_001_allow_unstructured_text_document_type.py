"""allow unstructured_text document_type

Revision ID: 20251219_001
Revises: 20251118_001
Create Date: 2025-12-19

Purpose:
- Extend tb_file_bss_info.document_type check constraint (chk_document_type)
  to allow the newly added document type: 'unstructured_text'.

Background:
- API/UI already expose 'unstructured_text', but DB constraint rejected inserts.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20251219_001"
down_revision: Union[str, None] = "20251118_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ALLOWED_TYPES_NEW = (
    "general",
    "academic_paper",
    "patent",
    "technical_report",
    "business_document",
    "presentation",
    "unstructured_text",
)

_ALLOWED_TYPES_OLD = (
    "general",
    "academic_paper",
    "patent",
    "technical_report",
    "business_document",
    "presentation",
)


def _in_list_sql(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"document_type IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint("chk_document_type", "tb_file_bss_info", type_="check")
    op.create_check_constraint(
        "chk_document_type",
        "tb_file_bss_info",
        _in_list_sql(_ALLOWED_TYPES_NEW),
    )


def downgrade() -> None:
    op.drop_constraint("chk_document_type", "tb_file_bss_info", type_="check")
    op.create_check_constraint(
        "chk_document_type",
        "tb_file_bss_info",
        _in_list_sql(_ALLOWED_TYPES_OLD),
    )
