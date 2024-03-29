"""Remove StringParts, add it into the Attribute table as JSON.

Revision ID: 6fe427cd07c7
Revises: 6f28391b3a2d
Create Date: 2023-05-22 22:42:51.154264

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6fe427cd07c7"
down_revision = "6f28391b3a2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("stringparts", schema=None) as batch_op:
        batch_op.drop_index("ix_stringparts_id")

    op.drop_table("stringparts")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "stringparts",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("text", sa.VARCHAR(), nullable=True),
        sa.Column("attribute_id", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attribute_id"], ["attributes.id"], name="fk_stringparts_attribute_id_attributes", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stringparts"),
    )
    with op.batch_alter_table("stringparts", schema=None) as batch_op:
        batch_op.create_index("ix_stringparts_id", ["id"], unique=False)

    # ### end Alembic commands ###
