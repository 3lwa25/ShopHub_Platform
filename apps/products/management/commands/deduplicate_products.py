"""
Deduplicate Products
Removes duplicate or very similar products based on title, images, and attributes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from difflib import SequenceMatcher
from apps.products.models import Product, ProductImage


class Command(BaseCommand):
    help = "Remove duplicate or very similar products"

    def add_arguments(self, parser):
        parser.add_argument(
            '--similarity-threshold',
            type=float,
            default=0.85,
            help='Title similarity threshold (0.0-1.0, default: 0.85)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        threshold = options['similarity_threshold']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Deduplicate Products\n"
            f"{'='*70}\n"
        ))
        self.stdout.write(f"📊 Similarity threshold: {threshold}")
        
        # Get all active products
        products = Product.objects.filter(status='active').select_related('category').prefetch_related('images')
        total = products.count()
        
        self.stdout.write(f"📦 Analyzing {total} products...")
        
        # Find duplicates
        duplicates = []
        processed = set()
        
        products_list = list(products)
        for i, product1 in enumerate(products_list):
            if product1.id in processed:
                continue
            
            similar_products = []
            for product2 in products_list[i+1:]:
                if product2.id in processed:
                    continue
                
                # Check if products are similar
                if self._are_similar(product1, product2, threshold):
                    similar_products.append(product2)
            
            if similar_products:
                # Keep the one with most images, highest rating, or most recent
                all_similar = [product1] + similar_products
                best_product = self._select_best_product(all_similar)
                to_delete = [p for p in all_similar if p.id != best_product.id]
                
                duplicates.append({
                    'keep': best_product,
                    'delete': to_delete
                })
                
                # Mark all as processed
                processed.add(product1.id)
                for p in similar_products:
                    processed.add(p.id)
        
        # Statistics
        total_to_delete = sum(len(d['delete']) for d in duplicates)
        
        self.stdout.write(f"\n📊 Results:")
        self.stdout.write(f"   • Duplicate groups found: {len(duplicates)}")
        self.stdout.write(f"   • Products to delete: {total_to_delete}")
        self.stdout.write(f"   • Products to keep: {len(duplicates)}")
        
        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ No duplicates found!"))
            return
        
        # Show examples
        self.stdout.write(f"\n📋 Examples of duplicates:")
        for dup in duplicates[:5]:
            self.stdout.write(f"\n   Keep: {dup['keep'].title[:60]}")
            for p in dup['delete'][:3]:
                self.stdout.write(f"   Delete: {p.title[:60]}")
            if len(dup['delete']) > 3:
                self.stdout.write(f"   ... and {len(dup['delete']) - 3} more")
        
        # Dry run mode
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  DRY RUN MODE - No products will be deleted"
            ))
            self.stdout.write(f"   Would delete {total_to_delete} duplicate products")
            return
        
        # Confirmation
        if not force:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  This will DELETE {total_to_delete} duplicate products!"
            ))
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        # Delete duplicates
        self.stdout.write(f"\n🗑️  Deleting {total_to_delete} duplicate products...")
        
        deleted_count = 0
        with transaction.atomic():
            for dup in duplicates:
                for product in dup['delete']:
                    try:
                        product.delete()
                        deleted_count += 1
                        if deleted_count % 10 == 0:
                            self.stdout.write(f"   Deleted {deleted_count}/{total_to_delete}...")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ✗ Error deleting {product.sku}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully deleted {deleted_count} duplicate products!"
        ))
        self.stdout.write(f"   • Remaining products: {Product.objects.count()}")

    def _are_similar(self, product1, product2, threshold):
        """Check if two products are similar (same title, same images, or same price)"""
        # Same category
        if product1.category != product2.category:
            return False
        
        # Title similarity
        title_sim = SequenceMatcher(None, 
            product1.title.lower().strip(), 
            product2.title.lower().strip()
        ).ratio()
        
        # Check if titles are very similar (duplicate topic)
        if title_sim >= threshold:
            return True
        
        # Check if they have same primary image URL
        attrs1 = product1.attributes or {}
        attrs2 = product2.attributes or {}
        
        primary_url1 = attrs1.get('primary_image_url', '')
        primary_url2 = attrs2.get('primary_image_url', '')
        
        if primary_url1 and primary_url2 and primary_url1 == primary_url2:
            return True
        
        # Check image similarity (same image files)
        images1 = set(img.image.name for img in product1.images.all() if img.image)
        images2 = set(img.image.name for img in product2.images.all() if img.image)
        
        # If they share any images, they're duplicates
        if images1 and images2 and images1.intersection(images2):
            return True
        
        # Check if all images are the same
        if images1 and images2 and images1 == images2:
            return True
        
        return False

    def _select_best_product(self, products):
        """Select the best product to keep from similar ones"""
        # Score each product
        best = None
        best_score = -1
        
        for product in products:
            score = 0
            
            # More images = better
            score += product.images.count() * 10
            
            # Higher rating = better
            score += float(product.rating or 0) * 5
            
            # More reviews = better
            score += product.review_count * 2
            
            # Has images = better
            if product.images.exists():
                score += 20
            
            # More stock = better
            score += min(product.stock, 100) * 0.1
            
            # Featured = better
            if product.is_featured:
                score += 10
            
            if score > best_score:
                best_score = score
                best = product
        
        return best

