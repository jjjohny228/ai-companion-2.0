from __future__ import annotations

from app.constants import LANGUAGES, SUBSCRIPTION_PLANS


TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "Welcome! Before chatting, please subscribe to all required channels.",
        "check_subscription": "Check subscription",
        "subscription_required": "You need to subscribe to all required channels to continue.",
        "choose_language": "Choose your language.",
        "choose_avatar": "Choose an avatar for chatting.",
        "main_menu": "Main menu",
        "language_updated": "Language updated.",
        "avatar_selected": "Avatar selected. You can start chatting.",
        "no_avatar_selected": "Please choose an avatar first.",
        "free_limit_reached": "Your free limit is over. Choose a subscription plan to continue.",
        "subscription_ok": "Subscription check passed.",
        "subscription_missing": "I still can't confirm the required subscriptions.",
        "menu_chat": "Chat",
        "menu_avatar": "Change avatar",
        "menu_language": "Language",
        "menu_subscription": "Messages",
        "menu_gift": "Send gift",
        "admin_menu": "Admin menu",
        "stats_empty": "No stats yet.",
        "gift_no_photos": "No new photos are available for this avatar right now.",
        "gift_choose": "Choose a gift.",
        "gift_success": "Gift sent successfully.",
        "gift_locked": "This gift does not unlock a premium photo.",
    },
    "ru": {
        "welcome": "Привет! Перед началом общения подпишитесь на все обязательные каналы.",
        "check_subscription": "Проверить подписку",
        "subscription_required": "Чтобы продолжить, нужно подписаться на все обязательные каналы.",
        "choose_language": "Выберите язык.",
        "choose_avatar": "Выберите аватара для общения.",
        "main_menu": "Главное меню",
        "language_updated": "Язык обновлен.",
        "avatar_selected": "Аватар выбран. Можно начинать общение.",
        "no_avatar_selected": "Сначала выберите аватара.",
        "free_limit_reached": "Бесплатный лимит закончился. Выберите тариф, чтобы продолжить.",
        "subscription_ok": "Проверка подписки пройдена.",
        "subscription_missing": "Пока не удалось подтвердить обязательные подписки.",
        "menu_chat": "Чат",
        "menu_avatar": "Сменить аватара",
        "menu_language": "Язык",
        "menu_subscription": "Сообщения",
        "menu_gift": "Подарок",
        "admin_menu": "Админ меню",
        "stats_empty": "Статистики пока нет.",
        "gift_no_photos": "Для этого аватара пока нет новых фото.",
        "gift_choose": "Выберите подарок.",
        "gift_success": "Подарок успешно отправлен.",
        "gift_locked": "Этот подарок не открывает премиум фото.",
    },
    "uk": {
        "welcome": "Привiт! Перед початком спiлкування пiдпишiться на всi обов'язковi канали.",
        "check_subscription": "Перевiрити пiдписку",
        "subscription_required": "Щоб продовжити, потрiбно пiдписатися на всi обов'язковi канали.",
        "choose_language": "Оберiть мову.",
        "choose_avatar": "Оберiть аватара для спiлкування.",
        "main_menu": "Головне меню",
        "language_updated": "Мову оновлено.",
        "avatar_selected": "Аватара обрано. Можна починати спiлкування.",
        "no_avatar_selected": "Спочатку оберiть аватара.",
        "free_limit_reached": "Безкоштовний лiмiт завершився. Оберiть тариф, щоб продовжити.",
        "subscription_ok": "Перевiрку пiдписки пройдено.",
        "subscription_missing": "Поки не вдалося пiдтвердити обов'язковi пiдписки.",
        "menu_chat": "Чат",
        "menu_avatar": "Змiнити аватара",
        "menu_language": "Мова",
        "menu_subscription": "Повiдомлення",
        "menu_gift": "Подарунок",
        "admin_menu": "Адмін меню",
        "stats_empty": "Статистики поки немає.",
        "gift_no_photos": "Для цього аватара поки немає нових фото.",
        "gift_choose": "Оберiть подарунок.",
        "gift_success": "Подарунок успiшно вiдправлено.",
        "gift_locked": "Цей подарунок не вiдкриває премiум фото.",
    },
}


def tr(language: str, key: str) -> str:
    return TEXTS.get(language, TEXTS["en"]).get(key, key)


def format_channels_message(language: str, channel_links: list[str]) -> str:
    intro = tr(language, "welcome")
    if not channel_links:
        return intro
    return "\n".join([intro, "", *channel_links])


def format_plans(language: str, available_messages: int) -> str:
    header = {
        "en": "Choose a plan:",
        "ru": "Выберите тариф:",
        "uk": "Оберiть тариф:",
    }.get(language, "Choose a plan:")
    available_label = {
        "en": f"Available messages: {available_messages}",
        "ru": f"Доступно сообщений: {available_messages}",
        "uk": f"Доступно повiдомлень: {available_messages}",
    }.get(language, f"Available messages: {available_messages}")
    rows = [available_label, "", header]
    return "\n".join(rows)


def available_languages_text() -> str:
    return "\n".join(LANGUAGES.values())
