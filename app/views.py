from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    Block,
    Bookmark,
    Comment,
    CreatorProfile,
    Follow,
    Message,
    Notification,
    Post,
    PostView,
    Profile,
    Report,
    Repost,
)


def _is_blocked(first, second):
    return Block.objects.filter(Q(blocker=first, blocked=second) | Q(blocker=second, blocked=first)).exists()


def _back(request, fallback='feed'):
    return redirect(request.META.get('HTTP_REFERER') or fallback)


@login_required
def feed_view(request):
    tab = request.GET.get('tab', 'for-you')
    posts = Post.objects.filter(parent__isnull=True).select_related(
        'author', 'author__profile', 'quote_post', 'quote_post__author'
    ).prefetch_related('likes', 'comments', 'replies').annotate(reply_count=Count('replies'))
    if request.user.is_authenticated:
        Profile.objects.get_or_create(user=request.user)
        CreatorProfile.objects.get_or_create(user=request.user)
        blocked_ids = Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
        posts = posts.exclude(author_id__in=blocked_ids)
        if tab == 'following':
            following = Follow.objects.filter(follower=request.user).values_list('user_id', flat=True)
            posts = posts.filter(Q(author_id__in=following) | Q(author=request.user))
    return render(request, 'posts/feed.html', {'posts': posts.order_by('-created_at'), 'active_tab': tab})


@login_required
def profile_view(request, username=None):
    profile_user = get_object_or_404(User, username=username) if username else request.user
    profile, _ = Profile.objects.get_or_create(user=profile_user)
    is_owner = request.user == profile_user
    is_following = Follow.objects.filter(user=profile_user, follower=request.user).exists()
    is_blocked = not is_owner and _is_blocked(request.user, profile_user)
    posts = Post.objects.filter(author=profile_user, parent__isnull=True).select_related('author').order_by('-created_at')
    if profile.is_private and not (is_owner or is_following):
        posts = Post.objects.none()
    return render(request, 'posts/profile.html', {
        'profile_user': profile_user, 'profile': profile, 'posts': posts,
        'is_owner': is_owner, 'is_following': is_following, 'is_blocked': is_blocked,
        'followers_count': profile_user.followers.count(), 'following_count': profile_user.following.count(),
    })


@login_required
def edit_profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '').strip()
        profile.is_private = request.POST.get('is_private') == 'on'
        profile.allow_messages = request.POST.get('allow_messages') == 'on'
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        profile.save()
        return redirect('profile')
    return render(request, 'posts/edit_profile.html', {'profile': profile})


@login_required
@require_POST
def toggle_follow_view(request, username):
    target = get_object_or_404(User, username=username)
    if target != request.user and not _is_blocked(request.user, target):
        follow, created = Follow.objects.get_or_create(user=target, follower=request.user)
        if created:
            Notification.objects.create(recipient=target, sender=request.user, notification_type='follow')
        else:
            follow.delete()
    return _back(request, 'profile')


@login_required
@require_POST
def toggle_block_view(request, username):
    target = get_object_or_404(User, username=username)
    if target != request.user:
        block, created = Block.objects.get_or_create(blocker=request.user, blocked=target)
        if created:
            Follow.objects.filter(Q(user=target, follower=request.user) | Q(user=request.user, follower=target)).delete()
        else:
            block.delete()
    return _back(request, 'profile')


@login_required
def direct_view(request, username=None):
    users = User.objects.filter(Q(followers__follower=request.user) | Q(following__user=request.user)).distinct()
    active = get_object_or_404(User, username=username) if username else None
    messages = []
    if active:
        profile, _ = Profile.objects.get_or_create(user=active)
        if _is_blocked(request.user, active) or (not profile.allow_messages and active != request.user):
            return HttpResponseForbidden('Этот пользователь не принимает сообщения.')
        if request.method == 'POST':
            text = request.POST.get('text', '').strip()
            if text:
                Message.objects.create(sender=request.user, recipient=active, text=text)
                return redirect('direct_dialog', username=active.username)
        messages = Message.objects.filter(Q(sender=request.user, recipient=active) | Q(sender=active, recipient=request.user)).order_by('created_at')
    return render(request, 'posts/direct.html', {'dialog_users': users, 'active_dialog_user': active, 'messages_list': messages})

@login_required
def reels_view(request):
    posts = Post.objects.filter(post_type='reels', parent__isnull=True).select_related('author').order_by('-created_at')
    return render(request, 'posts/reels.html', {'posts': posts})


@login_required
def create_post_view(request):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        media = request.FILES.get('media')
        post_type = request.POST.get('post_type', 'text')
        if post_type not in {'text', 'image', 'reels'}:
            post_type = 'text'
        if content or media:
            Post.objects.create(author=request.user, content=content, media=media, post_type=post_type)
        return redirect('feed')
    return render(request, 'posts/create.html')

@login_required
def post_detail_view(request, post_id):

    post = get_object_or_404(
        Post.objects.select_related(
            'author',
            'author__profile',
            'quote_post',
            'quote_post__author'
        ),
        id=post_id
    )

    root = post.parent or post

    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key

    PostView.objects.create(
        post=root,
        viewer=request.user if request.user.is_authenticated else None,
        session_key=session_key
    )

    replies = Post.objects.filter(
        parent=root
    ).select_related(
        'author',
        'author__profile'
    ).prefetch_related(
        'likes'
    ).order_by('created_at')

    return render(
        request,
        'posts/thread.html',
        {
            'post': root,
            'replies': replies
        }
    )

@login_required
@require_POST
def create_reply_view(request, post_id):
    parent = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '').strip()
    media = request.FILES.get('media')
    if content or media:
        Post.objects.create(author=request.user, parent=parent, content=content, media=media, post_type='image' if media else 'text')
        if parent.author != request.user:
            Notification.objects.create(recipient=parent.author, sender=request.user, notification_type='comment', post=parent)
    return redirect('post_detail', post_id=parent.id)


@login_required
def quote_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Post.objects.create(author=request.user, content=content, post_type='text', quote_post=post)
            return redirect('feed')
    return render(request, 'posts/quote.html', {'post': post})


@login_required
@require_POST
def delete_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.author == request.user:
        post.delete()
    return _back(request, 'profile')


@login_required
@require_POST
def toggle_like_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.likes.filter(id=request.user.id).exists():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True
        if post.author != request.user:
            Notification.objects.create(recipient=post.author, sender=request.user, notification_type='like', post=post)
    return JsonResponse({'success': True, 'is_liked': liked, 'likes_count': post.likes.count()})


@login_required
@require_POST
def toggle_bookmark_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, post=post)
    if not created:
        bookmark.delete()
    return JsonResponse({'success': True, 'is_bookmarked': created})


@login_required
def bookmarks_view(request):
    bookmarks = Bookmark.objects.filter(user=request.user).select_related('post', 'post__author')
    return render(request, 'posts/bookmarks.html', {'bookmarks': bookmarks})


@login_required
@require_POST
def add_comment_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    text = request.POST.get('text', '').strip()
    if text:
        Comment.objects.create(post=post, author=request.user, text=text)
        if post.author != request.user:
            Notification.objects.create(recipient=post.author, sender=request.user, notification_type='comment', post=post)
    return _back(request)


@login_required
@require_POST
def repost_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    repost, created = Repost.objects.get_or_create(post=post, user=request.user)
    if not created:
        repost.delete()
    return _back(request)


@login_required
@require_POST
def report_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    reason = request.POST.get('reason', 'other')
    if reason in dict(Report.REASONS):
        Report.objects.get_or_create(reporter=request.user, post=post, defaults={'reason': reason})
    return _back(request)


@login_required
def creator_view(request):
    creator, _ = CreatorProfile.objects.get_or_create(user=request.user)

    posts = Post.objects.filter(
        author=request.user,
        parent__isnull=True
    ).prefetch_related('likes')

    today = timezone.now().date()

    post_ids = posts.values_list('id', flat=True)

    today_views = PostView.objects.filter(
        post_id__in=post_ids,
        created_at__date=today
    ).count()

    total_views = PostView.objects.filter(
        post_id__in=post_ids
    ).count()

    reach = PostView.objects.filter(
        post_id__in=post_ids
    ).values(
        'viewer',
        'session_key'
    ).distinct().count()

  
    total_likes = sum(
        post.likes.count()
        for post in posts
    )

    
    total_replies = Post.objects.filter(
        parent__author=request.user
    ).count()

   
    total_comments = Comment.objects.filter(
        post__author=request.user
    ).count()

    
    total_reactions = total_likes + total_comments

  
    best_post = None

    for post in posts:
        views_count = post.views.count()

        if best_post is None or views_count > best_post['views']:
            best_post = {
                'post': post,
                'views': views_count
            }

    context = {
        'creator': creator,

        'posts_count': posts.count(),

        'today_views': today_views,

        'total_views': total_views,

        'reach': reach,

        'total_likes': total_likes,

        'total_comments': total_comments,

        'total_replies': total_replies,

        'total_reactions': total_reactions,

        'best_post': best_post,
    }

    return render(
        request,
        'posts/creator.html',
        context
    )


@login_required
@require_POST
def toggle_monetization_view(request):
    creator, _ = CreatorProfile.objects.get_or_create(user=request.user)
    creator.monetization_enabled = not creator.monetization_enabled
    creator.save(update_fields=['monetization_enabled'])
    return redirect('creator')

@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    users = User.objects.none()
    posts = Post.objects.none()
    if query:
        users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query))[:20]
        posts = Post.objects.filter(parent__isnull=True, content__icontains=query).select_related('author')[:30]
    return render(request, 'posts/search.html', {'users': users, 'posts': posts, 'query': query})


@login_required
def notifications_view(request):
    notifications = request.user.notifications.select_related('sender', 'post')
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'posts/notifications.html', {'notifications': notifications})


def login_view(request):
    if request.method == 'POST':

        action = request.POST.get('action')

        # ВХОД
        if action == 'login':
            form = AuthenticationForm(request, data=request.POST)

            if form.is_valid():
                login(request, form.get_user())
                return redirect(request.GET.get('next') or 'feed')

            return render(request, 'posts/login.html', {
                'form': form,
                'active_tab': 'login',
            })

        
        elif action == 'register':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            password_confirm = request.POST.get('password_confirm', '')

            if password != password_confirm:
                return render(request, 'posts/login.html', {
                    'error': 'Пароли не совпадают.',
                    'active_tab': 'register',
                })

            if User.objects.filter(username=username).exists():
                return render(request, 'posts/login.html', {
                    'error': 'Это имя пользователя уже занято.',
                    'active_tab': 'register',
                })

            if not username:
                return render(request, 'posts/login.html', {
                    'error': 'Введите имя пользователя.',
                    'active_tab': 'register',
                })

            if len(password) < 8:
                return render(request, 'posts/login.html', {
                    'error': 'Пароль должен содержать минимум 8 символов.',
                    'active_tab': 'register',
                })

            user = User.objects.create_user(
                username=username,
                password=password
            )

            Profile.objects.get_or_create(user=user)
            CreatorProfile.objects.get_or_create(user=user)

            login(request, user)

            return redirect('feed')

    return render(request, 'posts/login.html', {
        'active_tab': 'login'
    })


# def login_view(request):
#     form = AuthenticationForm(request, data=request.POST or None)
#     if request.method == 'POST' and form.is_valid():
#         login(request, form.get_user())
#         return redirect(request.GET.get('next') or 'feed')
#     return render(request, 'posts/login.html', {'form': form})


def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.get_or_create(user=user)
        CreatorProfile.objects.get_or_create(user=user)
        login(request, user)
        return redirect('feed')
    return render(request, 'posts/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')
