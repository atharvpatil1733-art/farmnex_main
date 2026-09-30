from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository

# F1 rule: "payer; seller of the order (read); ADMIN".
ADMIN_ROLES = {"ADMIN"}


def _is_admin(user: User) -> bool:
    return user.role is not None and user.role.name in ADMIN_ROLES


class PaymentService:
    """Payments are read-only over HTTP. The payer, the sellers in the order and ADMIN can read.

    Methods return (payment, order public id).
    """

    def __init__(self, repository: PaymentRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def get(self, public_id: UUID, current_user: User) -> tuple[Payment, UUID]:
        row = await self.repository.get_visible_by_public_id(
            public_id, current_user.id, is_admin=_is_admin(current_user)
        )
        if row is None:
            raise NotFoundError("Payment not found.")
        return row

    async def list(
        self, *, current_user: User, offset: int = 0, limit: int = 100
    ) -> tuple[list[tuple[Payment, UUID]], int]:
        self._validate_paging(offset, limit)
        is_admin = _is_admin(current_user)
        return (
            await self.repository.list_visible(
                user_id=current_user.id, is_admin=is_admin, offset=offset, limit=limit
            ),
            await self.repository.count_visible(user_id=current_user.id, is_admin=is_admin),
        )
