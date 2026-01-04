"""create IPC permissions and extend patent metadata (IP Portfolio)

Revision ID: 20260104_003
Revises: 20260103_001
Create Date: 2026-01-04

NOTE:
- This revision is required because the target DB already references 20260104_003.
- It formalizes IPC-based permissions and adds IP Portfolio fields to tb_patent_metadata.
- User table reference: tb_user (see app/models/auth/user_models.py). This revision does not
  enforce a FK to tb_user.emp_no to avoid blocking installs with pre-existing data; add it
  later if needed.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260104_003"
down_revision = "20260103_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1) tb_ipc_permissions
    # ---------------------------------------------------------------------
    op.create_table(
        "tb_ipc_permissions",
        sa.Column("permission_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_emp_no", sa.String(20), nullable=False),
        sa.Column("ipc_code", sa.String(20), nullable=False),
        sa.Column("role_id", sa.String(20), nullable=False),
        sa.Column("access_scope", sa.String(20), nullable=False, server_default="FULL"),
        sa.Column("include_children", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("valid_until", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_date", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(20), nullable=True),
        sa.Column("last_modified_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_modified_by", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(["ipc_code"], ["tb_ipc_code.code"], name="fk_ipc_perm_code"),
        sa.UniqueConstraint("user_emp_no", "ipc_code", name="uq_ipc_perm_user_code"),
        comment="IPC 기반 IP 포트폴리오 권한",
    )

    op.create_index("idx_ipc_perm_user", "tb_ipc_permissions", ["user_emp_no"])
    op.create_index("idx_ipc_perm_code", "tb_ipc_permissions", ["ipc_code"])
    op.create_index("idx_ipc_perm_role", "tb_ipc_permissions", ["role_id"])
    op.create_index("idx_ipc_perm_active", "tb_ipc_permissions", ["is_active", "valid_until"])
    op.create_index("idx_ipc_perm_user_active", "tb_ipc_permissions", ["user_emp_no", "is_active", "ipc_code"])

    # ---------------------------------------------------------------------
    # 2) tb_patent_metadata - IP Portfolio fields
    # ---------------------------------------------------------------------
    with op.batch_alter_table("tb_patent_metadata") as batch_op:
        batch_op.add_column(sa.Column("primary_ipc_section", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True))
        batch_op.add_column(sa.Column("patent_status", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("legacy_container_id", sa.String(50), nullable=True))

    op.create_index("idx_patent_status", "tb_patent_metadata", ["patent_status"])
    op.create_index("idx_patent_ipc_status", "tb_patent_metadata", ["primary_ipc_section", "patent_status"])
    op.create_index("idx_patent_legacy_container", "tb_patent_metadata", ["legacy_container_id"])


def downgrade() -> None:
    op.drop_index("idx_patent_legacy_container", table_name="tb_patent_metadata")
    op.drop_index("idx_patent_ipc_status", table_name="tb_patent_metadata")
    op.drop_index("idx_patent_status", table_name="tb_patent_metadata")

    with op.batch_alter_table("tb_patent_metadata") as batch_op:
        batch_op.drop_column("legacy_container_id")
        batch_op.drop_column("patent_status")
        batch_op.drop_column("keywords")
        batch_op.drop_column("primary_ipc_section")

    op.drop_index("idx_ipc_perm_user_active", table_name="tb_ipc_permissions")
    op.drop_index("idx_ipc_perm_active", table_name="tb_ipc_permissions")
    op.drop_index("idx_ipc_perm_role", table_name="tb_ipc_permissions")
    op.drop_index("idx_ipc_perm_code", table_name="tb_ipc_permissions")
    op.drop_index("idx_ipc_perm_user", table_name="tb_ipc_permissions")
    op.drop_table("tb_ipc_permissions")
