from django.conf import settings
from django.db import models
from django.db.models import Q


class PostQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user is not None and user.is_authenticated:
            return self.filter(Q(is_published=True) | Q(author=user))
        return self.filter(is_published=True)


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_posts',
        verbose_name='Автор',
    )
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    body = models.TextField(verbose_name='Текст')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')
    is_published = models.BooleanField(default=True, verbose_name='Опубликован')

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Пост блога'
        verbose_name_plural = 'Посты блога'

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Пост',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_comments',
        verbose_name='Автор',
    )
    body = models.TextField(verbose_name='Текст')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')
    is_approved = models.BooleanField(default=True, verbose_name='Одобрен')

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = 'Комментарий блога'
        verbose_name_plural = 'Комментарии блога'

    def __str__(self):
        return f'Комментарий {self.author} к «{self.post}»'
