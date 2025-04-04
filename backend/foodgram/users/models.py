import logging

from core.constants import MAX_LENGTH_EMAIL, MAX_LENGTH_USERS_CHAR
from django.contrib.auth.models import AbstractUser
from django.db import models

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
        null=True,
    )
    # Связь для хранения подписок
    subscriptions = models.ManyToManyField(
        'self',
        symmetrical=False,  # Подписка не обязана быть взаимной
        related_name='subscribers',
        verbose_name='Подписки',
        blank=True,
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ('id',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username
