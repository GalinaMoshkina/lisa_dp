# Digital Parallels: локальный запуск

## Запустить сайт, API и двух Telegram-ботов

Из корня проекта:

```bash
./work/start_all.sh
```

Скрипт запускает:

- Hash API: `work/hash_service_api/app.py`
- сайт: `http://127.0.0.1:8080`
- бот публикации материалов: `work/tgbot/bot.py`
- бот первого этапа регистрации: `work/discussion_bot/bot.py`

## Остановить все

```bash
./work/stop_all.sh
```

## Сайт отдельно

Если не нужен общий запуск, сайт можно открыть файлом:

```text
work/web_w/index.html
```

Если Hash API запущен, сайт покажет статус сервиса фиксации и последние SHA256-записи.

Порт сайта в общем запуске можно изменить так:

```bash
WEB_PORT=8081 ./work/start_all.sh
```

## Логи

После запуска логи лежат здесь:

```text
work/runtime/logs/
```

PID-файлы процессов:

```text
work/runtime/pids/
```

Если какой-то сервис не запустился, сначала смотрите соответствующий лог в `work/runtime/logs/`.
