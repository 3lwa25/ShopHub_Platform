"""
Cleanup Incomplete Products
Deletes products that are missing essential information:
- No images
- No description (or very short description)
- No specs/attributes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.models import Product


class Command(BaseCommand):
    help = "Delete products missing images, description, or specs"

    def add_arguments(self, parser):
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
        parser.add_argument(
            '--min-description-length',
            type=int,
            default=20,
            help='Minimum description length in characters (default: 20)'
        )
        parser.add_argument(
            '--require-images',
            action='store_true',
            default=True,
            help='Require products to have images (default: True)'
        )
        parser.add_argument(
            '--require-description',
            action='store_true',
            default=True,
            help='Require products to have description (default: True)'
        )
        parser.add_argument(
            '--require-specs',
            action='store_true',
            default=True,
            help='Require products to have specs/attributes (default: True)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        min_desc_length = options['min_description_length']
        require_images = options.get('require_images', True)
        require_description = options.get('require_description', True)
        require_specs = options.get('require_specs', True)
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Cleanup Incomplete Products\n"
            f"{'='*70}\n"
        ))
        self.stdout.write(f"📊 Configuration:")
        self.stdout.write(f"   • Require images: {'YES' if require_images else 'NO'}")
        self.stdout.write(f"   • Require description: {'YES' if require_description else 'NO'}")
        self.stdout.write(f"   • Min description length: {min_desc_length} characters")
        self.stdout.write(f"   • Require specs/attributes: {'YES' if require_specs else 'NO'}")
        self.stdout.write("")
        
        # Get all products
        all_products = Product.objects.filter(status='active').prefetch_related('images')
        
        # Find incomplete products
        incomplete_products = []
        
        for product in all_products:
            is_incomplete = False
            reasons = []
            
            # Check images
            if require_images and not product.images.exists():
                is_incomplete = True
                reasons.append("no images")
            
            # Check description
            if require_description:
                description = (product.description or '').strip()
                if len(description) < min_desc_length:
                    is_incomplete = True
                    reasons.append(f"description too short ({len(description)} chars)")
            
            # Check specs/attributes
            if require_specs:
                attributes = product.attributes or {}
                # Check if attributes is empty or has no meaningful data
                if not attributes or (isinstance(attributes, dict) and len(attributes) == 0):
                    # Also check if description doesn't contain specs
                    description = (product.description or '').lower()
                    spec_keywords = ['feature', 'spec', 'dimension', 'size', 'weight', 'material', 'color', 'brand']
                    has_specs_in_desc = any(keyword in description for keyword in spec_keywords)
                    if not has_specs_in_desc:
                        is_incomplete = True
                        reasons.append("no specs/attributes")
            
            if is_incomplete:
                incomplete_products.append({
                    'product': product,
                    'reasons': reasons
                })
        
        # Statistics
        total_products = all_products.count()
        incomplete_count = len(incomplete_products)
        
        self.stdout.write(f"\n📊 Analysis Results:")
        self.stdout.write(f"   • Total products: {total_products}")
        self.stdout.write(f"   • Incomplete products: {incomplete_count}")
        self.stdout.write(f"   • Complete products: {total_products - incomplete_count}")
        
        if incomplete_count == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ All products are complete!"))
            return
        
        # Show examples
        self.stdout.write(f"\n📋 Examples of incomplete products:")
        for item in incomplete_products[:10]:
            product = item['product']
            reasons = ', '.join(item['reasons'])
            self.stdout.write(f"   • {product.title[:50]} (SKU: {product.sku})")
            self.stdout.write(f"     Reasons: {reasons}")
        if incomplete_count > 10:
            self.stdout.write(f"   ... and {incomplete_count - 10} more")
        
        # Dry run mode
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  DRY RUN MODE - No products will be deleted"
            ))
            self.stdout.write(f"   Would delete {incomplete_count} incomplete products")
            return
        
        # Confirmation
        if not force:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  This will DELETE {incomplete_count} incomplete products!"
            ))
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        # Delete incomplete products
        self.stdout.write(f"\n🗑️  Deleting {incomplete_count} incomplete products...")
        
        deleted_count = 0
        with transaction.atomic():
            for item in incomplete_products:
                product = item['product']
                try:
                    product.delete()
                    deleted_count += 1
                    if deleted_count % 10 == 0:
                        self.stdout.write(f"   Deleted {deleted_count}/{incomplete_count}...", ending='\r')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ✗ Error deleting {product.sku}: {str(e)}"))
        
        self.stdout.write(f"\r   ✓ Deleted {deleted_count} incomplete products                    ")
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully deleted {deleted_count} incomplete products!"
        ))
        self.stdout.write(f"   • Remaining products: {Product.objects.count()}")
        self.stdout.write(f"   • Products with images: {Product.objects.filter(images__isnull=False).distinct().count()}")
        self.stdout.write("\n" + "="*70 + "\n")

