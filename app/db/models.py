from __future__ import annotations

from datetime import datetime

from peewee import (
    AutoField,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from app.db.base import database


class BaseModel(Model):
    class Meta:
        database = database


class User(BaseModel):
    id = AutoField()
    telegram_id = BigIntegerField(unique=True, index=True)
    username = CharField(null=True)
    first_name = CharField(null=True)
    language_code = CharField(default="en")
    is_admin = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    last_seen_at = DateTimeField(default=datetime.utcnow)


class Channel(BaseModel):
    id = AutoField()
    telegram_channel_id = BigIntegerField(unique=True)
    title = CharField()
    username_or_invite_link = CharField(null=True)
    is_private = BooleanField(default=False)
    requires_join_request = BooleanField(default=False)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)


class Avatar(BaseModel):
    id = AutoField()
    slug = CharField(unique=True)
    display_name = CharField()
    description = TextField(null=True)
    system_prompt = TextField()
    is_active = BooleanField(default=True)
    sort_order = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)


class UserProfile(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="profiles", unique=True, on_delete="CASCADE")
    selected_avatar = ForeignKeyField(Avatar, null=True, backref="user_profiles", on_delete="SET NULL")
    language = CharField(default="en")
    paid_message_balance = IntegerField(default=0)
    free_messages_used = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)


class DialogMessage(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="dialog_messages", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="dialog_messages", on_delete="CASCADE")
    role = CharField()
    content = TextField()
    created_at = DateTimeField(default=datetime.utcnow)


class DialogMemory(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="memories", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="memories", on_delete="CASCADE")
    rolling_summary = TextField(default="")
    last_compacted_message_id = IntegerField(default=0)
    updated_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = ((("user", "avatar"), True),)


class Payment(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="payments", on_delete="CASCADE")
    plan_code = CharField()
    message_quota = IntegerField()
    stars_amount = IntegerField()
    telegram_payment_charge_id = CharField(unique=True)
    provider_payment_charge_id = CharField(null=True)
    status = CharField(default="pending")
    created_at = DateTimeField(default=datetime.utcnow)


class PhotoSendHistory(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="photo_history", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="photo_history", on_delete="CASCADE")
    photo_path = TextField()
    sent_at = DateTimeField(default=datetime.utcnow)


class ChannelJoinRequest(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="channel_join_requests", on_delete="CASCADE")
    channel = ForeignKeyField(Channel, backref="join_requests", on_delete="CASCADE")
    status = CharField(default="pending")
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = ((("user", "channel"), True),)


MODELS = (
    User,
    Channel,
    Avatar,
    UserProfile,
    DialogMessage,
    DialogMemory,
    Payment,
    PhotoSendHistory,
    ChannelJoinRequest,
)
