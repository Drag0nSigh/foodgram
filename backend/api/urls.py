from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    AvatarUpdateView,
    UserViewSet,
    IngredientViewSet,
    RecipeViewSet,
    ShortLinkRedirectView,
    TagViewSet
)

app_name = 'api'

router = DefaultRouter()
router.register(r'ingredients', IngredientViewSet, basename='ingredients')
router.register(r'tags', TagViewSet, basename='tags')
router.register(r'users', UserViewSet)
router.register(r'recipes', RecipeViewSet, basename='recipes')


urlpatterns = [
    path('', include(router.urls)),
    path('', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('users/me/avatar/', AvatarUpdateView.as_view(), name='avatar-update'),
    path('s/<str:short_code>/',
         ShortLinkRedirectView.as_view(),
         name='short-link-redirect'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
