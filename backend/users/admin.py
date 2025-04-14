from django.contrib import admin

from users.models import Subscription, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'recipe_count',
    )
    search_fields = ['username', 'email']

    @admin.display(description='Всего рецептов')
    def recipe_count(self, obj):
        # Подсчитываем количество рецептов у пользователя
        return obj.recipes.count()


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'subscriber',
        'subscribed_to',
    )
