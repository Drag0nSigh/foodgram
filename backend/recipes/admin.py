from django.contrib import admin

from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
    UserFavourite,
    UserShoppingCart
)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'measurement_unit',
    )
    search_fields = ('name',)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'author',
    )
    search_fields = ('name', 'author__username')
    list_filter = ('tags',)
    inlines = [RecipeIngredientInline]
    readonly_fields = ('favourite_count',)

    @admin.display(description='Добавлений в избранное')
    def favourite_count(self, obj):
        # Подсчитываем количество добавлений в избранное для рецепта
        return obj.user_favourite.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
    )


@admin.register(UserFavourite)
class UserFavouriteAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'recipe',
    )


@admin.register(UserShoppingCart)
class UserShoppingCartAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'recipe',
    )
