"""Management command to train the flood prediction model.

Usage:
    python manage.py train_models
"""

from django.core.management.base import BaseCommand
from prediction.services.train import train_flood_model
from prediction.services.model_loader import model_exists, get_model_info


class Command(BaseCommand):
    help = 'Train the flood prediction ML model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Retrain even if model already exists',
        )

    def handle(self, *args, **options):
        force = options['force']

        # Check if model exists
        if model_exists('flood_model.pkl') and not force:
            info = get_model_info('flood_model.pkl')
            self.stdout.write(
                self.style.WARNING(
                    f'Model already exists ({info["size_kb"]} KB). '
                    f'Use --force to retrain.'
                )
            )
            return

        self.stdout.write('Training flood prediction model...\n')

        try:
            results = train_flood_model()

            self.stdout.write(self.style.SUCCESS(
                f'\nTraining complete!'
                f'\n  Samples: {results["n_samples"]}'
                f'\n  Train: {results["n_train"]}, Test: {results["n_test"]}'
                f'\n  Model saved: {results["model_path"]}'
            ))

            # Print top features
            self.stdout.write('\nTop features:')
            for name, imp in results['top_features']:
                self.stdout.write(f'  {name}: {imp}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Training failed: {e}'))
            raise
