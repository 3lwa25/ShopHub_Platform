"""
Fix Duplicate Prices
Changes products with identical prices to random prices
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from decimal import Decimal
import random
from apps.products.models import Product


class Command(BaseCommand):
    help = "Fix duplicate prices by assigning random prices to products with same prices"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update without confirmation'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Fix Duplicate Prices\n"
            f"{'='*70}\n"
        ))
        
        # Find products with duplicate prices
        # Group by price and find prices that appear more than once
        price_groups = Product.objects.filter(
            status='active'
        ).values('price').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_duplicates = sum(group['count'] - 1 for group in price_groups)
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicate prices found!"))
            return
        
        self.stdout.write(f"\n📊 Found {len(price_groups)} price groups with duplicates")
        self.stdout.write(f"   Total products with duplicate prices: {total_duplicates}")
        
        # Show examples
        self.stdout.write(f"\n📋 Examples of duplicate prices:")
        for group in price_groups[:5]:
            price = group['price']
            count = group['count']
            self.stdout.write(f"   • ${price}: {count} products")
        if len(price_groups) > 5:
            self.stdout.write(f"   ... and {len(price_groups) - 5} more groups")
        
        # Dry run mode
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  DRY RUN MODE - No prices will be changed"
            ))
            self.stdout.write(f"   Would update {total_duplicates} products")
            return
        
        # Confirmation
        if not force:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  This will change prices for {total_duplicates} products!"
            ))
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        # Fix duplicate prices
        self.stdout.write(f"\n💰 Fixing duplicate prices...")
        
        updated_count = 0
        with transaction.atomic():
            for group in price_groups:
                price = group['price']
                products = Product.objects.filter(
                    status='active',
                    price=price
                )
                
                # Keep first product with original price, change others
                products_list = list(products)
                for product in products_list[1:]:  # Skip first one
                    # Generate new random price
                    new_price = self._generate_realistic_price()
                    old_price = product.price
                    product.price = new_price
                    product.save(update_fields=['price'])
                    updated_count += 1
                    
                    if updated_count % 10 == 0:
                        self.stdout.write(f"   Updated {updated_count}/{total_duplicates}...", ending='\r')
        
        self.stdout.write(f"\r   ✓ Updated {updated_count} products with new random prices")
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully fixed {updated_count} duplicate prices!"
        ))

    def _generate_realistic_price(self):
        """Generate realistic random price"""
        rand = random.random()
        
        if rand < 0.5:  # 50% - Budget: $9.99 - $49.99
            price = round(random.uniform(9.99, 49.99), 2)
        elif rand < 0.8:  # 30% - Mid-range: $50 - $199.99
            price = round(random.uniform(50.00, 199.99), 2)
        elif rand < 0.95:  # 15% - Premium: $200 - $499.99
            price = round(random.uniform(200.00, 499.99), 2)
        else:  # 5% - Luxury: $500 - $999.99
            price = round(random.uniform(500.00, 999.99), 2)
        
        return Decimal(str(price))

