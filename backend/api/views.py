import base64
import csv
import logging
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django_filters.rest_framework import DjangoFilterBackend
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.filters import IngredientSearchFilter, RecipeFilter
from api.pagination import CustomPagination
from api.permissions import IsAuthor
from api.serializers import (
    AvatarSerializer,
    IngredientSerializer,
    RecipeCreateSerializer,
    RecipeReadSerializer,
    RecipeShortSerializer,
    SubscriptionSerializer,
    TagSerializer,
    UserFavouriteSerializer,
    UserSerializer,
    UserShoppingCartSerializer,
)
from core.constants import MAIN_URL
from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
)

logger = logging.getLogger('views')
User = get_user_model()


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
    filter_backends = (IngredientSearchFilter,)
    search_fields = ('^name',)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = [AllowAny]


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = CustomPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RecipeCreateSerializer
        return RecipeReadSerializer

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAuthor()]
        return [AllowAny()]

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

    @staticmethod
    def toggle_favorite_or_cart(request, recipe, serializer_class,
                                related_name):
        user = request.user
        if request.method == 'POST':
            serializer = serializer_class(
                data={'recipe': recipe.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        getattr(recipe, related_name).filter(user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        return self.toggle_favorite_or_cart(
            request, recipe, UserFavouriteSerializer, 'user_favourite'
        )

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        return self.toggle_favorite_or_cart(
            request, recipe, UserShoppingCartSerializer, 'user_shopping_cart'
        )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        user = request.user
        ingredients = RecipeIngredient.objects.filter(
            recipe__user_shopping_cart__user=user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        if not ingredients:
            return Response(
                {'detail': 'Список покупок пуст'},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response[
            'Content-Disposition'] = 'attachment; filename="shopping_cart.csv"'
        writer = csv.writer(response, lineterminator='\n')
        writer.writerow(['Ингредиент', 'Единица измерения', 'Количество'])
        for item in ingredients:
            writer.writerow([
                item['ingredient__name'],
                item['ingredient__measurement_unit'],
                item['total_amount']
            ])
        return response


class UserViewSet(UserViewSet):
    pagination_class = CustomPagination

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def subscribe(self, request, id=None):
        logger.info('начало обработки Подписаться')
        user = get_object_or_404(User, id=id)
        if request.method == 'POST':
            logger.info('POST запрос (подписаться)')
            serializer = SubscriptionSerializer(
                data={'subscribed_to': user.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(subscriber=request.user)
            data = UserSerializer(user, context={'request': request}).data
            data['recipes_count'] = user.recipes.count()
            recipes_limit = request.query_params.get('recipes_limit')
            recipes = user.recipes.all()
            if recipes_limit:
                try:
                    recipes_limit = int(recipes_limit)
                    if recipes_limit < 0:
                        raise ValueError
                    recipes = recipes[:recipes_limit]
                except ValueError:
                    return Response(
                        {
                            'detail':
                                'recipes_limit должен быть '
                                'неотрицательным числом'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            data['recipes'] = RecipeShortSerializer(recipes, many=True).data
            return Response(data, status=status.HTTP_201_CREATED)
        user.subscribers.filter(subscriber=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        queryset = request.user.subscriptions.all().annotate(
            recipes_count=Count('subscribed_to__recipes')
        )
        page = self.paginate_queryset(queryset)
        serializer = UserSerializer(page, many=True,
                                    context={'request': request})
        data = []
        recipes_limit = request.query_params.get('recipes_limit')
        for user_data in serializer.data:
            user = User.objects.get(id=user_data['id'])
            recipes = user.recipes.all()
            if recipes_limit:
                try:
                    recipes_limit = int(recipes_limit)
                    if recipes_limit < 0:
                        raise ValueError
                    recipes = recipes[:recipes_limit]
                except ValueError:
                    return Response(
                        {
                            'detail':
                                'recipes_limit должен быть '
                                'неотрицательным числом'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            user_data['recipes'] = RecipeShortSerializer(recipes,
                                                         many=True).data
            user_data['recipes_count'] = user.recipes_count
            data.append(user_data)
        return self.get_paginated_response(data)


class ShortLinkRedirectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, short_code, *args, **kwargs):
        try:
            recipe_id = base64.urlsafe_b64decode(short_code.encode()).decode()
            recipe_id = int(recipe_id)
        except (ValueError, UnicodeDecodeError):
            raise Http404('Ссылка не найдена')

        return redirect(f'/recipes/{recipe_id}/')
