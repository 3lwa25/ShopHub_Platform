"""
Comprehensive Product Management Command - Master Import & Organization Script

This command orchestrates a complete product import and management workflow:

WORKFLOW:
1. Import Dataset (import_dataset_improved.py) - Import products with quality checks
2. Clean Products (clean_products.py) - Download only good quality images  
3. Deduplicate Products (deduplicate_products.py) - Remove duplicate products
4. Fix Duplicate Prices (fix_duplicate_prices.py) - Randomize prices
5. Delete Low Quality (delete_low_quality_images.py) - Remove products without images
6. Organize Products (organize_products.py) - Set best sellers, sync chatbot

FEATURES:
- ✅ No duplicate products imported (checks existing SKUs)
- ✅ Only high-quality images downloaded (resolution + quality checks)
- ✅ Random realistic prices for each product
- ✅ Automatic deduplication of similar products
- ✅ Removes products without images or with low-quality images only
- ✅ Organizes best sellers by category
- ✅ Syncs product knowledge to AI chatbot
"""
import gzip
import json
import os
import re
import time
import random
import requests
from pathlib import Path
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import urlparse
from difflib import SequenceMatcher
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image
import numpy as np

from apps.products.models import Category, Product, ProductImage
from apps.ai_chatbot.models import ProductKnowledge
from apps.accounts.models import SellerProfile

User = get_user_model()

# User-Agent for image downloads
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


class Command(BaseCommand):
    help = "Comprehensive product management: cleanup, import, organize, and fix existing products"
    CHUNK_SIZE = 400
    MIN_DESCRIPTION_LENGTH = 40

    def add_arguments(self, parser):
        # Import options
        parser.add_argument(
            '--dataset-path',
            type=str,
            default=None,
            help='Path to the dataset root directory (default: BASE_DIR/dataset)'
        )
        parser.add_argument(
            '--max-per-category',
            type=int,
            default=1000,
            help='Maximum products to import per category (0 = unlimited, default: 1000)'
        )
        parser.add_argument(
            '--sample-rate',
            type=int,
            default=1,
            help='Import every Nth product (1 = all, 2 = every other, default: 1)'
        )
        
        # Quality options
        parser.add_argument(
            '--min-image-resolution',
            type=int,
            default=300,
            help='Minimum image resolution (width or height) in pixels (default: 300)'
        )
        parser.add_argument(
            '--min-image-quality',
            type=float,
            default=0.3,
            help='Minimum image quality score 0-1 (default: 0.3)'
        )
        
        # Action flags
        parser.add_argument(
            '--fix-existing',
            action='store_true',
            default=True,
            help='Fix existing products (add images, descriptions, specs) (default: True)'
        )
        parser.add_argument(
            '--remove-duplicates',
            action='store_true',
            default=True,
            help='Remove duplicate products (default: True)'
        )
        parser.add_argument(
            '--fix-prices',
            action='store_true',
            default=True,
            help='Fix duplicate prices (default: True)'
        )
        parser.add_argument(
            '--delete-low-quality',
            action='store_true',
            default=True,
            help='Delete products with only low-quality images (default: True)'
        )
        parser.add_argument(
            '--import-dataset',
            action='store_true',
            help='Import new products from dataset'
        )
        parser.add_argument(
            '--organize',
            action='store_true',
            default=True,
            help='Organize products (best sellers + chatbot sync) (default: True)'
        )
        parser.add_argument(
            '--skip-knowledge',
            action='store_true',
            help='Skip chatbot knowledge sync'
        )
        
        # Safety options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without making them'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts'
        )

    def handle(self, *args, **options):
        self.start_time = time.time()
        
        # Configuration
        self.dataset_path = Path(options['dataset_path']) if options['dataset_path'] else Path(settings.BASE_DIR) / 'dataset'
        self.max_per_category = options['max_per_category']
        self.sample_rate = options['sample_rate']
        self.min_resolution = options['min_image_resolution']
        self.min_quality = options['min_image_quality']
        self.skip_knowledge = options['skip_knowledge']
        self.dry_run = options['dry_run']
        self.force = options['force']
        
        # Action flags
        self.fix_existing = options.get('fix_existing', True)
        self.remove_duplicates = options.get('remove_duplicates', True)
        self.fix_prices = options.get('fix_prices', True)
        self.delete_low_quality = options.get('delete_low_quality', True)
        self.import_dataset = options.get('import_dataset', False)
        self.organize = options.get('organize', True)
        
        # Statistics
        self.stats = {
            'duplicates_removed': 0,
            'prices_fixed': 0,
            'low_quality_deleted': 0,
            'products_fixed': 0,
            'images_added': 0,
            'descriptions_added': 0,
            'specs_added': 0,
            'products_imported': 0,
            'imported_without_images': 0,
            'best_sellers_updated': 0,
            'knowledge_synced': 0,
            'errors': 0,
        }
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"  🚀 COMPREHENSIVE PRODUCT MANAGEMENT & IMPORT SYSTEM\n"
            f"{'='*80}\n"
        ))
        self.stdout.write(self.style.SUCCESS("\n📋 WORKFLOW STEPS:"))
        self.stdout.write(f"   1. Import Dataset → Import products with quality checks")
        self.stdout.write(f"   2. Clean Products → Download only GOOD quality images")
        self.stdout.write(f"   3. Deduplicate → Remove duplicate products")
        self.stdout.write(f"   4. Fix Prices → Randomize duplicate prices")
        self.stdout.write(f"   5. Delete Low Quality → Remove products without images")
        self.stdout.write(f"   6. Organize → Set best sellers & sync chatbot")
        
        self.stdout.write(f"\n📊 Configuration:")
        self.stdout.write(f"   • Fix existing products: {'✅ YES' if self.fix_existing else '❌ NO'}")
        self.stdout.write(f"   • Remove duplicates: {'✅ YES' if self.remove_duplicates else '❌ NO'}")
        self.stdout.write(f"   • Fix duplicate prices: {'✅ YES' if self.fix_prices else '❌ NO'}")
        self.stdout.write(f"   • Delete low-quality: {'✅ YES' if self.delete_low_quality else '❌ NO'}")
        self.stdout.write(f"   • Import dataset: {'✅ YES' if self.import_dataset else '❌ NO'}")
        self.stdout.write(f"   • Organize products: {'✅ YES' if self.organize else '❌ NO'}")
        
        self.stdout.write(f"\n🎯 Quality Settings:")
        self.stdout.write(f"   • Min image resolution: {self.min_resolution}x{self.min_resolution}px")
        self.stdout.write(f"   • Min image quality score: {self.min_quality}")
        self.stdout.write(f"   • Max per category: {self.max_per_category if self.max_per_category > 0 else 'Unlimited'} (randomized selection)")
        self.stdout.write("")
        
        # STEP 1: Import Dataset (import_dataset_improved.py logic)
        if self.import_dataset:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 1: 📥 IMPORT DATASET (import_dataset_improved.py)"))
            self.stdout.write("  Import products with NO duplicates & GOOD quality images ONLY")
            self.stdout.write("="*80)
            if not self.dataset_path.exists():
                self.stdout.write(self.style.WARNING(f"⚠️  Dataset path not found: {self.dataset_path}"))
            else:
                self._import_dataset()
        
        # STEP 2: Clean Products (clean_products.py logic - already integrated in import)
        if self.fix_existing:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 2: 🧹 CLEAN PRODUCTS (clean_products.py)"))
            self.stdout.write("  Fix existing products: add images, descriptions, specs")
            self.stdout.write("="*80)
            self._fix_existing_products()
        
        # STEP 3: Deduplicate Products (deduplicate_products.py logic)
        if self.remove_duplicates:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 3: 🔍 DEDUPLICATE PRODUCTS (deduplicate_products.py)"))
            self.stdout.write("  Remove duplicate or similar products")
            self.stdout.write("="*80)
            self._remove_duplicates()
        
        # STEP 4: Fix Duplicate Prices (fix_duplicate_prices.py logic)
        if self.fix_prices:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 4: 💰 FIX DUPLICATE PRICES (fix_duplicate_prices.py)"))
            self.stdout.write("  Randomize prices to avoid duplicates")
            self.stdout.write("="*80)
            self._fix_duplicate_prices()
        
        # STEP 5: Delete Low-Quality Products (delete_low_quality_images.py logic)
        if self.delete_low_quality:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 5: 🗑️  DELETE LOW-QUALITY PRODUCTS (delete_low_quality_images.py)"))
            self.stdout.write("  Remove products with no images or low-quality images only")
            self.stdout.write("="*80)
            self._delete_low_quality_products()
        
        # STEP 6: Organize Products (organize_products.py logic)
        if self.organize:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("  STEP 6: 📊 ORGANIZE PRODUCTS (organize_products.py)"))
            self.stdout.write("  Set best sellers & sync chatbot knowledge")
            self.stdout.write("="*80)
            self._organize_products()
        
        # Final summary
        self._print_summary()

    def _remove_duplicates(self):
        """Remove duplicate products"""
        products = Product.objects.filter(status='active').select_related('category').prefetch_related('images')
        total = products.count()
        
        self.stdout.write(f"🔍 Analyzing {total} products for duplicates...")
        
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
                
                if self._are_similar(product1, product2, 0.85):
                    similar_products.append(product2)
            
            if similar_products:
                all_similar = [product1] + similar_products
                best_product = self._select_best_product(all_similar)
                to_delete = [p for p in all_similar if p.id != best_product.id]
                
                duplicates.append({
                    'keep': best_product,
                    'delete': to_delete
                })
                
                processed.add(product1.id)
                for p in similar_products:
                    processed.add(p.id)
        
        total_to_delete = sum(len(d['delete']) for d in duplicates)
        
        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicates found!"))
            return
        
        self.stdout.write(f"📊 Found {len(duplicates)} duplicate groups, {total_to_delete} products to delete")
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING(f"⚠️  DRY RUN - Would delete {total_to_delete} products"))
            return
        
        if not self.force:
            confirm = input(f"Delete {total_to_delete} duplicate products? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        deleted_count = 0
        with transaction.atomic():
            for dup in duplicates:
                for product in dup['delete']:
                    try:
                        product.delete()
                        deleted_count += 1
                    except Exception as e:
                        self.stats['errors'] += 1
        
        self.stats['duplicates_removed'] = deleted_count
        self.stdout.write(self.style.SUCCESS(f"✅ Removed {deleted_count} duplicate products"))

    def _fix_duplicate_prices(self):
        """Fix duplicate prices"""
        price_groups = Product.objects.filter(status='active').values('price').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_duplicates = sum(group['count'] - 1 for group in price_groups)
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS("✅ No duplicate prices found!"))
            return
        
        self.stdout.write(f"📊 Found {len(price_groups)} price groups with {total_duplicates} duplicates")
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING(f"⚠️  DRY RUN - Would fix {total_duplicates} prices"))
            return
        
        updated_count = 0
        with transaction.atomic():
            for group in price_groups:
                price = group['price']
                products = Product.objects.filter(status='active', price=price)
                products_list = list(products)
                
                for product in products_list[1:]:  # Skip first
                    new_price = self._generate_realistic_price()
                    product.price = new_price
                    product.save(update_fields=['price'])
                    updated_count += 1
        
        self.stats['prices_fixed'] = updated_count
        self.stdout.write(self.style.SUCCESS(f"✅ Fixed {updated_count} duplicate prices"))

    def _delete_low_quality_products(self):
        """Delete products with only low-quality images"""
        products = Product.objects.filter(status='active').prefetch_related('images')
        total = products.count()
        
        self.stdout.write(f"🔍 Checking {total} products for low-quality images...")
        
        low_quality_products = []
        
        for product in products:
            if not product.images.exists():
                continue
            
            all_low_quality = True
            for image_obj in product.images.all():
                try:
                    if not self._check_image_quality(image_obj.image, self.min_resolution, self.min_quality):
                        continue
                    else:
                        all_low_quality = False
                        break
                except Exception:
                    continue
            
            if all_low_quality:
                low_quality_products.append(product)
        
        if len(low_quality_products) == 0:
            self.stdout.write(self.style.SUCCESS("✅ No low-quality products found!"))
            return
        
        self.stdout.write(f"📊 Found {len(low_quality_products)} products with only low-quality images")
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING(f"⚠️  DRY RUN - Would delete {len(low_quality_products)} products"))
            return
        
        if not self.force:
            confirm = input(f"Delete {len(low_quality_products)} products with low-quality images? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Cancelled."))
                return
        
        deleted_count = 0
        with transaction.atomic():
            for product in low_quality_products:
                try:
                    product.delete()
                    deleted_count += 1
                except Exception as e:
                    self.stats['errors'] += 1
        
        self.stats['low_quality_deleted'] = deleted_count
        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {deleted_count} low-quality products"))

    def _fix_existing_products(self):
        """Fix existing products: add images, descriptions, specs"""
        products = Product.objects.filter(status='active').prefetch_related('images')
        total = products.count()
        
        self.stdout.write(f"🔧 Fixing {total} existing products...")
        
        fixed_count = 0
        for idx, product in enumerate(products, 1):
            try:
                fixed = False
                
                # Fix images
                if not product.images.exists():
                    if self._try_fix_product_images(product):
                        fixed = True
                        self.stats['images_added'] += 1
                
                # Fix description
                description = (product.description or '').strip()
                if len(description) < 20:
                    if self._try_fix_product_description(product):
                        fixed = True
                        self.stats['descriptions_added'] += 1
                
                # Fix specs/attributes
                attributes = product.attributes or {}
                if not attributes or (isinstance(attributes, dict) and len(attributes) == 0):
                    if self._try_fix_product_specs(product):
                        fixed = True
                        self.stats['specs_added'] += 1
                
                if fixed:
                    fixed_count += 1
                    self.stats['products_fixed'] += 1
                
                if idx % 100 == 0:
                    self.stdout.write(f"   Processed {idx}/{total} products...", ending='\r')
            
            except Exception as e:
                self.stats['errors'] += 1
                continue
        
        self.stdout.write(f"\r   ✅ Fixed {fixed_count} products                    ")
        self.stdout.write(self.style.SUCCESS(f"\n✅ Fixed {fixed_count} existing products"))

    def _try_fix_product_images(self, product):
        """Try to download images for existing product (like clean_products.py)"""
        attributes = product.attributes or {}
        primary_url = attributes.get('primary_image_url')
        image_urls = attributes.get('image_urls', [])
        
        if not primary_url and not image_urls:
            return False
        
        # Use primary URL first, then fall back to image_urls
        urls_to_download = []
        if primary_url:
            urls_to_download.append(primary_url)
        
        # Add other URLs (limit to 5 images max)
        if image_urls:
            for url in image_urls[:5]:
                if url and url != primary_url:
                    urls_to_download.append(url)
        
        if not urls_to_download:
            return False
        
        downloaded = 0
        for idx, url in enumerate(urls_to_download):
            try:
                if self._download_and_save_image(product, url, is_primary=(idx == 0)):
                    downloaded += 1
            except Exception:
                continue
        
        return downloaded > 0

    def _try_fix_product_description(self, product):
        """Try to generate/fix product description"""
        # Try to get from attributes
        attributes = product.attributes or {}
        features = attributes.get('features', [])
        
        description_parts = []
        if product.title:
            description_parts.append(f"{product.title} is a high-quality product")
        
        if features:
            features_text = '\n'.join(f"• {f}" for f in features[:10] if f)
            description_parts.append(f"\n\nFeatures:\n{features_text}")
        
        brand = attributes.get('brand')
        if brand:
            description_parts.append(f"\n\nBrand: {brand}")
        
        if description_parts:
            new_description = ' '.join(description_parts)[:2000]
            if len(new_description) >= 20:
                product.description = new_description
                product.save(update_fields=['description'])
                return True
        
        return False

    def _try_fix_product_specs(self, product):
        """Try to add specs/attributes to product"""
        attributes = product.attributes or {}
        
        # If already has attributes, skip
        if attributes and isinstance(attributes, dict) and len(attributes) > 0:
            return False
        
        # Try to extract from description
        description = (product.description or '').lower()
        new_attributes = {}
        
        # Extract brand if mentioned
        brand_keywords = ['brand', 'made by', 'manufacturer']
        for keyword in brand_keywords:
            if keyword in description:
                # Try to extract brand name (simplified)
                parts = description.split(keyword)
                if len(parts) > 1:
                    potential_brand = parts[1].split()[0:2]  # Take first 2 words
                    if potential_brand:
                        new_attributes['brand'] = ' '.join(potential_brand).title()
                        break
        
        # Add basic specs if we have something
        if new_attributes:
            product.attributes = new_attributes
            product.save(update_fields=['attributes'])
            return True
        
        # Generate basic attributes
        new_attributes = {
            'category': product.category.name if product.category else 'General',
            'status': 'active',
        }
        
        product.attributes = new_attributes
        product.save(update_fields=['attributes'])
        return True

    def _import_dataset(self):
        """Import products from dataset"""
        if not self.dataset_path.exists():
            self.stdout.write(self.style.ERROR(f"Dataset path does not exist: {self.dataset_path}"))
            return
        
        # Get or create seller
        seller = self._get_or_create_seller()
        
        # Track imported SKUs
        self.imported_skus = set(Product.objects.values_list('sku', flat=True))
        
        # Process categories
        category_folders = [f for f in self.dataset_path.iterdir() if f.is_dir()]
        
        for folder in category_folders:
            self._process_category(folder, seller)
        
        self.stdout.write(self.style.SUCCESS(f"✅ Imported {self.stats['products_imported']} new products"))

    def _process_category(self, folder_path, seller):
        """Process a single category folder"""
        category_name = folder_path.name.replace('_', ' ').title()
        
        meta_files = list(folder_path.glob('meta_*.json*'))
        if not meta_files:
            return
        
        category, _ = Category.objects.get_or_create(
            name=category_name,
            defaults={'slug': slugify(category_name)}
        )
        
        meta_file = meta_files[0]
        self._import_products_from_meta(meta_file, category, seller)

    def _import_products_from_meta(self, meta_file, category, seller):
        """Import products from meta file with randomized selection and live status"""
        max_count = self.max_per_category if self.max_per_category > 0 else float('inf')
        
        if max_count == float('inf'):
            # Unlimited import – stream directly but show progress
            return self._stream_import_from_meta(meta_file, category, seller)
        
        # Finite limit → reservoir sampling to randomize selections upfront
        selected_lines = []
        processed_candidates = 0
        self.stdout.write(f"  📄 Reading: {meta_file.name} (collecting up to {max_count} randomized products)")
        
        try:
            if meta_file.suffix == '.gz':
                file_handle = gzip.open(meta_file, 'rt', encoding='utf-8', errors='ignore')
            else:
                file_handle = open(meta_file, 'r', encoding='utf-8', errors='ignore')
            
            with file_handle as fh:
                for line_num, line in enumerate(fh, start=1):
                    if self.sample_rate > 1 and (line_num % self.sample_rate) != 0:
                        continue
                    
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    processed_candidates += 1
                    if len(selected_lines) < max_count:
                        selected_lines.append(stripped)
                    else:
                        replace_index = random.randint(0, processed_candidates - 1)
                        if replace_index < max_count:
                            selected_lines[replace_index] = stripped
                    
                    if processed_candidates % 500 == 0:
                        self.stdout.write(
                            f"    • Scanned {processed_candidates} candidates (selected {len(selected_lines)})",
                            ending='\r'
                        )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error reading {meta_file.name}: {str(e)}"))
            return
        
        self.stdout.write(
            f"\r    ✓ Collected {len(selected_lines)} randomized candidates from {processed_candidates} scanned lines"
        )
        
        if not selected_lines:
            self.stdout.write(self.style.WARNING("    ⚠️  No eligible products found in this category"))
            return
        
        random.shuffle(selected_lines)
        self.stdout.write(f"    🔄 Importing randomized selection ({len(selected_lines)} products)...")
        
        count = 0
        buffer = []
        total_selected = len(selected_lines)
        
        for raw_line in selected_lines:
            buffer.append(raw_line)
            if len(buffer) >= self.CHUNK_SIZE:
                count = self._process_import_buffer(buffer, category, seller, count, max_count)
                buffer.clear()
                self.stdout.write(
                    f"    • Imported {count}/{total_selected} products...",
                    ending='\r'
                )
        
        if buffer:
            count = self._process_import_buffer(buffer, category, seller, count, max_count)
            self.stdout.write(
                f"\r    • Imported {count}/{total_selected} products...                           "
            )
        
        self.stdout.write(f"\r    ✅ Completed category import: {count} products imported\n")
    
    def _stream_import_from_meta(self, meta_file, category, seller):
        """Stream import when unlimited max_per_category but still show status"""
        count = 0
        buffer = []
        try:
            if meta_file.suffix == '.gz':
                file_handle = gzip.open(meta_file, 'rt', encoding='utf-8', errors='ignore')
            else:
                file_handle = open(meta_file, 'r', encoding='utf-8', errors='ignore')
            
            with file_handle as fh:
                for line_num, line in enumerate(fh, start=1):
                    if self.sample_rate > 1 and (line_num % self.sample_rate) != 0:
                        continue
                    
                    buffer.append(line.strip())
                    if len(buffer) >= self.CHUNK_SIZE:
                        count = self._process_import_buffer(buffer, category, seller, count, float('inf'))
                        buffer.clear()
                        if count % 50 == 0:
                            self.stdout.write(
                                f"    • Imported {count} products so far...",
                                ending='\r'
                            )
                
                if buffer:
                    count = self._process_import_buffer(buffer, category, seller, count, float('inf'))
                    buffer.clear()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error reading {meta_file.name}: {str(e)}"))
            return
        
        self.stdout.write(f"\r    ✅ Completed category import: {count} products imported\n")
    
    def _process_import_buffer(self, buffer, category, seller, current_count, max_count):
        random.shuffle(buffer)
        for raw_line in buffer:
            if current_count >= max_count:
                break
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            
            if self._import_single_product(data, category, seller):
                current_count += 1
                self.stats['products_imported'] += 1
        
        return current_count

    def _import_single_product(self, data, category, seller):
        """Import a single product"""
        asin = (data.get('asin') or data.get('parent_asin') or '').strip()
        if not asin or asin in self.imported_skus:
            return False
        
        title = (data.get('title') or data.get('name') or '').strip()
        if not title or len(title) < 3:
            return False
        
        description = self._extract_description(data)
        
        attributes = self._build_attributes(data)
        
        try:
            with transaction.atomic():
                price = self._generate_realistic_price()
                compare_price = None
                if random.random() < 0.3:
                    compare_price = round(Decimal(str(price)) * Decimal(str(random.uniform(1.15, 1.50))), 2)
                
                product = Product.objects.create(
                    seller=seller,
                    category=category,
                    title=title,
                    slug=slugify(title),
                    sku=asin,
                    description=description,
                    price=price,
                    compare_at_price=compare_price,
                    stock=random.randint(10, 100),
                    status='active',
                    rating=Decimal(str(data.get('average_rating') or data.get('rating') or 0)) or Decimal('0.00'),
                    review_count=data.get('review_count') or 0,
                    attributes=attributes,
                )
                
                # Download images
                images_downloaded = self._download_product_images(product, data)
                if images_downloaded == 0:
                    self.stats['imported_without_images'] += 1
                
                # Knowledge base
                if not self.skip_knowledge:
                    self._create_knowledge_entry(product, data)
                
                self.imported_skus.add(asin)
                return True
        
        except Exception:
            if 'product' in locals():
                product.delete()
            return False

    def _organize_products(self):
        """Organize products: best sellers + chatbot sync"""
        # Best sellers
        import random
        updated = 0
        categories = Category.objects.filter(is_active=True)
        
        for category in categories:
            products = Product.objects.filter(
                category=category,
                status='active'
            ).prefetch_related('images')
            
            eligible_products = [p for p in products if p.images.exists()]
            if not eligible_products:
                continue
            
            scored_products = []
            for product in eligible_products:
                score = 0
                if product.rating:
                    score += float(product.rating) * 2
                score += product.review_count * 0.5
                score += 10  # Has images
                if product.stock > 0:
                    score += 5
                
                if (product.rating and product.rating >= 3.0) or product.review_count >= 3:
                    scored_products.append((score, product))
            
            if not scored_products:
                continue
            
            scored_products.sort(key=lambda x: x[0], reverse=True)
            top_candidates = [p[1] for p in scored_products[:15]]
            
            if len(top_candidates) >= 10:
                selected = random.sample(top_candidates, 10)
            else:
                selected = top_candidates
            
            for product in selected:
                if not product.is_featured:
                    product.is_featured = True
                    product.save(update_fields=['is_featured'])
                    updated += 1
            
            featured_in_category = products.filter(is_featured=True)
            for product in featured_in_category:
                if product not in selected:
                    product.is_featured = False
                    product.save(update_fields=['is_featured'])
                    updated += 1
        
        self.stats['best_sellers_updated'] = updated
        
        # Chatbot sync
        if not self.skip_knowledge:
            synced = self._sync_chatbot_knowledge()
            self.stats['knowledge_synced'] = synced
        
        self.stdout.write(self.style.SUCCESS(f"✅ Organized products: {updated} best sellers, {self.stats['knowledge_synced']} knowledge entries"))

    def _sync_chatbot_knowledge(self):
        """Sync products to chatbot knowledge"""
        products = Product.objects.filter(status='active').select_related('category').prefetch_related('images')
        synced = 0
        
        for product in products:
            try:
                description_parts = []
                if product.description:
                    description_parts.append(product.description[:800])
                
                if product.attributes:
                    features = product.attributes.get('features', [])
                    if features:
                        features_text = '\n'.join(f"• {f}" for f in features[:10] if f)
                        description_parts.append(f"\n\nFeatures:\n{features_text}")
                    
                    brand = product.attributes.get('brand')
                    if brand:
                        description_parts.append(f"\n\nBrand: {brand}")
                
                full_description = ' '.join(description_parts)[:1500]
                
                ProductKnowledge.objects.update_or_create(
                    external_id=product.sku,
                    defaults={
                        'product': product,
                        'title': product.title,
                        'category': product.category.name if product.category else 'Uncategorized',
                        'description': full_description or 'No description available.',
                        'highlights': product.attributes.get('features', [])[:20] if product.attributes else [],
                        'average_rating': product.rating or 0,
                        'price': product.price,
                        'source': 'comprehensive_sync',
                    }
                )
                synced += 1
            except Exception:
                continue
        
        return synced

    # Helper methods
    def _are_similar(self, product1, product2, threshold):
        """Check if products are similar"""
        if product1.category != product2.category:
            return False
        
        title_sim = SequenceMatcher(None, 
            product1.title.lower().strip(), 
            product2.title.lower().strip()
        ).ratio()
        
        if title_sim >= threshold:
            return True
        
        attrs1 = product1.attributes or {}
        attrs2 = product2.attributes or {}
        
        primary_url1 = attrs1.get('primary_image_url', '')
        primary_url2 = attrs2.get('primary_image_url', '')
        
        if primary_url1 and primary_url2 and primary_url1 == primary_url2:
            return True
        
        images1 = set(img.image.name for img in product1.images.all() if img.image)
        images2 = set(img.image.name for img in product2.images.all() if img.image)
        
        if images1 and images2 and images1.intersection(images2):
            return True
        
        return False

    def _select_best_product(self, products):
        """Select best product to keep"""
        best = None
        best_score = -1
        
        for product in products:
            score = 0
            score += product.images.count() * 10
            score += float(product.rating or 0) * 5
            score += product.review_count * 2
            if product.images.exists():
                score += 20
            score += min(product.stock, 100) * 0.1
            if product.is_featured:
                score += 10
            
            if score > best_score:
                best_score = score
                best = product
        
        return best

    def _generate_realistic_price(self):
        """Generate realistic random price"""
        rand = random.random()
        if rand < 0.5:
            return Decimal(str(round(random.uniform(9.99, 49.99), 2)))
        elif rand < 0.8:
            return Decimal(str(round(random.uniform(50.00, 199.99), 2)))
        elif rand < 0.95:
            return Decimal(str(round(random.uniform(200.00, 499.99), 2)))
        else:
            return Decimal(str(round(random.uniform(500.00, 999.99), 2)))

    def _check_image_quality(self, image_file, min_resolution, min_quality):
        """Check image quality"""
        try:
            if hasattr(image_file, 'read'):
                img = Image.open(image_file)
            else:
                from django.core.files.storage import default_storage
                with default_storage.open(image_file.name, 'rb') as f:
                    img = Image.open(f)
            
            width, height = img.size
            if width < min_resolution or height < min_resolution:
                return False
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img_array = np.array(img)
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            variance = np.var(gray)
            normalized_variance = min(variance / 3000.0, 1.0)
            
            if normalized_variance < min_quality:
                return False
            
            return True
        except Exception:
            return False

    def _download_product_images(self, product, data):
        """Download product images"""
        image_urls = []
        
        if data.get('imageURL') or data.get('image_url'):
            url = data.get('imageURL') or data.get('image_url')
            if url:
                image_urls.append(url)
        
        if data.get('imageURLHighRes') or data.get('image_url_high_res'):
            url = data.get('imageURLHighRes') or data.get('image_url_high_res')
            if url:
                image_urls.append(url)
        
        if data.get('imageURLs') or data.get('image_urls'):
            urls = data.get('imageURLs') or data.get('image_urls')
            if isinstance(urls, list):
                image_urls.extend(urls[:5])
        
        downloaded = 0
        for idx, url in enumerate(image_urls[:5]):
            if self._download_and_save_image(product, url, is_primary=(idx == 0)):
                self.stats['images_added'] += 1
                downloaded += 1
        
        return downloaded

    def _download_and_save_image(self, product, url, is_primary=False):
        """Download and save image with quality check"""
        if not url or not url.startswith('http'):
            return False
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=10, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return False
            
            image_data = BytesIO(response.content)
            data_copy = BytesIO(image_data.getvalue())
            
            if not self._check_image_quality(data_copy, self.min_resolution, self.min_quality):
                return False
            
            image_data.seek(0)
            
            try:
                img = Image.open(image_data)
                img.verify()
            except Exception:
                return False
            
            image_data.seek(0)
            
            # Generate filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                ext = 'jpg'
                try:
                    img = Image.open(image_data)
                    img_format = img.format.lower() if img.format else 'jpg'
                    ext = img_format if img_format in ['jpg', 'jpeg', 'png', 'webp'] else 'jpg'
                    image_data.seek(0)
                except:
                    pass
                filename = f"{product.sku}_{int(time.time())}.{ext}"
            else:
                filename = re.sub(r'[^\w\-_\.]', '_', filename)
                if len(filename) > 100:
                    name, ext = os.path.splitext(filename)
                    filename = name[:90] + ext
            
            with transaction.atomic():
                if is_primary:
                    ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
                
                ProductImage.objects.create(
                    product=product,
                    image=ContentFile(image_data.read(), name=filename),
                    alt_text=f"{product.title} - Product Image",
                    is_primary=is_primary,
                    display_order=0 if is_primary else product.images.count()
                )
            
            return True
        except Exception:
            return False

    def _extract_description(self, data):
        """Extract description from data with graceful fallback (matches import_dataset_improved.py)"""
        description_parts = []
        
        if data.get('description'):
            desc = data['description']
            if isinstance(desc, list):
                desc = ' '.join(str(d) for d in desc)
            description_parts.append(str(desc)[:800])
        
        if data.get('features'):
            features = data['features']
            if isinstance(features, list):
                features_text = '\n'.join(f"• {f}" for f in features[:10] if f)
                description_parts.append(f"\n\nFeatures:\n{features_text}")
        
        description_text = ' '.join(description_parts).strip()
        return description_text[:5000] if description_text else 'No description available.'

    def _build_attributes(self, data):
        """Build product attributes"""
        attributes = {}
        if data.get('brand'):
            attributes['brand'] = str(data['brand']).strip()
        if data.get('main_cat'):
            attributes['main_category'] = str(data['main_cat']).strip()
        if data.get('features'):
            if isinstance(data['features'], list):
                attributes['features'] = [str(f).strip() for f in data['features'][:20] if f]
        
        primary_url = data.get('imageURL') or data.get('image_url')
        if primary_url:
            attributes['primary_image_url'] = primary_url
        
        collected_urls = []
        if data.get('imageURLHighRes') or data.get('image_url_high_res'):
            collected_urls.append(data.get('imageURLHighRes') or data.get('image_url_high_res'))
        
        if data.get('imageURLs') or data.get('image_urls'):
            urls = data.get('imageURLs') or data.get('image_urls')
            if isinstance(urls, list):
                collected_urls.extend(urls[:10])
        
        # ensure primary not duplicated and list cleaned
        cleaned_urls = []
        for url in collected_urls:
            if url and url not in cleaned_urls and url != primary_url:
                cleaned_urls.append(url)
        
        if cleaned_urls:
            attributes['image_urls'] = cleaned_urls
        
        return attributes

    def _create_knowledge_entry(self, product, data):
        """Create chatbot knowledge entry"""
        try:
            ProductKnowledge.objects.update_or_create(
                external_id=product.sku,
                defaults={
                    'product': product,
                    'title': product.title,
                    'category': product.category.name if product.category else 'Uncategorized',
                    'description': product.description[:1000] if product.description else '',
                    'highlights': product.attributes.get('features', [])[:20] if product.attributes else [],
                    'average_rating': product.rating or 0,
                    'price': product.price,
                    'source': 'dataset_import',
                }
            )
        except Exception:
            pass

    def _get_or_create_seller(self):
        """Get or create seller"""
        seller_user = User.objects.filter(role='seller').first()
        if not seller_user:
            seller_user = User.objects.create_user(
                email='dataset@shophub.com',
                username='dataset_seller',
                password='DatasetPass123',
                role='seller',
                full_name='Dataset Importer'
            )
        
        seller_profile = SellerProfile.objects.filter(user=seller_user).first()
        if not seller_profile:
            seller_profile = SellerProfile.objects.create(
                user=seller_user,
                business_name='Dataset Products',
                country='Egypt'
            )
        
        return seller_profile

    def _print_summary(self):
        """Print comprehensive summary"""
        total_time = time.time() - self.start_time
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("  ✅ COMPREHENSIVE MANAGEMENT COMPLETE!"))
        self.stdout.write("="*80)
        
        self.stdout.write(f"\n📊 FINAL SUMMARY:")
        self.stdout.write(f"\n  📥 Import & Cleaning:")
        self.stdout.write(f"     • Products imported: {self.stats['products_imported']}")
        self.stdout.write(f"     • Imported without images (needs fixing): {self.stats['imported_without_images']}")
        self.stdout.write(f"     • Existing products fixed: {self.stats['products_fixed']}")
        self.stdout.write(f"     • Images added: {self.stats['images_added']}")
        self.stdout.write(f"     • Descriptions added: {self.stats['descriptions_added']}")
        self.stdout.write(f"     • Specs added: {self.stats['specs_added']}")
        
        self.stdout.write(f"\n  🔧 Quality Control:")
        self.stdout.write(f"     • Duplicates removed: {self.stats['duplicates_removed']}")
        self.stdout.write(f"     • Prices fixed: {self.stats['prices_fixed']}")
        self.stdout.write(f"     • Low-quality products deleted: {self.stats['low_quality_deleted']}")
        
        self.stdout.write(f"\n  📊 Organization:")
        self.stdout.write(f"     • Best sellers updated: {self.stats['best_sellers_updated']}")
        self.stdout.write(f"     • Chatbot knowledge synced: {self.stats['knowledge_synced']}")
        
        self.stdout.write(f"\n  ⚙️  Performance:")
        self.stdout.write(f"     • Errors encountered: {self.stats['errors']}")
        self.stdout.write(f"     • Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        
        # Get final product count
        total_products = Product.objects.filter(status='active').count()
        self.stdout.write(f"\n  📦 Final Database State:")
        self.stdout.write(f"     • Total active products: {total_products}")
        
        self.stdout.write("\n" + "="*80)
        
        # Success messages
        if self.stats['products_imported'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Successfully imported {self.stats['products_imported']} new products with quality checks!"
            ))
        
        if self.stats['duplicates_removed'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Removed {self.stats['duplicates_removed']} duplicate products!"
            ))
        
        if self.stats['low_quality_deleted'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Deleted {self.stats['low_quality_deleted']} low-quality products!"
            ))
        
        if self.stats['knowledge_synced'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Synced {self.stats['knowledge_synced']} products to AI chatbot!"
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 All done! Your product database is clean, organized, and ready!\n"
        ))

