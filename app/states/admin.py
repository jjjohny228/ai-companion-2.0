from aiogram.fsm.state import State, StatesGroup


class AdminAvatarUploadState(StatesGroup):
    selecting_upload_target = State()


class AdminAvatarCreateState(StatesGroup):
    waiting_slug = State()
    waiting_name = State()
    waiting_description = State()
    waiting_system_prompt = State()
    waiting_main_photo = State()
    waiting_lite_media = State()
    waiting_premium_media = State()


class AdminAvatarEditState(StatesGroup):
    waiting_avatar_id = State()
    waiting_field = State()
    waiting_value = State()


class AdminPremiumPhotoState(StatesGroup):
    waiting_price = State()


class AdminGiftCreateState(StatesGroup):
    waiting_slug = State()
    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_photo = State()


class AdminGiftEditState(StatesGroup):
    waiting_value = State()
