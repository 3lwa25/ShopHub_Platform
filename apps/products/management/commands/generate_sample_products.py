"""
Management command to generate sample products for testing
"""
from django.core.management.base import BaseCommand
from apps.products.models import Category, Product
from apps.accounts.models import SellerProfile, User
from django.utils.text import slugify
import random


class Command(BaseCommand):
    help = 'Generate sample products for testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of products to create'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        
        # Get or create a seller
        seller_user = User.objects.filter(role='seller').first()
        if not seller_user:
            seller_user = User.objects.create_user(
                email='seller@shophub.com',
                username='sample_seller',
                password='SamplePass123',
                role='seller',
                full_name='Sample Seller'
            )
            self.stdout.write(self.style.SUCCESS(f'Created seller user: {seller_user.email}'))
        
        seller_profile = SellerProfile.objects.filter(user=seller_user).first()
        if not seller_profile:
            seller_profile = SellerProfile.objects.create(
                user=seller_user,
                business_name='Sample Shop',
                country='Egypt'
            )
        
        # Create categories
        categories = [
            'Electronics',
            'Clothing',
            'Books',
            'Home & Garden',
            'Sports',
            'Toys',
            'Beauty',
            'Food'
        ]
        
        category_objects = []
        for cat_name in categories:
            cat, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name)}
            )
            category_objects.append(cat)
            if created:
                self.stdout.write(f'Created category: {cat_name}')
        
        # Generate sample products
        product_templates = [
            'Premium {}',
            'Professional {}',
            'Luxury {}',
            'Classic {}',
            'Modern {}',
            'Vintage {}',
            'Essential {}',
            'Ultimate {}'
        ]
        
        product_types = [
            'Widget',
            'Gadget',
            'Device',
            'Tool',
            'Accessory',
            'Equipment',
            'Kit',
            'Set'
        ]
        
        created_count = 0
        for i in range(count):
            template = random.choice(product_templates)
            product_type = random.choice(product_types)
            title = template.format(product_type)
            
            # Generate unique slug
            slug = slugify(title)
            if Product.objects.filter(slug=slug).exists():
                slug = f"{slug}-{i}"
            
            # Generate unique SKU
            sku = f"PROD-{random.randint(10000, 99999)}"
            while Product.objects.filter(sku=sku).exists():
                sku = f"PROD-{random.randint(10000, 99999)}"
            
            price = round(random.uniform(10, 1000), 2)
            compare_price = round(price * random.uniform(1.1, 1.5), 2) if random.random() > 0.5 else None
            stock = random.randint(0, 100)
            rating = round(random.uniform(3.0, 5.0), 2)
            review_count = random.randint(0, 100)
            
            product = Product.objects.create(
                seller=seller_profile,
                category=random.choice(category_objects),
                title=title,
                slug=slug,
                sku=sku,
                description=f'This is a sample product: {title}. Perfect for testing and development purposes.',
                price=price,
                compare_at_price=compare_price,
                stock=stock,
                status='active',
                rating=rating,
                review_count=review_count,
                is_featured=random.random() > 0.8,
                vto_enabled=random.random() > 0.7,
                attributes={'color': random.choice(['Red', 'Blue', 'Green', 'Black', 'White'])}
            )
            
            created_count += 1
            
            if created_count % 10 == 0:
                self.stdout.write(f'Created {created_count} products...')
        
        self.stdout.write(self.style.SUCCESS(
            f'✓ Successfully created {created_count} sample products!'
        ))

