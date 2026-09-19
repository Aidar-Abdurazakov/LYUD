from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from PIL import Image


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True, null=True, verbose_name='Аватар')
    bio = models.TextField(max_length=500, blank=True, verbose_name='О себе')
    is_private = models.BooleanField(default=False, verbose_name='Закрытый профиль')
    allow_messages = models.BooleanField(default=True, verbose_name='Разрешить сообщения')

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'Профиль {self.user.username}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar and hasattr(self.avatar, 'path') and self.avatar.name != 'avatars/default.png':
            try:
                img = Image.open(self.avatar.path)
                if img.height > 500 or img.width > 500:
                    img.thumbnail((500, 500))
                    img.save(self.avatar.path, quality=85, optimize=True)
            except Exception:
                pass


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    elif hasattr(instance, 'profile'):
        instance.profile.save()


class Post(models.Model):
    POST_TYPES = (
        ('text', 'Текст / Ветка'),
        ('image', 'Фотография'),
        ('reels', 'Reels (Видео)'),
    )

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts', verbose_name='Автор')
    content = models.TextField(blank=True, null=True, verbose_name='Текст / Описание')
    media = models.FileField(upload_to='posts_media/', blank=True, null=True, verbose_name='Медиафайл (Фото/Видео)')
    post_type = models.CharField(max_length=10, choices=POST_TYPES, default='text', verbose_name='Тип публикации')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='Родительский пост')
    quote_post = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='quotes', verbose_name='Цитируемая публикация')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True, verbose_name='Лайки')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Публикация'
        verbose_name_plural = 'Публикации'

    def __str__(self):
        return f"{self.author.username} - {self.post_type} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"

    def total_likes(self):
        return self.likes.count()

    def total_reposts(self):
        return self.reposts.count()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.media and hasattr(self.media, 'path'):
            try:
                img = Image.open(self.media.path)
                if img.height > 1080 or img.width > 1080:
                    img.thumbnail((1080, 1080))
                    img.save(self.media.path, quality=85, optimize=True)
            except Exception:
                pass


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments', verbose_name='Публикация')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор')
    text = models.TextField(max_length=500, verbose_name='Текст комментария')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return f'{self.author.username}: {self.text[:20]}'


class Repost(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reposts', verbose_name='Публикация')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата репоста')

    class Meta:
        unique_together = ('post', 'user')
        verbose_name = 'Репост'
        verbose_name_plural = 'Репосты'

    def __str__(self):
        return f'{self.user.username} -> {self.post.id}'


class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers', verbose_name='На кого подписан')
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following', verbose_name='Кто подписан')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата подписки')

    class Meta:
        unique_together = ('user', 'follower')
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f'{self.follower.username} -> {self.user.username}'


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='Отправитель')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', verbose_name='Получатель')
    text = models.TextField(verbose_name='Текст сообщения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время отправки')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.text[:20]}"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Лайк'),
        ('comment', 'Комментарий'),
        ('follow', 'Подписка'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='Получатель')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Отправитель')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name='Тип')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Публикация')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'

    def __str__(self):
        return f"{self.sender.username} - {self.notification_type} -> {self.recipient.username}"


class Story(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stories', verbose_name='Автор')
    image = models.ImageField(upload_to='stories/', verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'История'
        verbose_name_plural = 'Истории'

    def is_active(self):
        return self.created_at >= timezone.now() - timedelta(hours=24)

    def __str__(self):
        return f"Story by {self.author.username} at {self.created_at}"


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']


class CreatorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='creator_profile')
    monetization_enabled = models.BooleanField(default=False)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class Report(models.Model):
    REASONS = (
        ('spam', 'Спам'),
        ('abuse', 'Оскорбления или ненависть'),
        ('unsafe', 'Небезопасный контент'),
        ('other', 'Другое'),
    )
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_sent')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=20, choices=REASONS)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('reporter', 'post')


class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks_created')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
