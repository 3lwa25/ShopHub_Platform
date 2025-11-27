"""
Context processor for wishlist data.
"""

from .models import Wishlist


def wishlist_context(request):
    """
    Expose wishlist metadata (count + preview) to templates.
    Only available for authenticated buyers.
    """
    wishlist_count = 0
    wishlist_item_ids = []

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "is_buyer", False):
        return {
            "wishlist_count": wishlist_count,
            "wishlist_item_ids": wishlist_item_ids,
        }

    try:
        wishlist = Wishlist.objects.prefetch_related("items__product").filter(user=user).first()
        if wishlist:
            wishlist_count = wishlist.item_count
            wishlist_item_ids = list(wishlist.items.values_list("product_id", flat=True)[:8])
    except Exception:
        # Fail silently so the navbar never breaks the entire page render.
        pass

    return {
        "wishlist_count": wishlist_count,
        "wishlist_item_ids": wishlist_item_ids,
    }

