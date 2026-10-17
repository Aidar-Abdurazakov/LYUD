from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register('posts', views.PostViewSet, basename='post')

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('posts/<int:post_pk>/comments/', views.CommentListCreateView.as_view(), name='post-comments'),
    path('comments/<int:pk>/', views.CommentDetailView.as_view(), name='comment-detail'),

    path('', include(router.urls)),
]
