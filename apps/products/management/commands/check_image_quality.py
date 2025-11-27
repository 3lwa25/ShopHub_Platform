"""
Check Image Quality and Remove Low-Quality Images
Detects pixelated/blurry images and removes products with only low-quality images
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.files.storage import default_storage
from PIL import Image
import numpy as np
from io import BytesIO
from apps.products.models import Product, ProductImage


class Command(BaseCommand):
    help = "Check image quality and remove products with only low-quality images"

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-resolution',
            type=int,
            default=300,
            help='Minimum resolution (width or height) in pixels (default: 300)'
        )
        parser.add_argument(
            '--min-quality-score',
            type=float,
            default=0.3,
            help='Minimum quality score 0-1 (default: 0.3)'
        )
        parser.add_argument(
            '--delete-products',
            action='store_true',
            help='Delete products with only low-quality images'
        )
        parser.add_argument(
            '--delete-images',
            action='store_true',
            help='Delete low-quality images (keep products)'
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
        delete_products = options['delete_products']
        delete_images = options['delete_images']
        min_resolution = options['min_resolution']
        min_quality = options['min_quality_score']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Image Quality Checker\n"
            f"{'='*70}\n"
        ))
        self.stdout.write(f"📊 Configuration:")
        self.stdout.write(f"   • Min resolution: {min_resolution}x{min_resolution}")
        self.stdout.write(f"   • Min quality score: {min_quality}")
        self.stdout.write(f"   • Delete products: {'YES' if delete_products else 'NO'}")
        self.stdout.write(f"   • Delete images: {'YES' if delete_images else 'NO'}")
        self.stdout.write("")
        
        # Get all products with images
        products = Product.objects.filter(status='active').prefetch_related('images')
        
        stats = {
            'products_checked': 0,
            'images_checked': 0,
            'low_quality_images': 0,
            'products_with_only_low_quality': [],
            'images_deleted': 0,
            'products_deleted': 0,
        }
        
        self.stdout.write(f"🔍 Checking {products.count()} products...\n")
        
        for product in products:
            if not product.images.exists():
                continue
            
            stats['products_checked'] += 1
            low_quality_count = 0
            total_images = product.images.count()
            
            for image_obj in product.images.all():
                stats['images_checked'] += 1
                
                try:
                    # Check image quality
                    is_low_quality = self._check_image_quality(
                        image_obj.image, 
                        min_resolution, 
                        min_quality
                    )
                    
                    if is_low_quality:
                        stats['low_quality_images'] += 1
                        low_quality_count += 1
                        
                        if delete_images and not dry_run:
                            try:
                                image_obj.delete()
                                stats['images_deleted'] += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(
                                    f"   ✗ Error deleting image {image_obj.id}: {str(e)}"
                                ))
                
                except Exception as e:
                    # If we can't check the image, consider it low quality
                    stats['low_quality_images'] += 1
                    low_quality_count += 1
            
            # If all images are low quality, mark product for deletion
            if low_quality_count == total_images and total_images > 0:
                stats['products_with_only_low_quality'].append(product)
            
            if stats['products_checked'] % 50 == 0:
                self.stdout.write(f"   Checked {stats['products_checked']} products...", ending='\r')
        
        self.stdout.write(f"\r   ✓ Checked {stats['products_checked']} products")
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("  📊 Quality Check Summary"))
        self.stdout.write("="*70)
        self.stdout.write(f"   • Products checked: {stats['products_checked']}")
        self.stdout.write(f"   • Images checked: {stats['images_checked']}")
        self.stdout.write(f"   • Low-quality images found: {stats['low_quality_images']}")
        self.stdout.write(f"   • Products with only low-quality images: {len(stats['products_with_only_low_quality'])}")
        
        if delete_images:
            self.stdout.write(f"   • Images deleted: {stats['images_deleted']}")
        
        # Show examples
        if stats['products_with_only_low_quality']:
            self.stdout.write(f"\n📋 Examples of products with only low-quality images:")
            for product in stats['products_with_only_low_quality'][:5]:
                self.stdout.write(f"   • {product.title[:60]} (SKU: {product.sku})")
            if len(stats['products_with_only_low_quality']) > 5:
                self.stdout.write(f"   ... and {len(stats['products_with_only_low_quality']) - 5} more")
        
        # Delete products if requested
        if delete_products and stats['products_with_only_low_quality']:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠️  DRY RUN MODE - Would delete {len(stats['products_with_only_low_quality'])} products"
                ))
            else:
                if not force:
                    self.stdout.write(self.style.WARNING(
                        f"\n⚠️  This will DELETE {len(stats['products_with_only_low_quality'])} products!"
                    ))
                    confirm = input("Type 'yes' to confirm: ")
                    if confirm.lower() != 'yes':
                        self.stdout.write(self.style.ERROR("Cancelled."))
                        return
                
                self.stdout.write(f"\n🗑️  Deleting {len(stats['products_with_only_low_quality'])} products...")
                
                with transaction.atomic():
                    for product in stats['products_with_only_low_quality']:
                        try:
                            product.delete()
                            stats['products_deleted'] += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(
                                f"   ✗ Error deleting {product.sku}: {str(e)}"
                            ))
                
                self.stdout.write(self.style.SUCCESS(
                    f"\n✅ Successfully deleted {stats['products_deleted']} products!"
                ))
        
        self.stdout.write("\n" + "="*70 + "\n")

    def _check_image_quality(self, image_file, min_resolution, min_quality):
        """
        Check if image is low quality (pixelated/blurry)
        Returns True if low quality, False if good quality
        """
        try:
            # Open image
            if hasattr(image_file, 'read'):
                img = Image.open(image_file)
            else:
                # If it's a file path
                with default_storage.open(image_file.name, 'rb') as f:
                    img = Image.open(f)
            
            # Check resolution
            width, height = img.size
            if width < min_resolution or height < min_resolution:
                return True  # Too small = low quality
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate quality score using Laplacian variance (blur detection)
            # Convert to numpy array
            img_array = np.array(img)
            
            # Calculate Laplacian variance (measure of sharpness)
            # Higher variance = sharper image
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            laplacian_var = np.var(np.array([
                [0, -1, 0],
                [-1, 4, -1],
                [0, -1, 0]
            ]))
            
            # Simple blur detection: check variance of image
            # Low variance = blurry/pixelated
            variance = np.var(gray)
            
            # Normalize variance (0-1 scale, approximate)
            # Typical good images have variance > 1000
            normalized_variance = min(variance / 3000.0, 1.0)
            
            # Check if quality is below threshold
            if normalized_variance < min_quality:
                return True  # Low quality
            
            # Additional check: very small file size might indicate compression artifacts
            try:
                if hasattr(image_file, 'size'):
                    file_size = image_file.size
                elif hasattr(image_file, 'name'):
                    file_size = default_storage.size(image_file.name)
                else:
                    file_size = len(image_data.getvalue()) if hasattr(image_data, 'getvalue') else 0
                
                # If image is very small (< 10KB), likely low quality
                if file_size < 10240:  # 10KB
                    return True
            except Exception:
                pass  # Skip file size check if we can't determine it
            
            return False  # Good quality
            
        except Exception as e:
            # If we can't check, assume low quality
            return True

