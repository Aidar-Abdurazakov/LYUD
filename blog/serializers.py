from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Comment, Post

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username')
        read_only_fields = ('id', 'username')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        read_only_fields = ('id',)

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    comments_count = serializers.SerializerMethodField(help_text='Количество одобренных комментариев')

    class Meta:
        model = Post
        fields = (
            'id', 'author', 'title', 'body', 'is_published',
            'created_at', 'updated_at', 'comments_count',
        )
        read_only_fields = ('id', 'author', 'created_at', 'updated_at', 'comments_count')

    def get_comments_count(self, obj) -> int:
        count = getattr(obj, 'approved_comments_count', None)
        if count is None:
            count = obj.comments.filter(is_approved=True).count()
        return count


class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'post', 'author', 'body', 'is_approved', 'created_at', 'updated_at')
        read_only_fields = ('id', 'post', 'author', 'is_approved', 'created_at', 'updated_at')
