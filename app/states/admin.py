from aiogram.fsm.state import State, StatesGroup


class AdminAvatarUploadState(StatesGroup):
    selecting_upload_target = State()
