<h1>Описание проекта Foodgram</h1>

***

Foodgram это сайт для публикаций рецептов. Каждый зарегистрированный пользователь может публиковать свои рецепты, смотреть чужие рецепты, подписываться на интересных авторов, помещать рецепты в избранное, а так же можно собирать продуктовую корзину из ингредиентов понравившихся рецептов.

Сайт находится по адресу foodgram.ddnsking.com

Автор: Drag0nsigh https://github.com/Drag0nSigh

Стек: Python 3.9, Django 3.2, PyJWT 2.1.0, Rest, Postgres

***

<h2>Установка</h2>

<h3>Реализован автоматический деплой с использованием CD/CI через GitHub Actions, состоящий из следующтх этапов:</h3>

1. Проверка автоматическими тестами

2. Сборка Docker образов и их отправка в облачное хранилище Docker Hub
  
3. Развертывание Docker контейнеров на удаленном сервере

Из репозитория нажмите кнопку "Fork". Из своего аккаунта в репозитории зайдите в "Actions" и нажмите "Run workflow"


<h3>Локальное разворачивание с помощью Docker</h3>

Копирование репозитория

```
git clone https://github.com/Drag0nSigh/foodgram
```

Переход в рабочую папку

```
cd foodgram
```

Создайте файл .env, пример как его заполнять в файле env_exemple

```
nano .env
```

Создание образов Docker из локального кода

```
docker compose -f docker-compose_local.yml build
```

Запуск контейнеров Docker

```
docker compose -f docker-compose_local.yml up
```

Миграция базы данных

```
docker compose -f docker-compose_local.yml exec backend python manage.py makemigrations
docker compose -f docker-compose_local.yml exec backend python manage.py migrate
```

Сбор статики

```
docker compose -f docker-compose_local.yml exec backend python manage.py collectstatic --noinput
docker compose -f docker-compose_local.yml exec backend cp -r /app/collected_static/. /backend_static/static/
```

Создание супер пользователя

```
docker compose -f docker-compose_local.yml exec backend python manage.py createsuperuser
```

Загрузка тестовых данных (если требуется)

```
docker compose -f docker-compose_local.yml exec backend python manage.py load_tag
docker compose -f docker-compose_local.yml exec backend python manage.py load_ingredient
```


Документацию можно найти по адресу:

domain/api/docs/

<h3>Локальное разворачивание</h3>

Копирование репозитория

```
git clone https://github.com/Drag0nSigh/foodgram
```

Переход в рабочую папку

```
cd foodgram
```

Создайте файл .env, пример как его заполнять в файле env_exemple

Поменяйте в .env DEBUG=FALSE

```
nano .env
```

Создание виртуалього окружения

```
python -m venv venv
source venv/Scripts/activate
python -m pip install --upgrade pip
```

Установка зависимостей

```
pip install -r requirements.txt
```

Перейдите в папку backend

```
cd backend
```

Для работы локально добавьте в файл setting:

```
# backend/foodgram/settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
```

Миграция базы данных

```
python manage.py makemigrations
python manage.py migrate
```



Создание супер пользователя

```
python manage.py createsuperuser
```

Загрузка тестовых данных (если требуется)

```
python manage.py load_tag
python manage.py load_ingredient
```

Запустить backend:

```
python manage.py runserver
```

Для работы frontedn:

Перейти в папку 

```
cd frontend
```

Ecтановить Node.js 

```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
nvm install 17
nvm use 17
```

Установите зависимости

```
npm install
```

запустите

```
npm start
```

