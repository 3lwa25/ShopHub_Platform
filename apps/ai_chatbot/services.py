"""
Service layer for the AI chatbot: Gemini integration + product knowledge retrieval.
Enhanced with comprehensive error handling and validation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from django.apps import apps as django_apps
from django.conf import settings
from django.db.models import (
    Q,
    CharField,
    TextField,
    JSONField,
    F,
    ExpressionWrapper,
    FloatField,
    Avg,
    Count,
)
from django.utils import timezone

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from .models import ChatSession, ChatMessage, ProductKnowledge
from apps.products.models import Product
from apps.orders.models import Order
from apps.rewards.models import RewardAccount

logger = logging.getLogger(__name__)

GENERATION_MODEL = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-2.5-flash')
MAX_RETRIES = max(1, getattr(settings, 'GEMINI_MAX_RETRIES', 3))
RETRY_BACKOFF_SECONDS = max(0.1, getattr(settings, 'GEMINI_RETRY_BACKOFF_SECONDS', 1.5))


class ChatbotError(Exception):
    """Base exception for chatbot-related errors."""
    pass


class APIKeyError(ChatbotError):
    """Raised when API key is missing or invalid."""
    pass


class APIConnectionError(ChatbotError):
    """Raised when connection to Gemini API fails."""
    pass


class APIQuotaError(ChatbotError):
    """Raised when API quota is exceeded."""
    pass


def configure_gemini():
    """
    Configure Gemini API with proper validation.
    Raises APIKeyError if configuration fails.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    if not api_key:
        logger.error('GEMINI_API_KEY is not configured in settings.')
        raise APIKeyError(
            'GEMINI_API_KEY is not configured. Please add your API key to the settings.'
        )
    
    if api_key.strip() == '':
        logger.error('GEMINI_API_KEY is empty.')
        raise APIKeyError('GEMINI_API_KEY cannot be empty.')
    
    try:
        genai.configure(api_key=api_key)
        logger.info('Gemini API configured successfully.')
    except Exception as e:
        logger.error(f'Failed to configure Gemini API: {str(e)}')
        raise APIKeyError(f'Failed to configure Gemini API: {str(e)}')


@dataclass
class KnowledgeSnippet:
    """Represents a snippet of product knowledge for context."""
    title: str
    description: str
    category: str
    rating: Optional[float]
    price: Optional[float]
    source: str

    def to_prompt_block(self) -> str:
        """Convert knowledge snippet to formatted text for AI prompt."""
        details = [
            f"📦 Product: {self.title}",
            f"📂 Category: {self.category or 'N/A'}",
        ]
        if self.price:
            details.append(f"💰 Price: ${self.price:.2f}")
        if self.rating:
            details.append(f"⭐ Rating: {self.rating}/5.0")
        details.append(f"📝 Description: {self.description[:500]}")
        details.append(f"🔗 Source: {self.source}")
        return "\n".join(details)


class SchemaOverviewBuilder:
    """Build and cache a concise schema overview for grounding answers."""

    _cached_overview: Optional[str] = None

    @classmethod
    def get_overview(cls) -> str:
        if cls._cached_overview:
            return cls._cached_overview

        summaries = []
        tracked = 0

        for model in django_apps.get_models():
            if model._meta.app_label in DatabaseKnowledgeService.EXCLUDED_APPS:
                continue
            if model._meta.abstract or model._meta.proxy:
                continue

            tracked += 1
            field_descriptions = []
            for field in model._meta.fields:
                field_type = field.get_internal_type()
                if field.is_relation:
                    target = field.related_model._meta.verbose_name.title() if field.related_model else 'Related'
                    field_descriptions.append(f"{field.name}→{target}")
                else:
                    field_descriptions.append(f"{field.name} ({field_type})")

            excerpt = ", ".join(field_descriptions[:6])
            summaries.append(
                f"{model._meta.verbose_name_plural.title()} "
                f"(table `{model._meta.db_table}`): {excerpt}"
            )

            if tracked >= 12:
                break

        cls._cached_overview = "\n".join(summaries[:12])
        return cls._cached_overview


class ProductCatalogSearch:
    """Search the live product catalog for dynamic snippets."""

    @staticmethod
    def _base_queryset():
        return (
            Product.objects.filter(status='active')
            .select_related('category', 'seller__user')
        )

    @classmethod
    def search(cls, query: str, limit: int = 3) -> List[KnowledgeSnippet]:
        if limit <= 0:
            return []

        qs = cls._base_queryset()
        query = (query or '').strip()
        query_lower = query.lower()

        if query:
            terms = [term for term in query.split() if len(term) >= 2]
            if terms:
                combined = Q()
                for term in terms:
                    combined |= (
                        Q(title__icontains=term) |
                        Q(description__icontains=term) |
                        Q(sku__icontains=term) |
                        Q(category__name__icontains=term)
                    )
                qs = qs.filter(combined)

        if not qs.exists():
            qs = cls._base_queryset().order_by('-rating', '-review_count', '-created_at')[:limit]
        else:
            qs = qs.order_by('-rating', '-review_count', '-stock')[:limit]

        snippets: List[KnowledgeSnippet] = []
        for product in qs:
            related_titles = []
            if product.category:
                related_qs = (
                    cls._base_queryset()
                    .filter(category=product.category)
                    .exclude(pk=product.pk)
                    .order_by('-rating')[:2]
                )
                related_titles = [rel.title for rel in related_qs]

            highlights = []
            if product.attributes:
                for key, value in list(product.attributes.items())[:3]:
                    highlights.append(f"{key.title()}: {value}")

            description_parts = [
                (product.description or "")[:220],
                f"SKU: {product.sku}",
                f"Available stock: {product.stock}",
                f"Price: EGP {product.price:.2f}",
            ]
            if product.rating:
                description_parts.append(
                    f"Rating: {float(product.rating):.1f}/5 from {product.review_count} reviews"
                )
            if highlights:
                description_parts.append("Highlights: " + ", ".join(highlights))
            if related_titles:
                description_parts.append("Similar picks: " + ", ".join(related_titles))

            snippets.append(
                KnowledgeSnippet(
                    title=product.title,
                    description="\n".join(description_parts),
                    category=product.category.name if product.category else 'Catalog',
                    rating=float(product.rating) if product.rating else None,
                    price=float(product.price),
                    source='database::products',
                )
            )

        if len(snippets) < limit:
            snippets.extend(cls.best_offers(limit=limit - len(snippets), query=query_lower))
        if cls._wants_comparison(query_lower) and len(snippets) < limit:
            snippets.extend(cls.comparison_snippets(query_lower, limit=limit - len(snippets)))

        return snippets

    @staticmethod
    def _category_hint(query: str) -> str | None:
        if not query:
            return None
        prioritized = ['phone', 'mobile', 'smartphone', 'laptop', 'tablet', 'camera', 'shoe', 'fashion', 'beauty', 'gaming']
        for token in prioritized:
            if token in query:
                return token
        terms = [term for term in query.split() if len(term) > 3]
        return terms[0] if terms else None

    @classmethod
    def best_offers(cls, limit: int = 3, query: str | None = None) -> List[KnowledgeSnippet]:
        if limit <= 0:
            return []

        qs = cls._base_queryset().filter(compare_at_price__gt=F('price'))
        category_hint = cls._category_hint(query or '')
        if category_hint:
            qs = qs.filter(Q(category__name__icontains=category_hint) | Q(title__icontains=category_hint))
        qs = qs.annotate(
            discount_amount=F('compare_at_price') - F('price'),
            discount_percent=ExpressionWrapper(
                (F('compare_at_price') - F('price')) / F('compare_at_price') * 100,
                output_field=FloatField(),
            ),
        ).order_by('-discount_amount', '-discount_percent', '-rating')[:limit]
        if not qs:
            qs = cls._base_queryset().order_by('-rating', '-review_count')[:limit]

        snippets: List[KnowledgeSnippet] = []
        for product in qs:
            discount_amount = getattr(product, 'discount_amount', None)
            discount_percent = getattr(product, 'discount_percent', None)
            bullet_points = [
                product.description[:200] if product.description else '',
                f"Current Price: EGP {product.price:.2f}",
            ]
            if product.compare_at_price:
                bullet_points.append(f"Was: EGP {product.compare_at_price:.2f}")
            if discount_amount:
                bullet_points.append(f"You save: EGP {float(discount_amount):.2f}")
            if discount_percent:
                bullet_points.append(f"Discount: {float(discount_percent):.1f}% off")
            if product.rating:
                bullet_points.append(f"Rating: {float(product.rating):.1f}/5 from {product.review_count} reviews")

            snippets.append(
                KnowledgeSnippet(
                    title=f"Deal • {product.title}",
                    description="\n".join([line for line in bullet_points if line]),
                    category=product.category.name if product.category else 'Deals',
                    rating=float(product.rating) if product.rating else None,
                    price=float(product.price),
                    source='database::best_offers',
                )
            )
        return snippets

    @staticmethod
    def _wants_comparison(query: str) -> bool:
        keywords = {'compare', 'comparison', 'versus', 'vs'}
        return any(word in query for word in keywords)

    @classmethod
    def comparison_snippets(cls, query: str, limit: int = 3) -> List[KnowledgeSnippet]:
        hint = cls._category_hint(query)
        qs = cls._base_queryset()
        if hint:
            qs = qs.filter(Q(category__name__icontains=hint) | Q(title__icontains=hint))
        qs = qs.order_by('-rating', '-review_count')[:limit]

        snippets: List[KnowledgeSnippet] = []
        for product in qs:
            highlights = []
            attrs = product.attributes or {}
            for key, value in list(attrs.items())[:3]:
                highlights.append(f"{key.title()}: {value}")
            description = [
                f"Rating: {float(product.rating):.1f}/5 ({product.review_count} reviews)" if product.rating else '',
                f"Price: EGP {product.price:.2f}",
            ]
            if highlights:
                description.append("Highlights: " + ", ".join(highlights))

            snippets.append(
                KnowledgeSnippet(
                    title=f"Comparison candidate: {product.title}",
                    description="\n".join([line for line in description if line]),
                    category=product.category.name if product.category else 'Comparison',
                    rating=float(product.rating) if product.rating else None,
                    price=float(product.price),
                    source='database::comparison',
                )
            )
        return snippets


class DomainKnowledgeService:
    """Provide curated snippets for common e-commerce intents (deals, coupons, rewards, VTO)."""

    DEAL_KEYWORDS = {'deal', 'deals', 'discount', 'offer', 'offers', 'sale', 'best price', 'best deals', 'best', 'smartphone', 'phone', 'phones', 'mobile', 'mobiles'}
    COUPON_KEYWORDS = {'coupon', 'coupons', 'promo', 'promotion', 'voucher', 'code'}
    REWARD_KEYWORDS = {'reward', 'rewards', 'points', 'loyalty', 'tier'}
    VTO_KEYWORDS = {'vto', 'virtual try-on', 'virtual tryon', 'try on'}
    COMPARE_KEYWORDS = {'compare', 'comparison', 'versus', 'vs'}

    @classmethod
    def get_snippets(cls, query: str) -> List[KnowledgeSnippet]:
        q = (query or '').lower()
        if not q:
            return []

        snippets: List[KnowledgeSnippet] = []

        if any(keyword in q for keyword in cls.DEAL_KEYWORDS):
            snippets.extend(cls._best_deals())
        if any(keyword in q for keyword in cls.COUPON_KEYWORDS):
            snippets.extend(cls._coupon_snippets())
        if any(keyword in q for keyword in cls.REWARD_KEYWORDS):
            snippets.extend(cls._rewards_snippet())
        if any(keyword in q for keyword in cls.VTO_KEYWORDS):
            snippets.extend(cls._vto_snippet())
        if any(keyword in q for keyword in cls.COMPARE_KEYWORDS):
            snippets.extend(cls._comparison_snippet())

        return snippets

    @staticmethod
    def _best_deals(limit: int = 3) -> List[KnowledgeSnippet]:
        discounted_products = (
            Product.objects.filter(status='active', compare_at_price__gt=F('price'))
            .annotate(discount_amount=F('compare_at_price') - F('price'))
            .order_by('-discount_amount', '-rating')[:limit]
        )

        snippets: List[KnowledgeSnippet] = []
        for product in discounted_products:
            discount_value = getattr(product, 'discount_amount', None)
            desc_lines = [
                product.description[:200] if product.description else '',
                f"Current Price: EGP {product.price:.2f}",
            ]
            if product.compare_at_price:
                desc_lines.append(f"Was: EGP {product.compare_at_price:.2f}")
            if discount_value:
                desc_lines.append(f"You save: EGP {discount_value:.2f}")
            if product.rating:
                desc_lines.append(f"Rating: {float(product.rating):.1f}/5 across {product.review_count} reviews")

            snippets.append(
                KnowledgeSnippet(
                    title=product.title,
                    description="\n".join([line for line in desc_lines if line]),
                    category=product.category.name if product.category else 'Deals',
                    rating=float(product.rating) if product.rating else None,
                    price=float(product.price),
                    source='database::best_deals',
                )
            )
        return snippets

    @staticmethod
    def _coupon_snippets(limit: int = 3) -> List[KnowledgeSnippet]:
        try:
            from apps.orders.coupon_models import Coupon
        except Exception:
            return []

        now = timezone.now()
        coupons = (
            Coupon.objects.filter(is_active=True, valid_from__lte=now, valid_to__gte=now)
            .order_by('-discount_value')[:limit]
        )
        snippets = []
        for coupon in coupons:
            description = coupon.description or "ShopHub promotion"
            description += f"\nDiscount: {coupon.get_discount_display()}"
            if coupon.min_order_value:
                description += f"\nMin order: EGP {coupon.min_order_value:.2f}"
            if coupon.valid_to:
                description += f"\nValid until: {coupon.valid_to.strftime('%Y-%m-%d')}"
            snippets.append(
                KnowledgeSnippet(
                    title=f"Coupon {coupon.code}",
                    description=description,
                    category='Coupons',
                    rating=None,
                    price=None,
                    source='database::coupons',
                )
            )
        return snippets

    @staticmethod
    def _rewards_snippet() -> List[KnowledgeSnippet]:
        tiers = [
            "Bronze: 0-1,999 pts",
            "Silver: 2,000+ pts",
            "Gold: 5,000+ pts",
            "Platinum: 10,000+ pts with VIP perks",
        ]
        description = (
            "Earn 10 points per EGP spent once orders are delivered. "
            "Points unlock tiered benefits and can be redeemed at checkout. "
            "Tiers:\n- " + "\n- ".join(tiers)
        )
        return [
            KnowledgeSnippet(
                title="Rewards & Loyalty Program",
                description=description,
                category='Rewards',
                rating=None,
                price=None,
                source='database::rewards',
            )
        ]

    @staticmethod
    def _vto_snippet() -> List[KnowledgeSnippet]:
        description = (
            "Use Virtual Try-On from /virtual-tryon/: upload a room or selfie photo, select an enabled product, and "
            "ShopHub's Gemini pipeline removes backgrounds, places items realistically, and auto-expires uploads after 30 days."
        )
        return [
            KnowledgeSnippet(
                title="Virtual Try-On (VTO)",
                description=description,
                category='Virtual Try-On',
                rating=None,
                price=None,
                source='platform::vto',
            )
        ]

    @staticmethod
    def _comparison_snippet(limit: int = 3) -> List[KnowledgeSnippet]:
        top_categories = (
            Product.objects.filter(status='active', rating__isnull=False)
            .values('category__name')
            .annotate(avg_rating=Avg('rating'), count=Count('id'))
            .order_by('-avg_rating', '-count')[:limit]
        )
        snippets = []
        for cat in top_categories:
            if not cat['category__name']:
                continue
            description = (
                f"Average rating {float(cat['avg_rating']):.1f}/5 with {cat['count']} active listings. "
                "Use comparison prompts like 'Compare the top 3 items in this category' to get spec breakdowns."
            )
            snippets.append(
                KnowledgeSnippet(
                    title=f"Category spotlight: {cat['category__name']}",
                    description=description,
                    category='Comparison',
                    rating=float(cat['avg_rating']),
                    price=None,
                    source='database::category_stats',
                )
            )
        return snippets


class PersonalizedKnowledgeService:
    """Inject user-specific context (orders, rewards, account) into the AI prompt when available."""

    ORDER_KEYWORDS = (
        'order',
        'orders',
        'purchase',
        'purchases',
        'delivery',
        'delivered',
        'tracking',
        'shipment',
        'invoice',
        'my package',
    )
    REWARD_KEYWORDS = (
        'reward',
        'rewards',
        'points',
        'loyalty',
        'tier',
    )
    ACCOUNT_KEYWORDS = (
        'account',
        'profile',
        'my info',
        'contact',
        'address',
    )

    @classmethod
    def gather(cls, session: ChatSession, query: str) -> List[KnowledgeSnippet]:
        if not session or not getattr(session, 'user_id', None):
            return []

        normalized_query = (query or '').lower()
        user = session.user
        snippets: List[KnowledgeSnippet] = []

        if cls._mentions(normalized_query, cls.ORDER_KEYWORDS):
            order_snippet = cls._latest_order_snippet(user)
            if order_snippet:
                snippets.append(order_snippet)

        if cls._mentions(normalized_query, cls.REWARD_KEYWORDS):
            reward_snippet = cls._reward_summary_snippet(user)
            if reward_snippet:
                snippets.append(reward_snippet)

        if not snippets and cls._mentions(normalized_query, cls.ACCOUNT_KEYWORDS):
            account_snippet = cls._account_overview_snippet(user)
            if account_snippet:
                snippets.append(account_snippet)

        return snippets

    @staticmethod
    def _mentions(query: str, keywords: tuple) -> bool:
        if not query:
            return False
        return any(keyword in query for keyword in keywords)

    @staticmethod
    def _latest_order_snippet(user) -> KnowledgeSnippet | None:
        order = (
            Order.objects.filter(buyer=user)
            .prefetch_related('items', 'shipments')
            .order_by('-created_at')
            .first()
        )

        if not order:
            return KnowledgeSnippet(
                title="Order history",
                description="No orders have been placed with this ShopHub account yet.",
                category="Personal Orders",
                rating=None,
                price=None,
                source='personal::orders',
            )

        lines = [
            f"Order Number: {order.order_number}",
            f"Placed On: {order.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Order Status: {order.get_status_display()}",
            f"Payment Status: {order.get_payment_status_display()}",
            f"Total: EGP {order.total_amount:.2f}",
        ]

        shipping = order.shipping_address or {}
        shipping_line = PersonalizedKnowledgeService._format_address(shipping)
        if shipping_line:
            lines.append(f"Ship To: {shipping_line}")

        item_lines = []
        for item in order.items.all():
            subtotal = float(item.subtotal) if hasattr(item, 'subtotal') else float(item.unit_price * item.quantity)
            item_lines.append(f"- {item.product_name} ×{item.quantity} (EGP {subtotal:.2f})")
        if item_lines:
            lines.append("Items:")
            lines.extend(item_lines[:4])
            if len(item_lines) > 4:
                lines.append(f"+ {len(item_lines) - 4} more item(s)")

        shipment_line = PersonalizedKnowledgeService._shipment_summary(order)
        if shipment_line:
            lines.append(shipment_line)

        return KnowledgeSnippet(
            title=f"Latest order {order.order_number}",
            description="\n".join(lines),
            category="Personal Orders",
            rating=None,
            price=float(order.total_amount),
            source='personal::orders',
        )

    @staticmethod
    def _reward_summary_snippet(user) -> KnowledgeSnippet | None:
        account = getattr(user, 'reward_account', None)
        if account is None:
            account = RewardAccount.objects.filter(user=user).first()

        if not account:
            return KnowledgeSnippet(
                title="Rewards overview",
                description="No reward account exists yet. Earn points by completing deliveries to unlock tier benefits.",
                category="Rewards",
                rating=None,
                price=None,
                source='personal::rewards',
            )

        lines = [
            f"Points Balance: {account.points_balance}",
            f"Tier: {account.get_tier_display()}",
            f"Lifetime Earned: {account.total_earned}",
            f"Lifetime Spent: {account.total_spent}",
            f"Approximate Value: EGP {account.points_value_egp:.2f}",
        ]

        latest_txn = account.user.points_transactions.order_by('-created_at').first()
        if latest_txn:
            txn_prefix = "Earned" if latest_txn.amount > 0 else "Redeemed"
            lines.append(
                f"Latest activity: {txn_prefix} {abs(latest_txn.amount)} pts on {latest_txn.created_at.strftime('%Y-%m-%d')}"
            )

        return KnowledgeSnippet(
            title="Rewards balance",
            description="\n".join(lines),
            category="Rewards",
            rating=None,
            price=None,
            source='personal::rewards',
        )

    @staticmethod
    def _account_overview_snippet(user) -> KnowledgeSnippet:
        lines = [
            f"Name: {user.full_name or user.get_full_name()}",
            f"Email: {user.email}",
            f"Role: {user.get_role_display()}",
            f"Member Since: {user.created_at.strftime('%Y-%m-%d')}",
        ]
        if getattr(user, 'phone', None):
            lines.append(f"Phone: {user.phone}")

        return KnowledgeSnippet(
            title="Account overview",
            description="\n".join(lines),
            category="Account",
            rating=None,
            price=None,
            source='personal::account',
        )

    @staticmethod
    def _format_address(address_dict: dict) -> str:
        if not isinstance(address_dict, dict):
            return ''
        parts = [
            address_dict.get('full_name'),
            address_dict.get('address_line1'),
            address_dict.get('city'),
            address_dict.get('state'),
            address_dict.get('country'),
        ]
        cleaned = [part for part in parts if part]
        return ", ".join(cleaned)

    @staticmethod
    def _shipment_summary(order: Order) -> str:
        shipment = order.shipments.order_by('-updated_at').first()
        if not shipment:
            return ''

        status_display = shipment.current_status.replace('_', ' ').title()
        details = [f"Shipment Status: {status_display}"]
        if shipment.tracking_number:
            details.append(f"Tracking #: {shipment.tracking_number}")

        last_event = PersonalizedKnowledgeService._latest_event(shipment.history)
        if last_event:
            timestamp = PersonalizedKnowledgeService._humanize_timestamp(last_event.get('timestamp'))
            location = last_event.get('location') or 'N/A'
            details.append(f"Last Update: {timestamp} @ {location}")

        return " | ".join(details)

    @staticmethod
    def _latest_event(history) -> dict | None:
        if not isinstance(history, list):
            return None
        events = [event for event in history if isinstance(event, dict)]
        return events[-1] if events else None

    @staticmethod
    def _humanize_timestamp(timestamp: str | None) -> str:
        if not timestamp:
            return 'Unknown time'
        try:
            date_part, time_part = timestamp.split('T', 1)
            time_part = time_part.split('.')[0]
            return f"{date_part} {time_part}"
        except ValueError:
            return timestamp


class ProductKnowledgeBase:
    """Utility helpers for retrieving structured product context."""

    @classmethod
    def search(cls, query: str, limit: int = 5) -> List[KnowledgeSnippet]:
        """
        Search for relevant product knowledge based on query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of KnowledgeSnippet objects
        """
        query = query.strip()
        if not query:
            logger.debug('Empty search query provided.')
            return []

        try:
            # Search in ProductKnowledge database
            qs = ProductKnowledge.objects.filter(
                Q(title__icontains=query) |
                Q(category__icontains=query) |
                Q(description__icontains=query)
            ).order_by('-last_updated')[:limit]

            snippets = [
                KnowledgeSnippet(
                    title=entry.title,
                    description=entry.description or "No description available.",
                    category=entry.category,
                    rating=float(entry.average_rating) if entry.average_rating is not None else None,
                    price=float(entry.price) if entry.price is not None else None,
                    source=entry.source or 'product_knowledge_db',
                )
                for entry in qs
            ]

            # Fallback to live products if knowledge base is empty
            if not snippets:
                logger.debug('No results in ProductKnowledge, falling back to Product catalog.')
                product_qs = Product.objects.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(category__name__icontains=query)
                ).select_related('category')[:limit]
                
                for product in product_qs:
                    desc = product.description or "No detailed description available."
                    snippets.append(
                        KnowledgeSnippet(
                            title=product.title,
                            description=desc,
                            category=product.category.name if product.category else 'General',
                            rating=float(product.rating) if product.rating else None,
                            price=float(product.price) if product.price else None,
                            source='live_product_catalog',
                        )
                    )

            logger.info(f'Found {len(snippets)} knowledge snippets for query: "{query}"')
            return snippets
        
        except Exception as e:
            logger.error(f'Error searching product knowledge: {str(e)}')
            return []


class DatabaseKnowledgeService:
    """Prioritize direct knowledge pulled from the primary project database."""
    
    SAFE_FIELD_KEYWORDS = (
        'title',
        'name',
        'description',
        'summary',
        'status',
        'category',
        'policy',
        'question',
        'answer',
        'guide',
        'faq',
        'details',
        'note',
        'spec',
        'specs',
        'info',
        'content',
        'body',
        'feature',
        'message',
        'terms',
    )
    EXCLUDED_APPS = {'admin', 'sessions', 'auth', 'contenttypes'}
    MAX_PER_MODEL = 4
    
    @classmethod
    def search(cls, query: str, limit: int = 5, include_schema_fallback: bool = False) -> List[KnowledgeSnippet]:
        """Scan safe textual fields across installed models for matching knowledge."""
        query = (query or '').strip()
        if not query:
            return cls._schema_fallback() if include_schema_fallback else []
        
        snippets: List[KnowledgeSnippet] = []
        seen_sources = set()
        
        for model in django_apps.get_models():
            if len(snippets) >= limit:
                break
            if not cls._is_searchable_model(model):
                continue
            
            text_fields = cls._get_searchable_fields(model)
            if not text_fields:
                continue
            
            q_obj = Q()
            for field_name in text_fields:
                q_obj |= Q(**{f"{field_name}__icontains": query})
            
            try:
                results = model.objects.filter(q_obj)[:cls.MAX_PER_MODEL]
            except Exception as exc:
                logger.debug('Skipping %s due to query error: %s', model._meta.label, exc)
                continue
            
            for instance in results:
                description = cls._format_instance(instance, text_fields)
                if not description:
                    continue
                source_key = f"{model._meta.label_lower}:{getattr(instance, 'pk', 'unknown')}"
                if source_key in seen_sources:
                    continue
                snippets.append(
                    KnowledgeSnippet(
                        title=cls._instance_title(model, instance),
                        description=description,
                        category=model._meta.verbose_name.title(),
                        rating=None,
                        price=None,
                        source=f"database::{model._meta.db_table}",
                    )
                )
                seen_sources.add(source_key)
                if len(snippets) >= limit:
                    break
        
        if not snippets and include_schema_fallback:
            snippets.extend(cls._schema_fallback())
        
        return snippets
    
    @classmethod
    def _is_searchable_model(cls, model) -> bool:
        if model._meta.app_label in cls.EXCLUDED_APPS:
            return False
        if model._meta.abstract or model._meta.proxy:
            return False
        return True
    
    @classmethod
    def _get_searchable_fields(cls, model) -> List[str]:
        searchable = []
        for field in model._meta.get_fields():
            if field.is_relation:
                continue
            if not isinstance(field, (CharField, TextField, JSONField)):
                continue
            field_name = field.name.lower()
            if any(keyword in field_name for keyword in cls.SAFE_FIELD_KEYWORDS):
                searchable.append(field.name)
        return searchable
    
    @staticmethod
    def _instance_title(model, instance) -> str:
        for attr in ('title', 'name', 'question'):
            value = getattr(instance, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return f"{model._meta.verbose_name.title()} #{getattr(instance, 'pk', 'N/A')}"
    
    @staticmethod
    def _format_instance(instance, fields: List[str]) -> str:
        chunks = []
        for field_name in fields:
            value = getattr(instance, field_name, '')
            if isinstance(value, (dict, list)):
                value = DatabaseKnowledgeService._stringify_json(value)
            elif not isinstance(value, str):
                value = str(value)
            value = value.strip()
            if not value:
                continue
            label = field_name.replace('_', ' ').title()
            snippet = value[:220]
            chunks.append(f"{label}: {snippet}")
        return " | ".join(chunks)[:600]

    @staticmethod
    def _stringify_json(data) -> str:
        if isinstance(data, dict):
            pairs = [f"{key.title()}: {str(val)[:80]}" for key, val in list(data.items())[:5]]
            return ", ".join(pairs)
        if isinstance(data, list):
            return ", ".join(str(item) for item in data[:5])
        return str(data)

    @classmethod
    def _schema_fallback(cls) -> List[KnowledgeSnippet]:
        overview = SchemaOverviewBuilder.get_overview()
        if not overview:
            return []
        return [
            KnowledgeSnippet(
                title="ShopHub database overview",
                description=overview,
                category="System Schema",
                rating=None,
                price=None,
                source='database::schema',
            )
        ]


class GeminiChatService:
    """High-level orchestrator for sending prompts to Gemini with context."""

    def __init__(self):
        """Initialize the Gemini chat service."""
        try:
            configure_gemini()
            self.model = genai.GenerativeModel(GENERATION_MODEL)
            logger.info(f'GeminiChatService initialized with model: {GENERATION_MODEL}')
        except APIKeyError as e:
            logger.error(f'Failed to initialize GeminiChatService: {str(e)}')
            raise
        except Exception as e:
            logger.error(f'Unexpected error initializing GeminiChatService: {str(e)}')
            raise ChatbotError(f'Failed to initialize chatbot service: {str(e)}')

    def build_system_prompt(self, knowledge_snippets: List[KnowledgeSnippet]) -> str:
        """
        Build comprehensive system prompt with product knowledge context.
        
        Args:
            knowledge_snippets: List of relevant product knowledge
            
        Returns:
            Formatted system prompt string
        """
        product_blocks = "\n\n".join(
            snippet.to_prompt_block() for snippet in knowledge_snippets
        )
        
        instructions = (
            "🛍️ You are ShopHub's AI Shopping Assistant, powered by Google Gemini.\n\n"
            "Your role:\n"
            "• Help customers find the perfect products\n"
            "• Provide detailed product information with prices and ratings\n"
            "• Compare products and recommend based on needs and budget\n"
            "• Answer questions about shopping, orders, and returns\n"
            "• Be friendly, helpful, and professional\n\n"
            "Guidelines:\n"
            "• Use the product knowledge provided to give accurate answers about ShopHub products\n"
            "• Never respond that you lack access to ShopHub data—summarize whatever the database returned and explain if certain tables did not match\n"
            "• When personal order/account context is supplied, treat it as authoritative and reference it directly instead of saying you lack access\n"
            "• Cite specific product facts (price, rating, features, availability)\n"
            "• If product information is not in the provided knowledge, you can use your general knowledge or search capabilities\n"
            "• For questions outside ShopHub's catalog, provide helpful general e-commerce advice\n"
            "• Suggest next steps (e.g., viewing product page, adding to cart, browsing categories)\n"
            "• If unsure about a specific ShopHub product, be honest and offer to help find the information\n"
            "• Keep responses concise but informative\n"
            "• You have access to real-time product data and can provide current prices, stock status, and ratings\n"
        )
        
        if product_blocks:
            instructions += "\n\n📚 Relevant Product Knowledge:\n\n" + product_blocks
        else:
            instructions += (
                "\n\n⚠️ Note: No specific product knowledge was found for this query. "
                "Rely on general e-commerce knowledge and suggest the customer browse the catalog."
            )
        
        return instructions

    def build_history(self, session: ChatSession, limit: int = 6) -> List[dict]:
        """
        Build conversation history from chat session.
        
        Args:
            session: ChatSession object
            limit: Maximum number of messages to include
            
        Returns:
            List of message dictionaries for Gemini API
        """
        role_map = {
            'user': 'user',
            'assistant': 'model',
            'system': 'user',
        }

        try:
            messages = session.get_context_messages(limit=limit)
            history = []
            for message in messages:
                mapped_role = role_map.get(message.role, 'user')
                history.append({
                    "role": mapped_role,
                    "parts": [message.content],
                })
            logger.debug(f'Built history with {len(history)} messages.')
            return history
        except Exception as e:
            logger.error(f'Error building conversation history: {str(e)}')
            return []

    def send(self, session: ChatSession, user_message: str) -> dict:
        """
        Send a message to Gemini and return assistant response payload.
        
        Args:
            session: ChatSession object
            user_message: User's message text
            
        Returns:
            Dictionary with 'text' and 'metadata' keys
            
        Raises:
            ChatbotError: If API call fails
        """
        if not user_message or not user_message.strip():
            raise ChatbotError('User message cannot be empty.')
        
        try:
            personal_snippets = PersonalizedKnowledgeService.gather(session, user_message)
            domain_snippets = DomainKnowledgeService.get_snippets(user_message)

            knowledge_snippets = list(personal_snippets)
            knowledge_snippets.extend(domain_snippets)

            catalog_limit = max(0, 3 - len(knowledge_snippets))
            catalog_snippets = ProductCatalogSearch.search(user_message, limit=catalog_limit)
            knowledge_snippets.extend(catalog_snippets)

            db_snippets = DatabaseKnowledgeService.search(
                user_message,
                limit=max(0, 5 - len(knowledge_snippets)),
            )
            knowledge_snippets.extend(db_snippets)

            if len(knowledge_snippets) < 5:
                fallback_limit = 5 - len(knowledge_snippets)
                knowledge_snippets.extend(
                    ProductKnowledgeBase.search(user_message, limit=fallback_limit)
                )

            schema_snippet_used = False
            if not knowledge_snippets:
                schema_snippets = DatabaseKnowledgeService.search(
                    user_message,
                    limit=1,
                    include_schema_fallback=True,
                )
                if schema_snippets:
                    schema_snippet_used = True
                    knowledge_snippets.extend(schema_snippets)

            # Build system prompt with context
            system_prompt = self.build_system_prompt(knowledge_snippets)
            
            # Build conversation history
            history = self.build_history(session)
            
            # Prepare messages for Gemini
            messages = [{"role": "user", "parts": [system_prompt]}] + history
            if not history or history[-1]["role"] != "user":
                messages.append({"role": "user", "parts": [user_message]})
            
            response = None
            elapsed = 0
            last_error = None

            for attempt in range(MAX_RETRIES):
                try:
                    start = time.monotonic()
                    logger.info(
                        'Sending message to Gemini API (model: %s) [attempt %s/%s]...',
                        GENERATION_MODEL,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    response = self.model.generate_content(
                        messages,
                        safety_settings=getattr(settings, 'GEMINI_SAFETY_SETTINGS', None),
                    )
                    elapsed = int((time.monotonic() - start) * 1000)
                    logger.info(
                        'Received response from Gemini API in %sms on attempt %s.',
                        elapsed,
                        attempt + 1,
                    )
                    break
                except google_exceptions.ResourceExhausted as exc:
                    last_error = exc
                    logger.warning(
                        'Gemini API reported quota/concurrency exhaustion (attempt %s/%s): %s',
                        attempt + 1,
                        MAX_RETRIES,
                        str(exc),
                    )
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BACKOFF_SECONDS * (attempt + 1)
                        logger.info('Retrying Gemini request in %.2fs...', delay)
                        time.sleep(delay)
                        continue
                    logger.error(
                        'Gemini API quota still exhausted after %s attempts.',
                        MAX_RETRIES,
                    )
                    raise APIQuotaError(
                        'The AI service is temporarily busy. Please wait a moment and try again.'
                    ) from exc

            if response is None:
                raise ChatbotError(
                    'No response was received from the AI service after multiple attempts.'
                )
            
            # Extract response text
            assistant_text = response.text.strip()
            
            if not assistant_text:
                logger.warning('Gemini returned empty response.')
                assistant_text = "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
            
            metadata = {
                "model": GENERATION_MODEL,
                "response_time_ms": elapsed,
                "knowledge_hits": len(knowledge_snippets),
                "database_hits": len(db_snippets),
                "catalog_hits": len(catalog_snippets),
                "domain_hits": len(domain_snippets),
                "personal_hits": len(personal_snippets),
                "schema_context": schema_snippet_used,
            }
            
            return {"text": assistant_text, "metadata": metadata}
        
        except google_exceptions.ResourceExhausted as e:
            logger.error(f'Gemini API quota exceeded: {str(e)}')
            raise APIQuotaError(
                'API quota exceeded. Please try again later or contact support.'
            )
        
        except google_exceptions.InvalidArgument as e:
            logger.error(f'Invalid argument sent to Gemini API: {str(e)}')
            raise ChatbotError(
                'Invalid request format. Please try rephrasing your message.'
            )
        
        except google_exceptions.GoogleAPIError as e:
            logger.error(f'Google API error: {str(e)}')
            raise APIConnectionError(
                f'Failed to connect to AI service: {str(e)}'
            )
        
        except Exception as e:
            logger.error(f'Unexpected error in GeminiChatService.send: {str(e)}', exc_info=True)
            raise ChatbotError(
                'An unexpected error occurred. Please try again or contact support.'
            )
