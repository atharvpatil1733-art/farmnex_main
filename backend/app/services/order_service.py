from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.address import Address
from app.models.order import Order
from app.models.product_listing import ProductListing
from app.models.user import User
from app.repositories.order_repository import OrderRepository

# Order steps (F12 prototype): PLACED -> CONFIRMED (the farmer) -> DELIVERED (route optimizer, S26),
# or CANCELLED by the buyer while PLACED.
# Orders the buyer may still cancel (F1 rule: "buyer may cancel while PLACED").
CANCELLABLE_STATUSES = {"PLACED"}
# Once any item has left the farm, the order can't be cancelled any more.
SHIPPED_ITEM_STATUSES = {"SHIPPED", "DELIVERED"}
# Items the farmer's confirm moves to CONFIRMED ("ACTIVE" is the table default, same as PLACED).
OPEN_ITEM_STATUSES = {"ACTIVE", "PLACED"}
MONEY = Decimal("0.01")


@dataclass(frozen=True)
class OrderLine:
    """One thing to buy. `unit_price` is only for server callers (S19: the winning bid's price);
    otherwise the listing's price is used."""

    listing_public_id: UUID
    quantity: Decimal
    unit_price: Decimal | None = None


def _address_snapshot(address: Address) -> dict[str, Any]:
    """The delivery address as it was at checkout (with coordinates for the drop point, S26)."""
    fields = ("address_line_1", "address_line_2", "landmark", "village", "city", "district",
              "state", "postal_code", "country")
    snapshot: dict[str, Any] = {name: getattr(address, name) for name in fields}
    snapshot["address_id"] = str(address.public_id)
    snapshot["latitude"] = float(address.latitude) if address.latitude is not None else None
    snapshot["longitude"] = float(address.longitude) if address.longitude is not None else None
    return snapshot


class OrderService:
    """Orders: the buyer and the sellers of its items can read; only the buyer can cancel; the
    farmer (the order's seller) confirms. Orders are created only by `create_orders`, with
    server-computed prices and totals. Never deleted.
    """

    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def get(self, public_id: UUID, current_user: User) -> Order:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("Order not found.")
        return entity

    async def list(
        self, offset: int = 0, limit: int = 100, *, current_user: User | None = None
    ) -> tuple[list[Order], int]:
        self._validate_paging(offset, limit)
        if current_user is None:
            # Internal callers only (me_service filters the result by buyer itself). The HTTP
            # controller always passes current_user.
            return await self.repository.list(offset=offset, limit=limit), await self.repository.count()
        return (
            await self.repository.list_visible(user_id=current_user.id, offset=offset, limit=limit),
            await self.repository.count_visible(user_id=current_user.id),
        )

    # --- Create (F12 / S18) -----------------------------------------------------------------

    async def checkout(self, data: dict[str, Any], current_user: User) -> tuple[str, list[Order]]:
        """`POST /orders`: the buyer's cart. Only listing ids, quantities and the address are used."""
        lines = [OrderLine(line["listing_id"], line["quantity"]) for line in data["items"]]
        return await self.create_orders(current_user, lines, address_public_id=data.get("address_id"))

    async def create_orders(
        self,
        buyer: User,
        lines: list[OrderLine],
        *,
        address_public_id: UUID | None = None,
        from_accepted_bid: bool = False,
    ) -> tuple[str, list[Order]]:
        """Create one PLACED order per farmer and lower each listing's stock, all in the caller's
        transaction (all or nothing). Returns (checkout number, orders).

        `from_accepted_bid=True` (S19, the farmer accepted a bid): skips the checks that only apply
        to direct buying - open pre-bid event, sale dates and minimum order quantity.
        """
        if not lines:
            raise ValidationError("Nothing to order.")
        if len({line.listing_public_id for line in lines}) != len(lines):
            raise ValidationError("Each listing may appear only once.")

        address = await self.repository.get_buyer_address(buyer.id, address_public_id)
        if address is None:
            if address_public_id is None:
                raise ValidationError("Add a delivery address first.")
            raise NotFoundError("Address not found.")

        listings = {
            listing.public_id: listing
            for listing in await self.repository.lock_listings([line.listing_public_id for line in lines])
        }
        pre_bid: set[int] = set()
        if not from_accepted_bid:
            pre_bid = await self.repository.listings_with_open_bid_event([l.id for l in listings.values()])

        # Check every line first, so a refused checkout changes nothing.
        now = datetime.now(timezone.utc)
        checked: list[tuple[OrderLine, ProductListing]] = []
        for line in lines:
            listing = listings.get(line.listing_public_id)
            if listing is None or listing.status != "ACTIVE":
                raise NotFoundError("Listing not found.")
            if listing.seller_id == buyer.id:
                raise ValidationError("You can't buy your own crop.")
            if line.quantity <= 0:
                raise ValidationError("Quantity must be more than 0.")
            if not from_accepted_bid:
                if listing.id in pre_bid:
                    raise ConflictError(f"'{listing.title}' is sold by pre-bid. Place a bid instead.")
                if (listing.starts_at and listing.starts_at > now) or (listing.ends_at and listing.ends_at <= now):
                    raise ConflictError(f"'{listing.title}' is not on sale right now.")
                if listing.minimum_order_quantity and line.quantity < listing.minimum_order_quantity:
                    raise ValidationError(
                        f"The minimum order for '{listing.title}' is "
                        f"{listing.minimum_order_quantity} {listing.unit}."
                    )
            if line.quantity > listing.available_quantity:
                raise ConflictError(
                    f"Only {listing.available_quantity} {listing.unit} of '{listing.title}' is left."
                )
            checked.append((line, listing))

        # One order per farmer (Decisions log: one order = one farmer).
        per_farmer: dict[int, list[tuple[OrderLine, ProductListing]]] = {}
        for line, listing in checked:
            per_farmer.setdefault(listing.seller_id, []).append((line, listing))
        for group in per_farmer.values():
            if len({listing.currency for _, listing in group}) > 1:
                raise ValidationError("One farmer's crops must share one currency.")

        checkout_number = f"CHK-{uuid4().hex[:8].upper()}"
        snapshot = _address_snapshot(address)
        orders: list[Order] = []
        for number, group in enumerate(per_farmer.values(), start=1):
            items = []
            for line, listing in group:
                unit_price = line.unit_price if line.unit_price is not None else listing.price
                listing.available_quantity -= line.quantity  # the row is locked (lock_listings)
                items.append({
                    "seller_id": listing.seller_id,
                    "farm_id": listing.farm_id,
                    "listing_id": listing.id,
                    "crop_batch_id": listing.crop_batch_id,
                    "title_snapshot": listing.title,
                    "unit_price": unit_price,
                    "quantity": line.quantity,
                    "unit": listing.unit,
                    "line_total": (unit_price * line.quantity).quantize(MONEY, ROUND_HALF_UP),
                    "status": "PLACED",
                })
            subtotal = sum((item["line_total"] for item in items), Decimal("0"))
            order = await self.repository.create_with_items(
                {
                    "buyer_id": buyer.id,
                    "order_number": f"{checkout_number}-{number}",
                    "status": "PLACED",
                    "currency": group[0][1].currency,
                    "subtotal": subtotal,
                    "delivery_fee": Decimal("0"),
                    "tax_amount": Decimal("0"),
                    "discount_amount": Decimal("0"),
                    "total_amount": subtotal,
                    "delivery_address_snapshot": snapshot,
                    "placed_at": now,
                },
                items,
            )
            orders.append(order)
        return checkout_number, orders

    async def confirm(self, public_id: UUID, current_user: User) -> Order:
        """The farmer selling this order confirms it: PLACED -> CONFIRMED (S26 then makes the load)."""
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id, for_update=True)
        if entity is None:
            raise NotFoundError("Order not found.")
        if entity.buyer_id == current_user.id:
            raise ForbiddenError("Only the farmer selling this order can confirm it.")
        if entity.status != "PLACED":
            raise ConflictError("Only a PLACED order can be confirmed.")
        if not await self.repository.confirm_open_items(entity.id, open_statuses=OPEN_ITEM_STATUSES):
            raise ConflictError("Every item in this order was cancelled.")
        return await self.repository.update(entity, status="CONFIRMED")

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> Order:
        # Lock the order row so a seller can't move an item forward while we cancel.
        entity = await self.repository.get_visible_by_public_id(
            public_id, current_user.id, for_update=True
        )
        if entity is None:
            raise NotFoundError("Order not found.")
        if entity.buyer_id != current_user.id:
            raise ForbiddenError("Only the buyer can change this order.")

        if data.get("status") == "CANCELLED":
            if entity.status not in CANCELLABLE_STATUSES or await self.repository.has_items_in(
                entity.id, SHIPPED_ITEM_STATUSES
            ):
                raise ConflictError("This order can no longer be cancelled.")
            final_statuses = SHIPPED_ITEM_STATUSES | {"CANCELLED"}
            # Stock goes back to the listings before the items are cancelled.
            await self.repository.give_back_stock_of_open_items(entity.id, final_statuses=final_statuses)
            await self.repository.cancel_open_items(entity.id, final_statuses=final_statuses)
            return await self.repository.update(entity, status="CANCELLED")

        raise ValidationError("Nothing to change.")
