# AdultChatBot

Telegram bot scaffold on `aiogram`, `langchain`, `langchain-xai`, `sqlite`, `peewee`, and `python-dotenv`, using xAI models.

## Features

- mandatory subscription gate for required channels;
- avatar cards with main photo, description and left/right navigation;
- avatar selection with active/inactive flag;
- one language shared by bot UI and companion replies;
- free limit of 10 avatar replies, then payment in Telegram Stars;
- plans by bot reply quota: 50 / 100 / 500;
- premium photos as separate paid items in Stars, offered by the agent as blurred paid media;
- custom gifts in Stars with optional premium-photo reward when the gift value covers a photo;
- rolling memory: summary + last 10 messages;
- avatar storage in `assets/avatars/<avatar_id>/main.jpg` and `photos/`;
- premium photos stored as separate DB records with `avatar_id`, `photo_path`, and `stars_price`;
- FSM admin flow for avatar creation and editing;
- admin sections for avatar management, gift management, inline statistics, channels, and database export.

## Quick start

```bash
cp .env.example .env
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.bot
```

## Docker

```bash
docker compose up -d --build
```

Persistent data is stored in Docker volumes:

- `bot_data` -> `/app/data`
- `bot_assets` -> `/app/assets`

This means the SQLite database and uploaded avatar media survive container restarts.

## Admin commands

- `/admin`
- `/use_avatar <avatar_id>` to set current upload target
- `/clear_avatar_context`
- `/add_channel chat_id | title | link | is_private(0/1) | requires_join_request(0/1)`

## Admin flow

- Open `/admin`
- Go to `Avatars`
- Press `Add avatar`
- Complete FSM steps: slug -> name -> description -> system prompt -> main photo or `Skip`
- Then upload `lite` photos, then `premium` photos
- `lite` supports photos, `.zip`, `Skip`, or `Done`
- `premium` supports one-by-one photo upload with per-photo price
- After setup, default upload target is `lite` photos
- Press `Edit avatars` to update main photo, description, system prompt, or switch upload mode to `Upload lite photos` / `Upload premium photos`

## Gifts

- Open `/admin`
- Go to `Gifts`
- Press `Add gift`
- Complete FSM steps: slug -> title -> description -> price -> photo or `Skip`
- Press `Edit gifts` to update photo, title, description, price, or active status
- Users can open `Send gift`, choose a gift, and pay in Stars
- If gift price covers at least one unseen premium photo for the selected avatar, the bot sends the best affordable one

## Premium Photos

- The agent can send a free lite photo normally
- The agent can also offer one unseen premium photo as native Telegram blurred paid media
- Before sending the paid media, the bot generates an in-character waiting message
- The bot waits 20-40 seconds, then sends the blurred paid media without caption
- Gift rewards use the same delayed delivery, but with a thankful in-character message first
