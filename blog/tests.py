from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Comment, Post

User = get_user_model()
PASSWORD = 'StrongPass123!'


class BlogApiTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('alice', password=PASSWORD)
        cls.bob = User.objects.create_user('bob', password=PASSWORD)
        cls.post = Post.objects.create(author=cls.alice, title='Привет', body='Первый пост')
        cls.draft = Post.objects.create(author=cls.alice, title='Черновик', body='Секрет', is_published=False)

    def login(self, username):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': username, 'password': PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])


    def test_register_and_get_token(self):
        response = self.client.post(
            reverse('register'),
            {'username': 'carol', 'password': PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        self.login('carol')

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse('register'),
            {'username': 'dave', 'password': '12345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_guest_sees_only_published_posts(self):
        response = self.client.get(reverse('post-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.post.id)

    def test_guest_cannot_open_draft(self):
        response = self.client.get(reverse('post-detail', args=[self.draft.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_author_sees_own_draft_but_others_do_not(self):
        self.login('alice')
        self.assertEqual(self.client.get(reverse('post-detail', args=[self.draft.id])).status_code, 200)
        self.login('bob')
        self.assertEqual(self.client.get(reverse('post-detail', args=[self.draft.id])).status_code, 404)

    def test_pagination(self):
        for i in range(12):
            Post.objects.create(author=self.alice, title=f'Пост {i}', body='...')
        response = self.client.get(reverse('post-list'), {'page_size': 5})
        self.assertEqual(len(response.data['results']), 5)
        self.assertIsNotNone(response.data['next'])

    def test_guest_cannot_create_post(self):
        response = self.client.post(reverse('post-list'), {'title': 'X', 'body': 'Y'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_post_sets_current_user_as_author(self):
        self.login('bob')
        response = self.client.post(reverse('post-list'), {'title': 'Мой пост', 'body': 'Текст'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author']['username'], 'bob')
        self.assertTrue(Post.objects.filter(title='Мой пост', author=self.bob).exists())

    def test_create_post_ignores_author_from_request(self):
        self.login('bob')
        response = self.client.post(
            reverse('post-list'),
            {'title': 'Подмена', 'body': 'Текст', 'author': self.alice.id},
            format='json',
        )
        self.assertEqual(response.data['author']['username'], 'bob')

    def test_only_author_can_update_post(self):
        url = reverse('post-detail', args=[self.post.id])
        payload = {'title': 'Новый', 'body': 'Новый текст', 'is_published': True}

        self.login('bob')
        self.assertEqual(self.client.put(url, payload, format='json').status_code, status.HTTP_403_FORBIDDEN)

        self.login('alice')
        response = self.client.put(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Новый')

    def test_only_author_can_delete_post(self):
        url = reverse('post-detail', args=[self.post.id])

        self.login('bob')
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

        self.login('alice')
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())


    def test_guest_can_read_comments(self):
        Comment.objects.create(post=self.post, author=self.bob, body='Класс!')
        response = self.client.get(reverse('post-comments', args=[self.post.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_guest_cannot_add_comment(self):
        response = self.client.post(reverse('post-comments', args=[self.post.id]), {'body': 'Привет'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_user_can_add_comment(self):
        self.login('bob')
        response = self.client.post(reverse('post-comments', args=[self.post.id]), {'body': 'Отлично'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author']['username'], 'bob')
        self.assertEqual(response.data['post'], self.post.id)

    def test_cannot_comment_on_foreign_draft(self):
        self.login('bob')
        response = self.client.post(reverse('post-comments', args=[self.draft.id]), {'body': 'Эй'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_only_author_can_change_or_delete_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.bob, body='Мой комментарий')
        url = reverse('comment-detail', args=[comment.id])

        self.login('alice')
        self.assertEqual(self.client.patch(url, {'body': 'Взлом'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

        self.login('bob')
        self.assertEqual(self.client.patch(url, {'body': 'Правка'}, format='json').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)

    @override_settings(BLOG_COMMENTS_REQUIRE_APPROVAL=True)
    def test_comment_waits_for_moderation_when_enabled(self):
        self.login('bob')
        self.client.post(reverse('post-comments', args=[self.post.id]), {'body': 'На проверке'}, format='json')

        self.assertEqual(self.client.get(reverse('post-comments', args=[self.post.id])).data['count'], 1)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse('post-comments', args=[self.post.id])).data['count'], 0)
