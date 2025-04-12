from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from core.constants import (
    MAX_LENGTH_INGREDIENTS_NAME,
    MAX_LENGTH_INGREDIENTS_UNIT,
    MAX_LENGTH_RECIPE_NAME,
    MAX_LENGTH_TAG_CHAR,
    MIN_AMOUNT,
    MIN_COOKING_TIME
)

User = get_user_model()


class Tag(models.Model):
    name = models.CharField(
        verbose_name='Название тега',
        max_length=MAX_LENGTH_TAG_CHAR,
        help_text='Обязательное поле. Название тега.',
        blank=False,
        null=False,
    )
    slug = models.SlugField(
        verbose_name='слаг',
        max_length=MAX_LENGTH_TAG_CHAR,
        unique=True,
        blank=False,
        null=False,
    )

    class Meta:
        ordering = ('name',)
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.slug


class Ingredient(models.Model):
    name = models.CharField(
        verbose_name='Название ингредиента',
        max_length=MAX_LENGTH_INGREDIENTS_NAME,
        help_text='Обязательно поле. Название ингредиентов',
        blank=False,
        null=False,
        db_index=True,
    )
    measurement_unit = models.CharField(
        verbose_name='Единица измерения',
        max_length=MAX_LENGTH_INGREDIENTS_UNIT,
        help_text='Обязательное поле. Единица измерения.',
        blank=False,
        null=False,
    )

    class Meta:
        ordering = ('name',)
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        unique_together = ('name', 'measurement_unit')

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField(
        blank=False,
        null=False,
        verbose_name='Название рецепта',
        max_length=MAX_LENGTH_RECIPE_NAME,
        help_text='Обязательное поле. Название рецепта.'
    )
    text = models.TextField(
        blank=False,
        null=False,
        verbose_name='Описание рецепта',
        help_text='Обязательное поле. Описание рецепта.',
    )
    cooking_time = models.PositiveSmallIntegerField(
        blank=False,
        null=False,
        verbose_name='Время приготовления (в минутах)',
        help_text=f'Обязательное поле. Время приготовления (в минутах). '
                  f'Минимальное значение {MIN_COOKING_TIME}.',
        validators=[MinValueValidator(MIN_COOKING_TIME), ]
    )
    image = models.ImageField(
        upload_to='recipes/images/',
        blank=False,
        null=False,
        verbose_name='Изображение рецепта',
        help_text='Обязательное поле. Изображение рецепта.',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',  # Промежуточную модель
        verbose_name='Ингредиенты',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Теги',
    )

    class Meta:
        ordering = ('name',)
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        default_related_name = 'recipes'

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_AMOUNT),
        ],
        verbose_name='Количество ингредиента',
        help_text=f'Обязательное поле. Количество ингредиента в единицах '
                  f'измерения ингредиента. Минимальное значение {MIN_AMOUNT}',
        blank=False,
        null=False,
    )

    class Meta:
        ordering = ('recipe',)
        verbose_name = 'Соответствие ингредиента и рецепта'
        verbose_name_plural = 'Соответствие ингредиентов и рецептов'
        default_related_name = 'recipe_ingredients'
        unique_together = ('ingredient', 'recipe')

    def __str__(self):
        return f'{self.recipe.name} - {self.ingredient.name} ({self.amount})'


class BaseFavouriteShoppingCart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True
        ordering = ('user__username',)
        unique_together = ('user', 'recipe')


class UserFavourite(BaseFavouriteShoppingCart):
    class Meta:
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        default_related_name = 'user_favourite'


class UserShoppingCart(BaseFavouriteShoppingCart):
    class Meta:
        verbose_name = 'Корзина покупок'
        verbose_name_plural = 'Корзины покупок'
        default_related_name = 'user_shopping_cart'
