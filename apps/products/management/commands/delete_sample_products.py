"""
Delete Sample Products
Removes all products created by generate_sample_products.py (SKU starts with PROD-)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.models import Product


class Command(BaseCommand):
    help = "Delete all sample products created by generate_sample_products.py"

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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Delete Sample Products\n"
            f"{'='*70}\n"
        ))
        
        # Find all sample products (SKU starts with PROD-)
        sample_products = Product.objects.filter(sku__startswith='PROD-')
        count = sample_products.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ No sample products found!"))
            return
        
        self.stdout.write(f"\n📊 Found {count} sample products to delete")
        
        # Show some examples
        self.stdout.write(f"\n📋 Examples:")
        for product in sample_products[:5]:
            self.stdout.write(f"   • {product.title[:60]} (SKU: {product.sku})")
        if count > 5:
            self.stdout.write(f"   ... and {count - 5} more")
        
        # Dry run mode
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  DRY RUN MODE - No products will be deleted"
            ))
            self.stdout.write(f"   Would delete {count} sample products")
            return
        
        # Confirmation
        if not force:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  This will DELETE {count} sample products!"
            ))
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        # Delete products
        self.stdout.write(f"\n🗑️  Deleting {count} sample products...")
        
        deleted_count = 0
        with transaction.atomic():
            for product in sample_products:
                try:
                    product.delete()
                    deleted_count += 1
                    if deleted_count % 10 == 0:
                        self.stdout.write(f"   Deleted {deleted_count}/{count}...")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ✗ Error deleting {product.sku}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully deleted {deleted_count} sample products!"
        ))
        self.stdout.write(f"   • Remaining products: {Product.objects.count()}")

