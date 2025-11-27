"""
Organize Products
Sets best seller badges, updates featured products, and ensures product knowledge for chatbot
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from apps.products.models import Product, Category
from apps.ai_chatbot.models import ProductKnowledge


class Command(BaseCommand):
    help = "Organize products: set best sellers, update featured, sync chatbot knowledge"

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-best-sellers',
            action='store_true',
            default=True,
            help='Update best seller flags (default: True)'
        )
        parser.add_argument(
            '--update-featured',
            action='store_true',
            help='Update featured products based on ratings'
        )
        parser.add_argument(
            '--sync-chatbot',
            action='store_true',
            default=True,
            help='Sync product knowledge for chatbot (default: True)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Organize Products\n"
            f"{'='*70}\n"
        ))
        
        update_best_sellers = options.get('update_best_sellers', True)
        update_featured = options.get('update_featured', False)
        sync_chatbot = options.get('sync_chatbot', True)
        
        stats = {
            'best_sellers_updated': 0,
            'featured_updated': 0,
            'chatbot_synced': 0,
        }
        
        # Update best sellers by category
        if update_best_sellers:
            self.stdout.write("\n🏆 Updating best sellers by category...")
            stats['best_sellers_updated'] = self._update_best_sellers()
        
        # Update featured products
        if update_featured:
            self.stdout.write("\n⭐ Updating featured products...")
            stats['featured_updated'] = self._update_featured_products()
        
        # Sync chatbot knowledge
        if sync_chatbot:
            self.stdout.write("\n🤖 Syncing product knowledge for chatbot...")
            stats['chatbot_synced'] = self._sync_chatbot_knowledge()
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("  ✅ Organization Complete!"))
        self.stdout.write("="*70)
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   • Best sellers updated: {stats['best_sellers_updated']}")
        self.stdout.write(f"   • Featured products updated: {stats['featured_updated']}")
        self.stdout.write(f"   • Chatbot knowledge synced: {stats['chatbot_synced']}")
        self.stdout.write("\n" + "="*70 + "\n")

    def _update_best_sellers(self):
        """Update best seller flags randomly (for variety) based on ratings, reviews, and images"""
        import random
        updated = 0
        
        # Get all categories
        categories = Category.objects.filter(is_active=True)
        
        for category in categories:
            # Get products in this category with images (best sellers must have images)
            products = Product.objects.filter(
                category=category,
                status='active'
            ).prefetch_related('images')
            
            # Get eligible products (must have images)
            eligible_products = [p for p in products if p.images.exists()]
            
            if not eligible_products:
                continue
            
            # Calculate scores for all eligible products
            scored_products = []
            for product in eligible_products:
                # Calculate score
                score = 0
                if product.rating:
                    score += float(product.rating) * 2
                score += product.review_count * 0.5
                score += 10  # Has images bonus
                if product.stock > 0:
                    score += 5
                
                # Must have at least rating >= 3.0 or review_count >= 3
                if (product.rating and product.rating >= 3.0) or product.review_count >= 3:
                    scored_products.append((score, product))
            
            if not scored_products:
                continue
            
            # Sort by score
            scored_products.sort(key=lambda x: x[0], reverse=True)
            
            # Select top 15, then randomly choose 10 for variety
            top_candidates = [p[1] for p in scored_products[:15]]
            
            # Randomly select 10 from top candidates (adds variety to best sellers)
            if len(top_candidates) >= 10:
                selected_best_sellers = random.sample(top_candidates, 10)
            else:
                selected_best_sellers = top_candidates
            
            # Mark as featured (which is used for best seller badge)
            for product in selected_best_sellers:
                if not product.is_featured:
                    product.is_featured = True
                    product.save(update_fields=['is_featured'])
                    updated += 1
            
            # Unfeature products that are no longer best sellers
            featured_in_category = products.filter(is_featured=True)
            for product in featured_in_category:
                if product not in selected_best_sellers:
                    product.is_featured = False
                    product.save(update_fields=['is_featured'])
                    updated += 1
        
        self.stdout.write(f"   ✓ Updated {updated} products as best sellers (random selection)")
        return updated

    def _update_featured_products(self):
        """Update featured products based on ratings and reviews"""
        updated = 0
        
        # Set featured for high-rated products
        featured = Product.objects.filter(
            status='active',
            rating__gte=4.5,
            review_count__gte=5,
            stock__gt=0
        )
        
        for product in featured:
            if not product.is_featured:
                product.is_featured = True
                product.save(update_fields=['is_featured'])
                updated += 1
        
        # Unfeature low-rated products
        unfeatured = Product.objects.filter(
            status='active',
            is_featured=True,
            rating__lt=3.5
        )
        
        for product in unfeatured:
            product.is_featured = False
            product.save(update_fields=['is_featured'])
            updated += 1
        
        self.stdout.write(f"   ✓ Updated {updated} featured products")
        return updated

    def _sync_chatbot_knowledge(self):
        """Sync all products to chatbot knowledge base with comprehensive information"""
        synced = 0
        updated = 0
        
        products = Product.objects.filter(status='active').select_related('category').prefetch_related('images')
        
        total = products.count()
        self.stdout.write(f"   Processing {total} products...")
        
        for idx, product in enumerate(products, 1):
            try:
                # Build comprehensive description
                description_parts = []
                if product.description:
                    description_parts.append(product.description[:800])
                
                # Add features from attributes
                if product.attributes:
                    features = product.attributes.get('features', [])
                    if features:
                        features_text = '\n'.join(f"• {f}" for f in features[:10] if f)
                        description_parts.append(f"\n\nFeatures:\n{features_text}")
                    
                    brand = product.attributes.get('brand')
                    if brand:
                        description_parts.append(f"\n\nBrand: {brand}")
                
                full_description = ' '.join(description_parts)[:1500]
                
                # Get or create knowledge entry
                knowledge, created = ProductKnowledge.objects.update_or_create(
                    external_id=product.sku,
                    defaults={
                        'product': product,
                        'title': product.title,
                        'category': product.category.name if product.category else 'Uncategorized',
                        'description': full_description or 'No description available.',
                        'highlights': product.attributes.get('features', [])[:20] if product.attributes else [],
                        'average_rating': product.rating or 0,
                        'price': product.price,
                        'source': 'product_sync',
                        'metadata': {
                            'brand': product.attributes.get('brand') if product.attributes else None,
                            'stock': product.stock,
                            'is_featured': product.is_featured,
                            'is_best_seller': product.is_featured,  # Use is_featured as best seller flag
                            'review_count': product.review_count,
                            'has_images': product.images.exists(),
                            'image_count': product.images.count(),
                            'compare_price': float(product.compare_at_price) if product.compare_at_price else None,
                            'discount_percentage': product.discount_percentage if product.is_on_sale else None,
                        },
                    }
                )
                
                if created:
                    synced += 1
                else:
                    updated += 1
                
                if idx % 50 == 0:
                    self.stdout.write(f"   Processed {idx}/{total} products...", ending='\r')
                    
            except Exception as e:
                continue
        
        self.stdout.write(f"\r   ✓ Synced {synced} new products, updated {updated} existing products to chatbot knowledge base")
        return synced + updated

