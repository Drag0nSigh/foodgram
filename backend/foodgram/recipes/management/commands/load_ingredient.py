import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузка данных из CSV-файлов в базу данных'

    def handle(self, *args, **kwargs):
        self.load_ingredient(
            os.path.join(
                os.path.dirname(settings.BASE_DIR),
                'data',
                'ingredients.csv'
            )
        )

    def load_ingredient(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                try:
                    ingredient, created = Ingredient.objects.update_or_create(
                        name=row[0],
                        defaults={'measurement_unit': row[1]}
                    )
                    action = 'создан' if created else 'обновлен'
                    self.stdout.write(
                        self.style.SUCCESS(f'Ингредиента {ingredient.name} '
                                           f'({action}).'))
                except IntegrityError as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Ошибка при добавлении ингредиента с '
                            f'id={row["id"]}: {e}'
                        )
                    )
        self.stdout.write(
            self.style.SUCCESS(
                'Файл ingredients.csv обработан'
            )
        )
