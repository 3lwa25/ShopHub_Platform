"""
Clean and Fix Products Command
Downloads real images from URLs, fixes prices, and improves product data quality
"""
import os
import re
import gzip
import json
import time
import requests
from pathlib import Path
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from PIL import Image

from apps.products.models import Product, ProductImage, Category

# User-Agent for image downloads
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


class Command(BaseCommand):
    help = "Clean and fix imported products: download real images, fix prices, improve data quality"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset-path',
            type=str,
            default=None,
            help='Path to the dataset root directory (for re-reading prices)'
        )
        parser.add_argument(
            '--fix-images',
            action='store_true',
            default=True,
            help='Download and set product images from URLs (default: True)'
        )
        parser.add_argument(
            '--fix-prices',
            action='store_true',
            help='Re-read prices from dataset files'
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=0,
            help='Maximum products to process (0 = all)'
        )
        parser.add_argument(
            '--skip-existing-images',
            action='store_true',
            help='Skip products that already have images'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Timeout for image downloads in seconds (default: 10)'
        )

    def handle(self, *args, **options):
        import time
        self.start_time = time.time()
        
        self.dataset_path = Path(options['dataset_path']) if options['dataset_path'] else None
        self.fix_images = options.get('fix_images', True)
        self.fix_prices = options.get('fix_prices', False)
        self.max_products = options['max_products']
        self.skip_existing = options['skip_existing_images']
        self.timeout = options['timeout']
        
        # Statistics
        self.stats = {
            'products_processed': 0,
            'images_downloaded': 0,
            'images_failed': 0,
            'prices_fixed': 0,
            'prices_failed': 0,
            'errors': 0,
        }
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Product Cleanup & Fix Command\n"
            f"{'='*70}\n"
        ))
        self.stdout.write(f"📊 Configuration:")
        self.stdout.write(f"   • Fix images: {'YES' if self.fix_images else 'NO'}")
        self.stdout.write(f"   • Fix prices: {'YES' if self.fix_prices else 'NO'}")
        self.stdout.write(f"   • Max products: {self.max_products if self.max_products > 0 else 'ALL'}")
        self.stdout.write(f"   • Skip existing images: {'YES' if self.skip_existing else 'NO'}")
        self.stdout.write("")
        
        # Get products to process
        products = Product.objects.filter(status='active')
        if self.max_products > 0:
            products = products[:self.max_products]
        
        total = products.count()
        self.stdout.write(f"📦 Found {total} products to process\n")
        
        if total == 0:
            self.stdout.write(self.style.WARNING("No products found to process!"))
            return
        
        # Process each product
        for idx, product in enumerate(products, 1):
            try:
                self._process_product(product, idx, total)
            except Exception as e:
                self.stats['errors'] += 1
                self.stdout.write(self.style.ERROR(f"\n  ✗ Error processing {product.sku}: {str(e)}"))
        
        # Print summary
        self._print_summary()

    def _process_product(self, product, idx, total):
        """Process a single product"""
        self.stdout.write(f"\n[{idx}/{total}] Processing: {product.title[:60]}...")
        
        # Check if product already has images
        if self.skip_existing and product.images.exists():
            self.stdout.write(f"  ⏭️  Skipping (already has images)")
            return
        
        # Fix images
        if self.fix_images:
            self._download_product_images(product)
        
        # Fix prices
        if self.fix_prices and self.dataset_path:
            self._fix_product_price(product)
        
        self.stats['products_processed'] += 1

    def _download_product_images(self, product):
        """Download images from URLs in product attributes"""
        attributes = product.attributes or {}
        primary_url = attributes.get('primary_image_url')
        image_urls = attributes.get('image_urls', [])
        
        if not primary_url and not image_urls:
            self.stdout.write(f"  ⚠️  No image URLs found in attributes")
            return
        
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
            self.stdout.write(f"  ⚠️  No valid image URLs found")
            return
        
        downloaded = 0
        failed = 0
        
        for idx, url in enumerate(urls_to_download):
            try:
                if self._download_and_save_image(product, url, is_primary=(idx == 0)):
                    downloaded += 1
                    self.stdout.write(f"  ✓ Downloaded image {idx + 1}/{len(urls_to_download)}")
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                if failed <= 3:  # Only show first few failures
                    self.stdout.write(f"  ✗ Failed to download image: {str(e)[:80]}")
        
        self.stats['images_downloaded'] += downloaded
        self.stats['images_failed'] += failed
        
        if downloaded > 0:
            self.stdout.write(f"  ✅ {downloaded} image(s) saved successfully")
        if failed > 0:
            self.stdout.write(f"  ⚠️  {failed} image(s) failed to download")

    def _download_and_save_image(self, product, url, is_primary=False):
        """Download a single image from URL and save as ProductImage"""
        if not url or not url.startswith('http'):
            return False
        
        try:
            # Download image
            response = requests.get(url, headers=HEADERS, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return False
            
            # Read image data
            image_data = BytesIO(response.content)
            
            # Verify it's a valid image
            try:
                img = Image.open(image_data)
                img.verify()  # Verify it's a valid image
            except Exception:
                return False
            
            # Reset stream
            image_data.seek(0)
            
            # Generate filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                # Generate filename from product SKU
                ext = 'jpg'  # Default extension
                # Try to detect format from content
                try:
                    img_format = Image.open(image_data).format.lower()
                    ext = img_format if img_format in ['jpg', 'jpeg', 'png', 'webp'] else 'jpg'
                    image_data.seek(0)
                except:
                    pass
                filename = f"{product.sku}_{int(time.time())}.{ext}"
            else:
                # Clean filename
                filename = re.sub(r'[^\w\-_\.]', '_', filename)
                if len(filename) > 100:
                    name, ext = os.path.splitext(filename)
                    filename = name[:90] + ext
            
            # Create ProductImage
            with transaction.atomic():
                # Check if primary image already exists
                if is_primary:
                    ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
                
                product_image = ProductImage.objects.create(
                    product=product,
                    image=ContentFile(image_data.read(), name=filename),
                    alt_text=f"{product.title} - Product Image",
                    is_primary=is_primary,
                    display_order=0 if is_primary else product.images.count()
                )
            
            return True
            
        except requests.RequestException as e:
            return False
        except Exception as e:
            return False

    def _fix_product_price(self, product):
        """Re-read price from dataset file"""
        if not self.dataset_path or not self.dataset_path.exists():
            return
        
        # Find the category folder
        category_name = product.category.name if product.category else None
        if not category_name:
            return
        
        # Try to find category folder (handle different naming)
        category_folders = [f for f in self.dataset_path.iterdir() if f.is_dir()]
        category_folder = None
        
        for folder in category_folders:
            folder_name = folder.name.replace('_', ' ').title()
            if category_name.lower() in folder_name.lower() or folder_name.lower() in category_name.lower():
                category_folder = folder
                break
        
        if not category_folder:
            return
        
        # Find meta file
        meta_files = list(category_folder.glob('meta_*.json*'))
        if not meta_files:
            return
        
        meta_file = meta_files[0]
        
        # Search for product in meta file
        try:
            if meta_file.suffix == '.gz':
                file_handle = gzip.open(meta_file, 'rt', encoding='utf-8', errors='ignore')
            else:
                file_handle = open(meta_file, 'r', encoding='utf-8', errors='ignore')
            
            with file_handle as fh:
                for line in fh:
                    try:
                        data = json.loads(line.strip())
                        asin = (data.get('asin') or data.get('parent_asin') or '').strip()
                        
                        if asin == product.sku:
                            # Found the product! Extract price
                            new_price = self._extract_price_from_data(data)
                            if new_price and new_price > Decimal('0.01'):
                                old_price = product.price
                                product.price = new_price
                                product.save(update_fields=['price'])
                                self.stats['prices_fixed'] += 1
                                self.stdout.write(f"  💰 Price updated: ${old_price} → ${new_price}")
                            else:
                                self.stats['prices_failed'] += 1
                            return
                    except (json.JSONDecodeError, Exception):
                        continue
        except Exception as e:
            self.stats['prices_failed'] += 1
            return

    def _extract_price_from_data(self, data):
        """Extract price from dataset entry"""
        price_fields = ['price', 'list_price', 'original_price', 'retail_price', 'sale_price']
        
        for field in price_fields:
            price_val = data.get(field)
            if price_val:
                if isinstance(price_val, (int, float)):
                    if price_val > 0:
                        return Decimal(str(price_val))
                
                if isinstance(price_val, str):
                    cleaned = price_val.replace('$', '').replace(',', '').replace('USD', '').replace('EGP', '').strip()
                    if cleaned:
                        try:
                            price_decimal = Decimal(cleaned)
                            if price_decimal > 0:
                                return price_decimal
                        except (InvalidOperation, ValueError):
                            continue
        
        return None

    def _print_summary(self):
        """Print cleanup summary"""
        import time
        total_time = time.time() - self.start_time
        
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("  ✅ Cleanup Complete!"))
        self.stdout.write("="*70)
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"  • Products processed: {self.stats['products_processed']}")
        self.stdout.write(f"  • Images downloaded: {self.stats['images_downloaded']}")
        self.stdout.write(f"  • Images failed: {self.stats['images_failed']}")
        self.stdout.write(f"  • Prices fixed: {self.stats['prices_fixed']}")
        self.stdout.write(f"  • Prices failed: {self.stats['prices_failed']}")
        self.stdout.write(f"  • Errors: {self.stats['errors']}")
        self.stdout.write(f"  • Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        
        if self.stats['products_processed'] > 0:
            avg_time = total_time / self.stats['products_processed']
            self.stdout.write(f"  • Average: {avg_time:.2f}s per product")
        
        self.stdout.write("\n" + "="*70 + "\n")
        
        if self.stats['images_downloaded'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Successfully downloaded {self.stats['images_downloaded']} product images!\n"
                "   Images are now stored locally and ready for use.\n"
            ))
        
        if self.stats['prices_fixed'] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Fixed {self.stats['prices_fixed']} product prices!\n"
            ))

