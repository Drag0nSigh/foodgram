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
    UserFavourite
)

User = get_user_model()

logger = logging.getLogger('serializers')


# Сериализатор для автора
class UserSerializer(serializers.ModelSerializer):
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
            return request.user.subscriptions.filter(id=obj.id).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


# Сериализатор для создания User
class SignUpSerializer(serializers.ModelSerializer):
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


# Сериализатор для загрузки аватара
class AvatarSerializer(serializers.ModelSerializer):
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


# Сериализатор для получения списка ингредиентов
class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


# Сериализатор для получения списка тегов
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


# Сериализатор для проверки ингредиентов при создании рецепта
class IngredientInRecipeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    def validate_id(self, value):
        if not Ingredient.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                {'detail': 'Ингредиент с указанным ID не найден.'}
            )
        return value


# Сериализатор для отображения ингредиентов в ответе
class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


# Сериализатор для создания рецепта
class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = IngredientInRecipeSerializer(many=True)
    tags = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
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

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                {'detail': "Необходимо указать хотя бы один ингредиент."}
            )
        ingredient_ids = [item['id'] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'detail': "Ингредиенты не должны повторяться."}
            )
        return value

    def validate_tags(self, value):
        if not Tag.objects.filter(id__in=value).exists():
            raise serializers.ValidationError(
                {'detail': "Один или более тегов не найдены."}
            )
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                {'detail': "Теги не должны повторяться."}
            )
        return value

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)

        recipe.tags.set(tags_data)

        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient_data['id'],
                amount=ingredient_data['amount']
            )

        return recipe

    def update(self, instance, validated_data):
        # Обновляем основные поля рецепта
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time',
                                                   instance.cooking_time)
        instance.image = validated_data.get('image', instance.image)
        instance.author = validated_data.get('author', instance.author)

        # Обновляем теги, если они переданы
        if 'tags' in validated_data:
            tags_data = validated_data.pop('tags')
            instance.tags.set(tags_data)
        else:
            raise serializers.ValidationError(
                {'detail': 'Нельзя обновлять рецепт без тега'}
            )

        # Обновляем ингредиенты, если они переданы
        if 'ingredients' in validated_data:
            ingredients_data = validated_data.pop('ingredients')
            # Удаляем старые ингредиенты
            instance.recipe_ingredients.all().delete()
            # Добавляем новые ингредиенты
            for ingredient_data in ingredients_data:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient_id=ingredient_data['id'],
                    amount=ingredient_data['amount']
                )
        else:
            raise serializers.ValidationError(
                {'detail': 'Нельзя обновлять рецепт без ингредиентов'}
            )

        # Сохраняем обновленный рецепт
        instance.save()
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data


# Сериализатор для отображения рецепта
class RecipeReadSerializer(serializers.ModelSerializer):
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
            return request.user.user_favourite.filter(
                recipe_id=obj.id
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user.user_shopping_cart.filter(
                recipe_id=obj.id
            ).exists()
        return False


class UserFavouriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='recipe.id')
    name = serializers.CharField(source='recipe.name')
    image = serializers.ImageField(source='recipe.image')
    cooking_time = serializers.IntegerField(source='recipe.cooking_time')

    class Meta:
        model = UserFavourite
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
