from django.contrib import admin

from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
    UserFavourite,
    UserShoppingCart
)
from users.models import User


class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'measurement_unit',
    )
    search_fields = ('name',)


class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'author',
    )
    search_fields = ('name', 'author')
    list_filter = ('tags',)
    readonly_fields = ('favourite_count',)

    def favourite_count(self, obj):
        # Подсчитываем количество добавлений в избранное для рецепта
        return obj.user_favourite.count()

    favourite_count.short_description = 'Добавлений в избранное'


class TagAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
    )


class UserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
    )
    search_fields = ['username', 'email']


class UserFavouriteAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'recipe',
    )


class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = (
        'recipe',
        'ingredient',
        'amount',
    )


class UserShoppingCartAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'recipe',
    )


admin.site.register(UserShoppingCart, UserShoppingCartAdmin)
admin.site.register(UserFavourite, UserFavouriteAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(RecipeIngredient, RecipeIngredientAdmin)
admin.site.register(User, UserAdmin)
