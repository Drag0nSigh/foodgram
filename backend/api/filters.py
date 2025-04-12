from django_filters import rest_framework as filters
from rest_framework.filters import SearchFilter

from recipes.models import Ingredient, Recipe, UserFavourite, UserShoppingCart


class IngredientSearchFilter(SearchFilter):
    def filter_queryset(self, request, queryset, view):
        name = request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class RecipeFilter(filters.FilterSet):
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')
    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    author = filters.NumberFilter(field_name='author__id')

    class Meta:
        model = Recipe
        fields = ('is_favorited', 'is_in_shopping_cart', 'tags', 'author')

    def filter_is_favorited(self, queryset, name, value):
        if not self.request.user.is_authenticated:
            return queryset
        favorite_ids = UserFavourite.objects.filter(
            user=self.request.user
        ).values_list('recipe_id', flat=True)
        if value:
            return queryset.filter(id__in=favorite_ids)
        return queryset.exclude(id__in=favorite_ids)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if not self.request.user.is_authenticated:
            return queryset
        cart_ids = UserShoppingCart.objects.filter(
            user=self.request.user
        ).values_list('recipe_id', flat=True)
        if value:
            return queryset.filter(id__in=cart_ids)
        return queryset.exclude(id__in=cart_ids)
