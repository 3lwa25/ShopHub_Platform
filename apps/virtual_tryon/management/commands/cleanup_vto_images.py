"""
Cleanup Old VTO Images Command
Deletes images past their auto-delete date for GDPR compliance
"""
from django.core.management.base import BaseCommand
from apps.virtual_tryon.models import TryonImage


class Command(BaseCommand):
    help = "Delete VTO images past their auto-delete date (GDPR compliance)"
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  Cleanup Old VTO Images (Privacy Compliance)\n"
            f"{'='*70}\n"
        ))
        
        count = TryonImage.cleanup_old_images()
        
        if count > 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Deleted {count} old VTO images for privacy compliance\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nℹ️  No images to delete\n"
            ))
        
        self.stdout.write("="*70 + "\n")

