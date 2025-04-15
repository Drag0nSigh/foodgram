import base64
import logging

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from drf_base64.fields import Base64ImageField
from rest_framework import serializers

from api.validators import username_by_path_me, username_by_pattern
from core.constants import MAX_LENGTH_EMAIL, MAX_LENGTH_USERS_CHAR
from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
    UserFavourite,
    UserShoppingCart
)
from users.models import Subscription

User = get_user_model()

logger = logging.getLogger('serializers')


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для автора"""
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        logger.info('Проверка на подписку')
        if request and request.user.is_authenticated:
            return obj.subscribers.filter(subscriber=request.user).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class SignUpSerializer(serializers.ModelSerializer):
    """Сериализатор для создания User"""
    email = serializers.EmailField(
        max_length=MAX_LENGTH_EMAIL,
        required=True
    )
    username = serializers.CharField(
        max_length=MAX_LENGTH_USERS_CHAR,
        required=True
    )
    first_name = serializers.CharField(
        max_length=MAX_LENGTH_USERS_CHAR,
        required=True
    )
    last_name = serializers.CharField(
        max_length=MAX_LENGTH_USERS_CHAR,
        required=True
    )
    password = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password')

    def validate(self, data):
        username = data.get('username')

        username_by_path_me(username)
        username_by_pattern(username)

        return data

    def create(self, validated_data: dict):
        username = validated_data.get('username')
        email = validated_data.get('email')
        if (not User.objects.filter(username=username).first()
                and not User.objects.filter(email=email).first()):
            logger.info('username и email уникальные')
            user = User.objects.create_user(**validated_data)
            return user
        logger.info('username и email не уникальные')
        raise serializers.ValidationError(
            {'detail': 'username и email должны быть уникальными'}
        )


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для загрузки аватара"""
    avatar = serializers.CharField(
        required=False,
        allow_blank=True
    )  # Принимаем base64-строку

    class Meta:
        model = User
        fields = ('avatar',)

    def validate_avatar(self, value):
        # Проверяем, что это base64-строка с изображением
        if not value.startswith('data:image/'):
            logger.info('Неверный формат данных аватара. '
                        'Ожидается base64-изображение.')
            raise serializers.ValidationError(
                {'detail': 'Неверный формат данных аватара. '
                           'Ожидается base64-изображение.'})
        return value

    def update(self, instance, validated_data):
        # Декодируем base64 и сохраняем как файл
        avatar_data = validated_data['avatar']
        format, imgstr = avatar_data.split(';base64,')
        ext = format.split('/')[-1]  # Например, 'png'
        file_name = f"{instance.username}_avatar.{ext}"
        data = ContentFile(base64.b64decode(imgstr), name=file_name)

        instance.avatar = data
        instance.save()
        return instance


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для получения списка ингредиентов"""
    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для получения списка тегов"""
    class Meta:
        model = Tag
        fields = '__all__'


class IngredientInRecipeSerializer(serializers.Serializer):
    """Сериализатор для проверки ингредиентов при создании рецепта"""
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField(min_value=1)


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения ингредиентов в ответе"""
    id = serializers.PrimaryKeyRelatedField(
        source='ingredient',
        read_only=True
    )
    name = serializers.SlugRelatedField(
        source='ingredient',
        slug_field='name',
        read_only=True
    )
    measurement_unit = serializers.SlugRelatedField(
        source='ingredient',
        slug_field='measurement_unit',
        read_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания рецепта"""
    ingredients = IngredientInRecipeSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
    image = Base64ImageField()
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'text',
            'cooking_time',
            'image',
            'ingredients',
            'tags',
            'author'
        )

    def validate(self, data):
        # Валидация ингредиентов
        logger.info('Валидация ингредиентов')
        ingredients_data = data.get('ingredients', [])
        if not ingredients_data:
            raise serializers.ValidationError(
                {'ingredients': 'Необходимо указать хотя бы один ингредиент.'}
            )
        ingredient_ids = []
        for ingredient in ingredients_data:
            if ingredient['amount'] < 1:
                raise serializers.ValidationError(
                    {
                        'ingredients': 'Количество ингредиента должно быть '
                                       'больше или равно 1.'
                    }
                )
            ingredient_ids.append(ingredient['id'].pk)
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'ingredients': 'Ингредиенты не должны повторяться.'}
            )

        # Валидация тегов
        logger.info('Валидация тегов')
        tags = data.get('tags', [])
        if not tags:
            raise serializers.ValidationError(
                {'tags': 'Необходимо указать хотя бы один тег.'}
            )
        tag_ids = [tag.pk for tag in tags]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError(
                {'tags': 'Теги не должны повторяться.'}
            )
        if not Tag.objects.filter(id__in=tag_ids).exists():
            raise serializers.ValidationError(
                {'tags': 'Один или более тегов не найдены.'}
            )

        return data

    @staticmethod
    def create_or_update_ingredients(recipe, ingredients_data):
        """Статический метод для обработки ингредиентов."""
        ingredient_objects = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
            for ingredient_data in ingredients_data
        ]
        logger.info(f'Ингредиенты {ingredient_objects}')
        RecipeIngredient.objects.bulk_create(ingredient_objects)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        logger.info(f'Ингредиенты {ingredients_data}')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)

        recipe.tags.set(tags_data)
        self.create_or_update_ingredients(recipe, ingredients_data)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)
        instance = super().update(instance, validated_data)

        if tags_data is not None:
            instance.tags.set(tags_data)

        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            self.create_or_update_ingredients(instance, ingredients_data)

        instance.save()
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения рецепта"""
    tags = TagSerializer(many=True)
    author = UserSerializer()
    ingredients = RecipeIngredientReadSerializer(
        many=True,
        source='recipe_ingredients'
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'image',
            'name',
            'text',
            'cooking_time'
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_favourite.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_shopping_cart.filter(user=request.user).exists()
        return False


class UserFavouriteSerializer(serializers.ModelSerializer):
    """Сериализатор для избранного"""
    id = serializers.IntegerField(source='recipe.id')
    name = serializers.CharField(source='recipe.name')
    image = serializers.ImageField(source='recipe.image')
    cooking_time = serializers.IntegerField(source='recipe.cooking_time')

    class Meta:
        model = UserFavourite
        fields = ('id', 'name', 'image', 'cooking_time')

    def validate(self, data):
        user = self.context['request'].user
        recipe = data['recipe']
        if UserFavourite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'detail': 'Рецепт уже в избранном.'}
            )
        return data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Сериализатор для коротких ссылок"""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class UserShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для корзины покупок"""
    class Meta:
        model = UserShoppingCart
        fields = ('user', 'recipe')
        read_only_fields = ('user',)

    def validate(self, data):
        user = self.context['request'].user
        recipe = data['recipe']
        if UserShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'detail': 'Рецепт уже в корзине.'}
            )
        return data


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализаор для подписок на пользователей"""
    class Meta:
        model = Subscription
        fields = ('subscriber', 'subscribed_to')
        read_only_fields = ('subscriber',)

    def validate(self, data):
        subscriber = self.context['request'].user
        subscribed_to = data['subscribed_to']
        if subscriber == subscribed_to:
            raise serializers.ValidationError(
                {'detail': 'Нельзя подписаться на себя.'}
            )
        if subscribed_to.subscribers.filter(subscriber=subscriber).exists():
            raise serializers.ValidationError(
                {'detail': 'Вы уже подписаны на этого пользователя.'}
            )
        return data
