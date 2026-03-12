# AdultChatBot

Telegram bot scaffold on `aiogram`, `langchain`, `sqlite`, `peewee`, and `python-dotenv`.

## Features

- mandatory subscription gate for required channels;
- avatar selection with active/inactive flag;
- one language shared by bot UI and companion replies;
- free limit of 10 avatar replies, then payment in Telegram Stars;
- plans by bot reply quota: 50 / 100 / 500;
- rolling memory: summary + last 10 messages;
- avatar photo storage in `assets/avatars/<avatar_id>/photos`;
- admin commands for channels, avatars, stats, and database export.

## Quick start

```bash
cp .env.example .env
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.bot
```

## Admin commands

- `/admin`
- `/add_avatar slug | name | description | system_prompt`
- send photo with caption `avatar:<avatar_id>`
- send zip with caption `avatar_zip:<avatar_id>`
- `/add_channel chat_id | title | link | is_private(0/1) | requires_join_request(0/1)`
