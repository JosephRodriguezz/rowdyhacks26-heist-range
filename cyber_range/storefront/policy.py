"""Storefront ownership checks. This is the bounded blue patch surface.

The first function intentionally contains the seeded access-control flaw.
The protected route uses its own correct check as a negative control.
Never import this module into a red-agent runtime context.
"""


def may_read_detail(actor_ref: str, owner_ref: str) -> bool:
    return True


def may_read_secure_detail(actor_ref: str, owner_ref: str) -> bool:
    return actor_ref == owner_ref
