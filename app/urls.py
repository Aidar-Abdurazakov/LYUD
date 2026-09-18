from django.urls import path
from . import views

urlpatterns = [
    # Главная лента и авторизация
    path('', views.feed_view, name='feed'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Профиль и Подписки
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
    path('follow/<str:username>/', views.toggle_follow_view, name='toggle_follow'),
    
    # Сообщения (Direct)
    path('direct/', views.direct_view, name='direct'),
    path('direct/<str:username>/', views.direct_view, name='direct_dialog'),
    
    # Посты и взаимодействие
    path('reels/', views.reels_view, name='reels'),
    path('create/', views.create_post_view, name='create'),
    path('post/<int:post_id>/delete/', views.delete_post_view, name='delete_post'),
    path('post/<int:post_id>/like/', views.toggle_like_view, name='toggle_like'),
    path('post/<int:post_id>/comment/', views.add_comment_view, name='add_comment'),
    path('post/<int:post_id>/repost/', views.repost_view, name='repost_post'),
    
    # Поиск и Уведомления
    path('search/', views.search_view, name='search'),
    path('notifications/', views.notifications_view, name='notifications'),
]