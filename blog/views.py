from django.conf import settings
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly

from .models import Comment, Post
from .permissions import IsAuthorOrReadOnly
from .serializers import CommentSerializer, PostSerializer, RegisterSerializer


def get_visible_post_or_404(request, post_pk):
    """Пост, который этот пользователь вправе видеть (иначе 404, а не 403, чтобы не раскрывать черновики)."""
    return get_object_or_404(Post.objects.visible_to(request.user), pk=post_pk)


def visible_comments(queryset, user):
    """Одобренные комментарии, а авторизованному ещё и его собственные (ожидающие модерации)."""
    condition = Q(is_approved=True)
    if user is not None and user.is_authenticated:
        condition |= Q(author=user)
    return queryset.filter(condition).select_related('author')


@extend_schema(
    summary='Регистрация',
    description='Создаёт пользователя. После регистрации получите токен через `POST /api/v1/auth/token/`.',
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # чтобы устаревший токен в заголовке не мешал регистрации


@extend_schema_view(
    list=extend_schema(
        summary='Список постов',
        description='Гостям доступны только опубликованные посты. Авторизованный пользователь '
                    'дополнительно видит свои черновики. Есть пагинация: `?page=2&page_size=5`.',
    ),
    create=extend_schema(summary='Создать пост', description='Автором станет текущий пользователь.'),
    retrieve=extend_schema(summary='Один пост'),
    update=extend_schema(summary='Изменить пост (только автор)'),
    partial_update=extend_schema(summary='Частично изменить пост (только автор)'),
    destroy=extend_schema(summary='Удалить пост (только автор)'),
)
class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        return (
            Post.objects.visible_to(self.request.user)
            .select_related('author')
            .annotate(approved_comments_count=Count('comments', filter=Q(comments__is_approved=True)))
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


@extend_schema_view(
    get=extend_schema(summary='Список комментариев поста'),
    post=extend_schema(summary='Добавить комментарий', description='Автором станет текущий пользователь.'),
)
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Comment.objects.none()
        post = get_visible_post_or_404(self.request, self.kwargs['post_pk'])
        return visible_comments(post.comments.all(), self.request.user)

    def perform_create(self, serializer):
        post = get_visible_post_or_404(self.request, self.kwargs['post_pk'])
        approved = not getattr(settings, 'BLOG_COMMENTS_REQUIRE_APPROVAL', False)
        serializer.save(post=post, author=self.request.user, is_approved=approved)


@extend_schema_view(
    get=extend_schema(summary='Один комментарий'),
    put=extend_schema(summary='Изменить комментарий (только автор)'),
    patch=extend_schema(summary='Частично изменить комментарий (только автор)'),
    delete=extend_schema(summary='Удалить комментарий (только автор)'),
)
class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        queryset = Comment.objects.filter(post__in=Post.objects.visible_to(user))
        return visible_comments(queryset, user)
