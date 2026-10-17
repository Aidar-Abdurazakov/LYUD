# LYUD: соцсеть и REST API блога

Проект состоит из двух независимых частей на одном Django-проекте:

- **Сайт LYUD** (приложение `app`): лента, профили, reels, direct и т. д. Работает как раньше по адресу `/`.
- **REST API блога** (приложение `blog`): посты и комментарии, JWT-аутентификация, документация Swagger. Адрес `/api/v1/`.

API использует встроенную модель `User` Django, но свои модели `Post` и `Comment`, поэтому на данные и работу сайта не влияет.

## Стек

Python 3.9+, Django 4.2, Django REST Framework, SimpleJWT, drf-spectacular (Swagger/ReDoc), SQLite по умолчанию или PostgreSQL.

## Как запустить

```bash
# 1. Виртуальное окружение
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Зависимости
pip install -r requirements.txt

# 3. Миграции (создают таблицы блога, миграции уже лежат в blog/migrations)
python manage.py migrate

# 4. Администратор (по желанию, для /admin/)
python manage.py createsuperuser

# 5. Запуск
python manage.py runserver
```

После запуска:

| Что | Адрес |
|---|---|
| Сайт LYUD | http://127.0.0.1:8000/ |
| Swagger UI | http://127.0.0.1:8000/api/docs/ |
| ReDoc | http://127.0.0.1:8000/api/redoc/ |
| OpenAPI-схема (YAML) | http://127.0.0.1:8000/api/schema/ |
| Админка | http://127.0.0.1:8000/admin/ |

### Запуск на PostgreSQL (бонус)

```bash
docker compose up -d db                       # поднимает PostgreSQL 16
pip install -r requirements-postgres.txt      # добавляет драйвер psycopg2

export POSTGRES_DB=blog POSTGRES_USER=blog POSTGRES_PASSWORD=blog POSTGRES_HOST=127.0.0.1

python manage.py migrate
python manage.py runserver
```

Если `POSTGRES_DB` не задана, проект использует SQLite (`db.sqlite3`). База PostgreSQL создаётся пустой: данные из SQLite не переносятся.

### Тесты

```bash
python manage.py test blog
```

## Эндпоинты

Базовый адрес: `/api/v1/`

| Метод | URL | Описание | Доступ |
|---|---|---|---|
| POST | `auth/register/` | Регистрация | все |
| POST | `auth/token/` | Получить `access` и `refresh` токены | все |
| POST | `auth/token/refresh/` | Обновить `access` по `refresh` | все |
| GET | `posts/` | Список постов (пагинация) | все |
| POST | `posts/` | Создать пост (автор: текущий пользователь) | авторизованные |
| GET | `posts/{id}/` | Один пост | все |
| PUT, PATCH | `posts/{id}/` | Изменить пост | только автор |
| DELETE | `posts/{id}/` | Удалить пост | только автор |
| GET | `posts/{id}/comments/` | Список комментариев поста | все |
| POST | `posts/{id}/comments/` | Добавить комментарий | авторизованные |
| GET | `comments/{id}/` | Один комментарий | все |
| PUT, PATCH, DELETE | `comments/{id}/` | Изменить или удалить комментарий | только автор |

### Правила доступа

- Гости только читают **опубликованные** посты (`is_published=true`).
- Авторизованный пользователь дополнительно видит **свои черновики**. Чужие черновики для всех, кроме автора, возвращают 404.
- Менять и удалять посты и комментарии может только их автор (иначе 403).
- Без токена запись возвращает 401.
- Автор подставляется автоматически из токена, передать чужого автора нельзя.

### Пагинация

Ответ списка: `{"count": ..., "next": ..., "previous": ..., "results": [...]}`.
Параметры: `?page=2&page_size=5` (по умолчанию 10, максимум 100).

### Комментарии и модерация

Поле `is_approved` по умолчанию `true`: комментарий виден сразу. Чтобы включить премодерацию, задайте `BLOG_COMMENTS_REQUIRE_APPROVAL=True`: новые комментарии будут скрыты (автор видит свой), пока админ не одобрит их в `/admin/` (действие «Одобрить выбранные комментарии»).

## Пример работы через curl

```bash
# Регистрация
curl -X POST http://127.0.0.1:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "StrongPass123!"}'

# Токен (в ответе поля access и refresh)
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "StrongPass123!"}'

# Создать пост (вставьте свой access вместо <ACCESS>)
curl -X POST http://127.0.0.1:8000/api/v1/posts/ \
  -H "Authorization: Bearer <ACCESS>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Привет", "body": "Мой первый пост"}'

# Список постов (без токена)
curl http://127.0.0.1:8000/api/v1/posts/

# Добавить комментарий к посту 1
curl -X POST http://127.0.0.1:8000/api/v1/posts/1/comments/ \
  -H "Authorization: Bearer <ACCESS>" \
  -H "Content-Type: application/json" \
  -d '{"body": "Отличный пост!"}'
```

В Swagger UI нажмите **Authorize** и вставьте `access`-токен (без слова Bearer), после этого можно пробовать все запросы прямо из браузера.

## Структура

```
LYUD/                  настройки проекта и корневые urls
app/                   сайт-соцсеть (не менялся)
blog/                  REST API блога
  models.py            Post, Comment
  serializers.py       сериализаторы
  views.py             ViewSet для постов, вьюхи комментариев и регистрации
  permissions.py       IsAuthorOrReadOnly
  pagination.py        пагинация
  urls.py              маршруты /api/v1/
  admin.py             админка и модерация комментариев
  migrations/          миграции
  tests.py             тесты API
```

## Переменные окружения (необязательно)

Все значения по умолчанию сохраняют прежнее поведение проекта. Полный список см. в `.env.example`:
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `POSTGRES_*`, `BLOG_COMMENTS_REQUIRE_APPROVAL`.
