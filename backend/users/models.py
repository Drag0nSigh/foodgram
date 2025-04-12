import logging

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models

from core.constants import MAX_LENGTH_EMAIL, MAX_LENGTH_USERS_CHAR

logger = logging.getLogger('models')


class User(AbstractUser):
    username = models.CharField(
        verbose_name='Никнейм',
        max_length=MAX_LENGTH_USERS_CHAR,
        unique=True,
        help_text=f'Обязательное поле. Никнейм. Максимальная длина '
                  f'{MAX_LENGTH_USERS_CHAR} символов.',
        blank=False,
        null=False,
        validators=[UnicodeUsernameValidator()],
    )
    email = models.EmailField(
        verbose_name='Адрес электронной почты',
        max_length=MAX_LENGTH_EMAIL,
        unique=True,
        help_text='Обязательное поле. Введите корректный адрес электронной '
                  'почты.',
        blank=False,
        null=False,
    )
    first_name = models.CharField(
        verbose_name='Имя пользователя',
        max_length=MAX_LENGTH_USERS_CHAR,
        help_text='Обязательное поле. Имя пользователя.',
        blank=False,
        null=False,
    )
    last_name = models.CharField(
        verbose_name='Фамилия пользователя',
        max_length=MAX_LENGTH_USERS_CHAR,
        help_text='Обязательное поле. Фамилия пользователя.',
        blank=False,
        null=False,
    )
    avatar = models.ImageField(
        verbose_name='Аватар',
        upload_to='users/',  # Папка в MEDIA_ROOT для хранения аватаров
        help_text='Не обязательное поле. Загрузите аватар пользователя.',
        blank=True,
        default='',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        ordering = ('username',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscription(models.Model):
    subscriber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        # Обратная связь: подписки пользователя
        verbose_name='Подписчик',
    )
    subscribed_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscribers',
        # Обратная связь: кто подписан на пользователя
        verbose_name='Подписан на',
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        unique_together = ('subscriber', 'subscribed_to')

    def clean(self):
        """Запрещаем подписку на самого себя."""
        if self.subscriber == self.subscribed_to:
            raise ValidationError('Нельзя подписаться на самого себя.')

    def save(self, *args, **kwargs):
        """Запускаем валидацию перед сохранением."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.subscriber} подписан на {self.subscribed_to}'
