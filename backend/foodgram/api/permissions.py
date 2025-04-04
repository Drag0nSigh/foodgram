import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger('permissions')


class IsAuthor(BasePermission):
    """
    Разрешает доступ если пользователь автор.
    """

    def has_object_permission(self, request, view, obj):
        return obj.author is not None and obj.author == request.user
