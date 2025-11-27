import gzip
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_chatbot.models import ProductKnowledge


class Command(BaseCommand):
    help = "Load product metadata/reviews into the AI chatbot knowledge base."

    def add_arguments(self, parser):
        parser.add_argument('--dataset-path', type=str, default=settings.CHATBOT_DATASET_ROOT)
        parser.add_argument('--max-per-file', type=int, default=200, help='Limit entries per meta file')

    def handle(self, *args, **options):
        dataset_path = Path(options['dataset_path'])
        max_per_file = options['max_per_file']

        if not dataset_path.exists():
            self.stderr.write(self.style.ERROR(f"Dataset path {dataset_path} does not exist."))
            return

        processed = 0
        for root, _, files in os.walk(dataset_path):
            for file_name in files:
                if not file_name.startswith('meta_') or not file_name.endswith('.json.gz'):
                    continue

                file_path = Path(root) / file_name
                self.stdout.write(f"Processing {file_path}")
                processed += self._ingest_meta_file(file_path, max_per_file)

        self.stdout.write(self.style.SUCCESS(f"Knowledge base updated with {processed} entries."))

    def _ingest_meta_file(self, file_path: Path, limit: int) -> int:
        count = 0
        category_label = file_path.stem.replace('meta_', '').replace('_', ' ')

        with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if limit and count >= limit:
                    break

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                asin = record.get('asin')
                title = record.get('title') or ''
                description = record.get('description') or ''
                price_raw = record.get('price')
                rating_raw = record.get('rating')
                features = record.get('feature') or record.get('features') or []

                if not asin or not title:
                    continue

                ProductKnowledge.objects.update_or_create(
                    external_id=asin,
                    defaults={
                        'title': title[:255],
                        'category': category_label[:255],
                        'description': description if isinstance(description, str) else ' '.join(description),
                        'highlights': features if isinstance(features, list) else [features] if features else [],
                        'price': self._safe_decimal(price_raw),
                        'average_rating': self._safe_decimal(rating_raw),
                        'source': str(file_path),
                        'metadata': {
                            'brand': record.get('brand'),
                            'tech1': record.get('tech1'),
                            'tech2': record.get('tech2'),
                        },
                    }
                )
                count += 1
        return count

    @staticmethod
    def _safe_decimal(value):
        from decimal import Decimal, InvalidOperation

        if value in (None, ''):
            return None

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        if isinstance(value, str):
            cleaned = value.replace('$', '').replace(',', '').strip()
            if not cleaned:
                return None
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return None
        return None

