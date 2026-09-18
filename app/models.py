from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from django.utils import timezone



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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

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


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.author.username}: {self.text[:20]}'


class Repost(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reposts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')


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


class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')  # На кого подписаны
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')  # Кто подписан

    class Meta:
        unique_together = ('user', 'follower')


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, verbose_name='О себе')

    def __str__(self):
        return f'Профиль {self.user.username}'


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Лайк'),
        ('comment', 'Комментарий'),
        ('follow', 'Подписка'),
    )
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

# Добавь timedelta в импорты из datetime в начале файла, если его там нет:

class Story(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stories')
    image = models.ImageField(upload_to='stories/')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self):
        # История активна только 24 часа
        return self.created_at >= timezone.now() - timedelta(hours=24)

    def __str__(self):
        return f"Story by {self.author.username} at {self.created_at}"        