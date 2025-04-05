import base64
import csv
import logging
import os

from api.permissions import IsAuthor
from api.serializers import (AvatarSerializer, IngredientSerializer,
                             RecipeCreateSerializer, RecipeReadSerializer,
                             RecipeShortSerializer, TagSerializer,
                             UserFavouriteSerializer, UserSerializer)
from core.constants import MAIN_URL
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from djoser.views import UserViewSet
from recipes.models import (Ingredient, Recipe, RecipeIngredient, Tag,
                            UserFavourite, UserShoppingCart)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger('views')
User = get_user_model()


def add_recipes_to_data(request, data, recipes_queryset):
    """Добавляет рецепты в словарь данных с учетом recipes_limit."""
    recipes_limit = request.query_params.get('recipes_limit')
    recipes = recipes_queryset

    if recipes_limit is not None:
        try:
            recipes_limit = int(recipes_limit)
            if recipes_limit >= 0:
                recipes = recipes[:recipes_limit]
            else:
                raise ValueError(
                    'recipes_limit должен быть неотрицательным числом')
        except ValueError as e:
            error_message = str(e) if 'неотрицательным' in str(
                e) else 'recipes_limit должен быть целым числом'
            return Response({'detail': error_message},
                            status=status.HTTP_400_BAD_REQUEST)

    data['recipes'] = RecipeShortSerializer(recipes, many=True).data
    data['recipes_count'] = recipes_queryset.count()
    return None


class RecipePagination(PageNumberPagination):
    page_size_query_param = 'limit'


class AvatarUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        user = request.user

        # Проверяем, есть ли данные в запросе
        if not request.data:
            logger.warning('Пустое тело запроса')
            return Response({'error': 'Тело запроса не может быть пустым'},
                            status=400)

        serializer = AvatarSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            logger.info('Аватар прошёл валидацию')
            serializer.save()
            return Response({'avatar': f"{settings.MEDIA_URL}{user.avatar}"},
                            status=200)
        logger.warning(f'Проблема с валидацией {serializer.errors}')
        return Response(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        user = request.user

        # Удаляем аватар пользователя
        if user.avatar:
            # Удаляем файл аватара с диска, если он существует
            if os.path.isfile(user.avatar.path):
                os.remove(user.avatar.path)
            user.avatar = None
            user.save()
            logger.info(f'Аватар пользователя {user.username} удалён')
            return Response({'message': 'Аватар успешно удалён'}, status=200)
        else:
            logger.warning(
                f'У пользователя {user.username} нет аватара для удаления')
            return Response({'error': 'Аватар отсутствует'}, status=404)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = self.queryset
        name = self.request.query_params.get('name', None)
        if name is not None:
            logger.debug(f"Фильтрация ингредиентов по name: {name}")
            # Фильтр по частичному вхождению в начале названия
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = [AllowAny]


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = RecipePagination

    def get_permissions(self):
        if self.action in [
            'create',
            'favorite',
            'unfavorite',
            'shopping_cart',
            'download_shopping_cart',
        ]:
            return [IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy',]:
            permissions = [IsAuthenticated(), IsAuthor()]
            return permissions
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RecipeCreateSerializer
        return RecipeReadSerializer

    def get_queryset(self):
        logger.debug(
            f'Получен запрос {self.request.method} с параметрами: '
            f'{self.request.query_params}'
        )
        recipes = Recipe.objects.all()
        user = (self.request.user if
                self.request.user.is_authenticated else None)
        logger.debug(f"Пользователь: {user}, авторизован: "
                     f"{self.request.user.is_authenticated}")

        # Пропускаем фильтры для действий, работающих с конкретным объектом
        if self.action in ['update', 'partial_update', 'destroy']:
            logger.debug(
                'Пропускаем фильтры для действий '
                'update/partial_update/destroy')
            return recipes

        # Фильтрация по is_favorited (в избранном)
        is_favorited = self.request.query_params.get('is_favorited')
        # Преобразуем значение в булево
        is_favorited_true = is_favorited in ('1', 'true')
        is_favorited_false = is_favorited in ('0', 'false')
        if is_favorited is not None:
            logger.debug(f"Фильтрация по is_favorited: {is_favorited}")
            if user and is_favorited_true:
                # Получаем ID рецептов, которые в избранном у пользователя
                favorite_recipe_ids = UserFavourite.objects.filter(
                    user=user).values_list('recipe_id', flat=True)
                recipes = recipes.filter(id__in=favorite_recipe_ids)
                logger.debug(f"Фильтрация по is_favorited: true {recipes}")
            elif is_favorited_false and user:
                # Исключаем рецепты, которые в избранном у пользователя
                favorite_recipe_ids = UserFavourite.objects.filter(
                    user=user).values_list('recipe_id', flat=True)
                recipes = recipes.exclude(id__in=favorite_recipe_ids)
                logger.debug(f"Фильтрация по is_favorited: false {recipes}")

        # Фильтрация по is_in_shopping_cart (в корзине покупок)
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart')

        is_in_shopping_cart_true = is_in_shopping_cart in ('1', 'true')
        is_in_shopping_cart_false = is_in_shopping_cart in ('0', 'false')
        if is_in_shopping_cart is not None:
            logger.debug(
                f"Фильтрация по is_in_shopping_cart: {is_in_shopping_cart}")
            logger.debug(
                f"is_in_shopping_cart_true: {is_in_shopping_cart_true}, "
                f"user: {user}")
            if user and is_in_shopping_cart_true:
                # Получаем ID рецептов, которые в корзине у пользователя
                shopping_cart_recipe_ids = UserShoppingCart.objects.filter(
                    user=user).values_list('recipe_id', flat=True)
                logger.debug(
                    f"Рецепты в корзине (IDs): "
                    f"{list(shopping_cart_recipe_ids)}")
                recipes = recipes.filter(id__in=shopping_cart_recipe_ids)
                logger.debug(
                    f"Фильтрация по is_in_shopping_cart: true {recipes}")
            elif is_in_shopping_cart_false and user:
                # Исключаем рецепты, которые в корзине у пользователя
                shopping_cart_recipe_ids = UserShoppingCart.objects.filter(
                    user=user).values_list('recipe_id', flat=True)
                logger.debug(
                    f'Рецепты в корзине (IDs): '
                    f'{list(shopping_cart_recipe_ids)}')
                recipes = recipes.exclude(id__in=shopping_cart_recipe_ids)
                logger.debug(
                    f'Фильтрация по is_in_shopping_cart: false {recipes}')

        # Фильтрация по тегам
        tags = self.request.query_params.getlist('tags')
        if tags:
            logger.debug(f"Фильтрация по tags (slugs): {tags}")
            recipes = recipes.filter(tags__slug__in=tags).distinct()

        # Фильтрация по автору
        author_id = self.request.query_params.get('author')
        if author_id:
            logger.debug(f"Фильтрация по author_id: {author_id}")
            try:
                author_id = int(author_id)
                recipes = recipes.filter(author_id=author_id)
            except ValueError:
                logger.warning(
                    "Параметр 'author' должен быть целым числом "
                    "(ID пользователя)")
                raise serializers.ValidationError(
                    {
                        "error": "Параметр 'author' должен быть целым числом "
                                 "(ID пользователя)"}
                )

        logger.debug(f"Количество найденных рецептов: {recipes.count()}")
        recipes = recipes.order_by('-id')
        return recipes

    def perform_create(self, serializer):
        logger.info('Начало обработки POST-запроса для создания рецепта')
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_short_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        short_link = self.generate_short_link(recipe)
        return Response({'short-link': short_link})

    def generate_short_link(self, recipe):
        short_link = base64.urlsafe_b64encode(str(recipe.id).encode()).decode()
        return f'https://{MAIN_URL}/s/{short_link}'

    @action(detail=True, methods=['post', 'delete'])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            if UserFavourite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Рецепт уже в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            favourite = UserFavourite.objects.create(user=user, recipe=recipe)
            serializer = UserFavouriteSerializer(favourite)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            favourite = UserFavourite.objects.filter(user=user,
                                                     recipe=recipe).first()
            if not favourite:
                return Response(
                    {'detail': 'Рецепт не найден в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            favourite.delete()
            logger.info('Рецепт удалён')
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'])
    def shopping_cart(self, request, pk=None):
        recipe = Recipe.objects.filter(id=pk).first()
        if not recipe:
            return Response(
                {'detail': 'Рецепт не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        if request.method == 'POST':
            if UserShoppingCart.objects.filter(user=user,
                                               recipe=recipe).exists():
                return Response(
                    {'detail': 'Рецепт уже в корзине'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            UserShoppingCart.objects.create(user=user, recipe=recipe)
            return Response(
                RecipeShortSerializer(
                    recipe,
                    context={'request': request}
                ).data,
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            recipe_in_shopping_cart = UserShoppingCart.objects.filter(
                user=user, recipe=recipe
            ).first()
            logger.info(f'Рецепт для удаления {recipe_in_shopping_cart}')
            if not recipe_in_shopping_cart:
                return Response(
                    {'detail': 'Рецепт не в корзине'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            recipe_in_shopping_cart.delete()
            logger.info('Рецепт удалён')
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        user = request.user

        # Получаем все рецепты из списка покупок пользователя
        shopping_cart_recipes = UserShoppingCart.objects.filter(
            user=user).values_list('recipe', flat=True)
        if not shopping_cart_recipes:
            return Response(
                {'detail': 'Список покупок пуст'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем все ингредиенты для этих рецептов
        recipe_ingredients = RecipeIngredient.objects.filter(
            recipe__in=shopping_cart_recipes
        ).select_related('ingredient')

        # Суммируем ингредиенты
        ingredient_summary = {}
        for ri in recipe_ingredients:
            ingredient = ri.ingredient
            key = (ingredient.name, ingredient.measurement_unit)
            if key in ingredient_summary:
                ingredient_summary[key] += ri.amount
            else:
                ingredient_summary[key] = ri.amount

        # Создаем CSV-файл
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response[
            'Content-Disposition'] = 'attachment; filename="shopping_cart.csv"'

        writer = csv.writer(response, lineterminator='\n')
        writer.writerow(['Ингредиент', 'Единица измерения', 'Количество'])

        for (name, unit), amount in ingredient_summary.items():
            writer.writerow([name, unit, amount])

        return response


class CustomUserPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100


class CustomUserViewSet(UserViewSet):
    pagination_class = CustomUserPagination

    def get_permissions(self):
        if (self.action == 'me'
                or self.action == 'subscribe'
                or self.action == 'get_subscribe'):
            return [IsAuthenticated()]
        # Для всех остальных действий используем права из настроек
        return [permission() for permission in self.permission_classes]

    @action(detail=True, methods=['post', 'delete'])
    def subscribe(self, request, id=None):
        if request.method == 'POST':
            user = User.objects.filter(id=id).first()

            if request.user == user:
                return Response(
                    {'detail': 'Нельзя подписаться на себя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not user:
                return Response(
                    {'detail': 'Такого пользователя нет'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if user.subscribers.filter(id=request.user.id).exists():
                return Response(
                    {'detail': 'Вы уже подписаны на этого пользователя'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.subscribers.add(request.user)
            serializer = UserSerializer(user, context={'request': request})
            data = serializer.data

            # Добавляем рецепты и их количество
            recipes = user.recipes.all()

            # Добавляем рецепты в ответ с лимитом
            error_response = add_recipes_to_data(request, data, recipes)
            if error_response:
                return error_response

            return Response(data, status=status.HTTP_201_CREATED)
        if request.method == 'DELETE':
            user = User.objects.filter(id=id).first()
            if user is None:
                return Response(
                    {'detail': 'Такого пользователя не существует'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not request.user.subscriptions.filter(id=user.id).exists():
                return Response(
                    {'detail': 'Вы не были подписаны на этого пользователя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            request.user.subscriptions.remove(user)
            logger.info('Пользователь удалён')
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def subscriptions(self, request, id=None):
        users_limit = request.query_params.get('limit')
        subscribed_users = request.user.subscriptions.all()

        if users_limit is not None:
            try:
                users_limit = int(users_limit)
                if users_limit >= 0:
                    subscribed_users = subscribed_users[:users_limit]
                else:
                    raise ValueError(
                        'limit должен быть неотрицательным числом')
            except ValueError as e:
                error_message = str(e) if 'неотрицательным' in str(
                    e) else 'limit должен быть целым числом'
                return Response({'detail': error_message},
                                status=status.HTTP_400_BAD_REQUEST)

        # Добавляем пагинацию пользователей
        page = self.paginate_queryset(subscribed_users)
        all_data = []
        for user in page:
            serializer = UserSerializer(user, context={'request': request})
            data = serializer.data
            recipes = user.recipes.all()
            error_response = add_recipes_to_data(request, data, recipes)
            if error_response:
                return error_response
            all_data.append(data)
        return self.get_paginated_response(all_data)


class ShortLinkRedirectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, short_code, *args, **kwargs):
        try:
            recipe_id = base64.urlsafe_b64decode(short_code.encode()).decode()
            recipe_id = int(recipe_id)
        except (ValueError, UnicodeDecodeError):
            raise Http404('Ссылка не найдена')

        return redirect(f'/api/recipes/{recipe_id}/')
