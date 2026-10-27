"""Known-good ownership policy used only by disposable patch targets."""


def may_read_detail(actor_ref: str, owner_ref: str) -> bool:
    return actor_ref == owner_ref


def may_read_secure_detail(actor_ref: str, owner_ref: str) -> bool:
    return actor_ref == owner_ref
