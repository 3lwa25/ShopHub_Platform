"""
Enable Virtual Try-On for products with good quality images
Only enables VTO for: accessories, eyewear, jewelry, hats
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.products.models import Product, Category
from apps.virtual_tryon.models import VTOAsset
from PIL import Image


class Command(BaseCommand):
    help = "Enable VTO for products with good images in eligible categories"
    
    # Map category names to VTO asset types
    # Expanded to support: Accessories, Clothing, Jewelry, Shoes, Home & Kitchen, Decorations, etc.
    CATEGORY_MAPPING = {
        # Eyewear
        'eyewear': 'glasses',
        'sunglasses': 'glasses',
        'glasses': 'glasses',
        'spectacles': 'glasses',
        'reading glasses': 'glasses',
        
        # Headwear
        'hats': 'hat',
        'caps': 'hat',
        'headwear': 'hat',
        'beanie': 'hat',
        'cap': 'hat',
        'helmet': 'hat',
        
        # Jewelry
        'jewelry': 'jewelry',
        'jewellery': 'jewelry',
        'earrings': 'jewelry',
        'necklaces': 'jewelry',
        'necklace': 'jewelry',
        'bracelet': 'jewelry',
        'bracelets': 'jewelry',
        'ring': 'jewelry',
        'rings': 'jewelry',
        'pendant': 'jewelry',
        'pendants': 'jewelry',
        'tiara': 'jewelry',
        'brooch': 'jewelry',
        
        # Accessories
        'accessories': 'accessory',
        'accessory': 'accessory',
        'hair clip': 'accessory',
        'hair clips': 'accessory',
        'hairpin': 'accessory',
        'badge': 'accessory',
        'badges': 'accessory',
        'pin': 'accessory',
        'pins': 'accessory',
        'scarf': 'accessory',
        'scarves': 'accessory',
        'tie': 'accessory',
        'ties': 'accessory',
        'belt': 'accessory',
        'belts': 'accessory',
        'watch': 'accessory',
        'watches': 'accessory',
        
        # Clothing (for future full-body VTO)
        'clothing': 'accessory',
        'clothes': 'accessory',
        'apparel': 'accessory',
        'shirt': 'accessory',
        'shirts': 'accessory',
        'dress': 'accessory',
        'dresses': 'accessory',
        'top': 'accessory',
        'tops': 'accessory',
        'jacket': 'accessory',
        'jackets': 'accessory',
        'coat': 'accessory',
        'coats': 'accessory',
        'sweater': 'accessory',
        'sweaters': 'accessory',
        'hoodie': 'accessory',
        'hoodies': 'accessory',
        
        # Shoes
        'shoes': 'accessory',
        'shoe': 'accessory',
        'sneakers': 'accessory',
        'boots': 'accessory',
        'boot': 'accessory',
        'sandals': 'accessory',
        'sandal': 'accessory',
        'heels': 'accessory',
        'heel': 'accessory',
        'slippers': 'accessory',
        'slipper': 'accessory',
        
        # Home & Kitchen (room placement items)
        'home': 'room',
        'kitchen': 'room',
        'decoration': 'room',
        'decorations': 'room',
        'decorative': 'room',
        'ornament': 'room',
        'ornaments': 'room',
        'vase': 'room',
        'vases': 'room',
        'frame': 'room',
        'frames': 'room',
        'mirror': 'room',
        'mirrors': 'room',
        'lamp': 'room',
        'lamps': 'room',
        'candle': 'room',
        'candles': 'room',
        'candleholder': 'room',
        'wall art': 'room',
        'artwork': 'room',
        'container': 'room',
        'containers': 'room',
        'storage': 'room',
        'tupperware': 'room',
        'organizer': 'room',
        'organizers': 'room',
        'furniture': 'room',
        
        # Face Masks
        'masks': 'mask',
        'face masks': 'mask',
        'face mask': 'mask',
        'mask': 'mask',
    }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--min-image-resolution',
            type=int,
            default=300,
            help='Minimum image resolution (default: 300px - more flexible)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without making changes'
        )
    
    def handle(self, *args, **options):
        min_resolution = options['min_image_resolution']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Enable VTO for Products with Good Images\n"
            f"{'='*70}\n"
        ))
        
        enabled_count = 0
        skipped_count = 0
        
        # Get all products in eligible categories
        eligible_products = self._get_eligible_products()
        total = eligible_products.count()
        
        self.stdout.write(f"Found {total} products in VTO-eligible categories\n")
        
        for idx, product in enumerate(eligible_products, 1):
            if idx % 50 == 0:
                self.stdout.write(
                    f"   Processing {idx}/{total} products...",
                    ending='\r'
                )
            
            # Check if product has good images
            if not self._has_good_images(product, min_resolution):
                skipped_count += 1
                continue
            
            # Determine asset type from category
            asset_type = self._get_asset_type(product.category)
            if not asset_type:
                skipped_count += 1
                continue
            
            # Determine placement mode based on category
            placement_mode = self._get_placement_mode(product.category, asset_type)
            
            if not dry_run:
                # Enable VTO on product
                product.vto_enabled = True
                product.save(update_fields=['vto_enabled'])
                
                # Create VTOAsset if doesn't exist
                VTOAsset.objects.get_or_create(
                    product=product,
                    defaults={
                        'asset_type': asset_type,
                        'overlay_image': product.images.first().image,
                        'anchor_points': self._get_default_anchor_points(asset_type),
                        'scale_factor': self._get_default_scale(asset_type),
                        'placement_mode': placement_mode,
                        'is_active': True,
                    }
                )
            
            enabled_count += 1
        
        self.stdout.write(f"\r   Processed {total} products                    \n")
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("  VTO Enablement Complete!"))
        self.stdout.write("="*70)
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"   Products processed: {total}")
        self.stdout.write(f"   VTO enabled: {enabled_count}")
        self.stdout.write(f"   Skipped (no good images): {skipped_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN - No changes made"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nEnabled VTO for {enabled_count} products!"
            ))
    
    def _get_eligible_products(self):
        """Get products in VTO-eligible categories - More flexible matching"""
        # Build query for eligible categories - check name, slug, and category path
        category_query = Q()
        for category_name in self.CATEGORY_MAPPING.keys():
            # Check category name
            category_query |= Q(category__name__icontains=category_name)
            # Check category slug
            category_query |= Q(category__slug__icontains=category_name.replace(' ', '-'))
            # Check category path (full path like "Fashion > Accessories")
            category_query |= Q(category_path__icontains=category_name)
        
        # Also check parent categories
        # Get all categories that match and include their children
        matching_categories = Category.objects.filter(
            Q(name__icontains='accessor') |
            Q(name__icontains='jewelry') |
            Q(name__icontains='jewellery') |
            Q(name__icontains='clothing') |
            Q(name__icontains='clothes') |
            Q(name__icontains='apparel') |
            Q(name__icontains='shoe') |
            Q(name__icontains='eyewear') |
            Q(name__icontains='glasses') |
            Q(name__icontains='hat') |
            Q(name__icontains='home') |
            Q(name__icontains='kitchen') |
            Q(name__icontains='decoration') |
            Q(name__icontains='decorative')
        )
        
        # Get all child categories
        all_eligible_categories = list(matching_categories)
        for cat in matching_categories:
            all_eligible_categories.extend(cat.get_all_children())
        
        category_ids = [cat.id for cat in all_eligible_categories]
        
        # Combine queries
        final_query = category_query
        if category_ids:
            final_query |= Q(category_id__in=category_ids)
        
        return Product.objects.filter(
            status='active',
            vto_enabled=False  # Not already enabled
        ).filter(final_query).prefetch_related('images', 'category')
    
    def _has_good_images(self, product, min_resolution):
        """Check if product has at least one good quality image - More flexible"""
        if not product.images.exists():
            return False
        
        for image_obj in product.images.all():
            try:
                img = Image.open(image_obj.image.path)
                width, height = img.size
                
                # Check resolution - at least one dimension should meet minimum
                # This is more flexible than requiring both dimensions
                if (width >= min_resolution or height >= min_resolution) and (width * height >= min_resolution * min_resolution * 0.5):
                    return True
            except Exception as e:
                # If file doesn't exist or can't be opened, try URL-based check
                try:
                    if hasattr(image_obj.image, 'url'):
                        # If image exists in storage, consider it valid
                        return True
                except:
                    continue
        
        return False
    
    def _get_asset_type(self, category):
        """Map category to VTO asset type - Check category path too"""
        if not category:
            return None
        
        # Check category name
        category_name = category.name.lower()
        category_path = category.get_full_path().lower() if hasattr(category, 'get_full_path') else category_name
        
        # Check both name and path
        search_text = f"{category_name} {category_path}"
        
        for key, asset_type in self.CATEGORY_MAPPING.items():
            if key in search_text:
                return asset_type
        
        # Default to accessory for most items
        return 'accessory'
    
    def _get_default_anchor_points(self, asset_type):
        """Get default anchor points for asset type"""
        defaults = {
            'glasses': {
                'leftEye': {'x': 0.3, 'y': 0.4},
                'rightEye': {'x': 0.7, 'y': 0.4},
                'nose': {'x': 0.5, 'y': 0.5},
            },
            'hat': {
                'top': {'x': 0.5, 'y': 0.1},
                'left': {'x': 0.2, 'y': 0.3},
                'right': {'x': 0.8, 'y': 0.3},
            },
            'jewelry': {
                'leftEar': {'x': 0.2, 'y': 0.4},
                'rightEar': {'x': 0.8, 'y': 0.4},
                'neck': {'x': 0.5, 'y': 0.8},
            },
            'mask': {
                'nose': {'x': 0.5, 'y': 0.5},
                'mouth': {'x': 0.5, 'y': 0.65},
            },
            'accessory': {
                'center': {'x': 0.5, 'y': 0.5},
            },
            'room': {
                'center': {'x': 0.5, 'y': 0.5},
            },
        }
        return defaults.get(asset_type, {})
    
    def _get_default_scale(self, asset_type):
        """Get default scale factor for asset type"""
        scales = {
            'glasses': 1.2,
            'hat': 1.5,
            'jewelry': 0.8,
            'mask': 1.0,
            'accessory': 1.0,
            'room': 0.3,  # Smaller for room placement
        }
        return scales.get(asset_type, 1.0)
    
    def _get_placement_mode(self, category, asset_type):
        """Determine placement mode based on category"""
        if not category:
            return 'auto'
        
        category_name = category.name.lower()
        category_path = category.get_full_path().lower() if hasattr(category, 'get_full_path') else category_name
        
        # Room placement categories (home, kitchen, decor, furniture)
        room_keywords = [
            'home', 'kitchen', 'decoration', 'decorative', 'furniture',
            'vase', 'vases', 'frame', 'frames', 'mirror', 'mirrors',
            'lamp', 'lamps', 'candle', 'candles', 'ornament', 'ornaments',
            'wall art', 'artwork', 'container', 'containers', 'storage',
            'tupperware', 'organizer', 'organizers'
        ]
        
        # Face detection categories (personal items)
        face_keywords = [
            'glasses', 'sunglasses', 'eyewear', 'hat', 'hats', 'cap', 'caps',
            'jewelry', 'jewellery', 'earrings', 'necklace', 'bracelet',
            'mask', 'face mask', 'clothing', 'apparel', 'shoes'
        ]
        
        search_text = f"{category_name} {category_path}"
        
        # Check for room keywords
        for keyword in room_keywords:
            if keyword in search_text:
                return 'room'
        
        # Check for face keywords
        for keyword in face_keywords:
            if keyword in search_text:
                return 'face'
        
        # Default to auto for accessories and unknown
        return 'auto'

