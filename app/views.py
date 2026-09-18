from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Post, Comment, Repost, Follow, Message, Profile, Notification

# --- Лента ---
def feed_view(request):
    if request.user.is_authenticated:
        following_users = Follow.objects.filter(follower=request.user).values_list('user', flat=True)
        posts = Post.objects.filter(
            Q(author__in=following_users) | Q(author=request.user)
        ).order_by('-created_at')
    else:
        posts = Post.objects.all().order_by('-created_at')
        
    return render(request, 'posts/feed.html', {'posts': posts})

# --- Профиль и редактирование ---
@login_required
def profile_view(request, username=None):
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = request.user

    posts = Post.objects.filter(author=profile_user).order_by('-created_at')
    is_following = False
    if request.user.is_authenticated and profile_user != request.user:
        is_following = Follow.objects.filter(user=profile_user, follower=request.user).exists()

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
        'followers_count': profile_user.followers.count(),
        'following_count': profile_user.following.count(),
    }
    return render(request, 'posts/profile.html', context)

@login_required
def edit_profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        bio = request.POST.get('bio', '')
        avatar = request.FILES.get('avatar')
        
        profile.bio = bio
        if avatar:
            profile.avatar = avatar
        profile.save()
        return redirect('profile')
        
    return render(request, 'posts/edit_profile.html', {'profile': profile})

# --- Подписки ---
@login_required
def toggle_follow_view(request, username):
    target_user = get_object_or_404(User, username=username)
    if target_user != request.user:
        follow_obj = Follow.objects.filter(user=target_user, follower=request.user).first()
        if follow_obj:
            follow_obj.delete()
        else:
            Follow.objects.create(user=target_user, follower=request.user)
            Notification.objects.create(
                recipient=target_user,
                sender=request.user,
                notification_type='follow'
            )
    return redirect(request.META.get('HTTP_REFERER', 'profile'))

# --- Чат / Direct ---
@login_required
def direct_view(request, username=None):
    following_users = User.objects.filter(followers__follower=request.user)
    active_dialog_user = None
    messages_list = []

    if username:
        active_dialog_user = get_object_or_404(User, username=username)
        if request.method == 'POST':
            text = request.POST.get('text', '').strip()
            if text:
                Message.objects.create(
                    sender=request.user,
                    recipient=active_dialog_user,
                    text=text
                )
                return redirect('direct_dialog', username=username)

        messages_list = Message.objects.filter(
            Q(sender=request.user, recipient=active_dialog_user) |
            Q(sender=active_dialog_user, recipient=request.user)
        ).order_by('created_at')

    context = {
        'dialog_users': following_users,
        'active_dialog_user': active_dialog_user,
        'messages_list': messages_list,
    }
    return render(request, 'posts/direct.html', context)

# --- Посты и медиа ---
def reels_view(request):
    reels_posts = Post.objects.filter(post_type='reels').order_by('-created_at')
    return render(request, 'posts/reels.html', {'posts': reels_posts})

@login_required
def create_post_view(request):
    if request.method == 'POST':
        content = request.POST.get('content', '')
        media = request.FILES.get('media')
        post_type = request.POST.get('post_type', 'post')
        
        Post.objects.create(
            author=request.user,
            content=content,
            media=media,
            post_type=post_type
        )
        return redirect('feed')
    return render(request, 'posts/create.html')

@login_required
def delete_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.author == request.user:
        post.delete()
    return redirect(request.META.get('HTTP_REFERER', 'profile'))

# --- Лайки, Комментарии, Репосты ---
@login_required
def toggle_like_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author,
                sender=request.user,
                notification_type='like',
                post=post
            )
    return redirect(request.META.get('HTTP_REFERER', 'feed'))

@login_required
def add_comment_view(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        text = request.POST.get('text', '').strip()
        if text:
            Comment.objects.create(post=post, author=request.user, text=text)
            if post.author != request.user:
                Notification.objects.create(
                    recipient=post.author,
                    sender=request.user,
                    notification_type='comment',
                    post=post
                )
    return redirect(request.META.get('HTTP_REFERER', 'feed'))

@login_required
def repost_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    repost, created = Repost.objects.get_or_create(post=post, user=request.user)
    if not created:
        repost.delete()
    return redirect(request.META.get('HTTP_REFERER', 'feed'))

# --- Поиск и Уведомления ---
@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    users = []
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query)
        ).exclude(id=request.user.id)
    return render(request, 'posts/search.html', {'users': users, 'query': query})

@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'posts/notifications.html', {'notifications': notifications})

# --- Авторизация ---
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'feed')
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, 'posts/login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('feed')
    else:
        form = UserCreationForm()
    return render(request, 'posts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')