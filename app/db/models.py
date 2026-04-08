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
    display_name_ru = CharField(null=True)
    display_name_uk = CharField(null=True)
    description = TextField(null=True)
    description_ru = TextField(null=True)
    description_uk = TextField(null=True)
    system_prompt = TextField()
    main_photo_path = TextField(null=True)
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
    channel_bonus_granted = BooleanField(default=False)
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


class Gift(BaseModel):
    id = AutoField()
    slug = CharField(unique=True)
    title = CharField()
    description = TextField()
    stars_price = IntegerField()
    photo_path = TextField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)


class PremiumPhoto(BaseModel):
    id = AutoField()
    avatar = ForeignKeyField(Avatar, backref="premium_photos", on_delete="CASCADE")
    photo_path = TextField()
    description = TextField(default="")
    stars_price = IntegerField()
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)


class GiftPurchase(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="gift_purchases", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="gift_purchases", on_delete="CASCADE")
    gift = ForeignKeyField(Gift, backref="purchases", on_delete="CASCADE")
    telegram_payment_charge_id = CharField(unique=True)
    provider_payment_charge_id = CharField(null=True)
    stars_amount = IntegerField()
    rewarded_premium_photo = ForeignKeyField(PremiumPhoto, null=True, backref="gift_rewards", on_delete="SET NULL")
    status = CharField(default="paid")
    created_at = DateTimeField(default=datetime.utcnow)


class PremiumPhotoPurchase(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="premium_photo_purchases", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="premium_photo_purchases", on_delete="CASCADE")
    premium_photo = ForeignKeyField(PremiumPhoto, backref="purchases", on_delete="CASCADE")
    telegram_payment_charge_id = CharField(unique=True)
    provider_payment_charge_id = CharField(null=True)
    stars_amount = IntegerField()
    status = CharField(default="paid")
    created_at = DateTimeField(default=datetime.utcnow)


class CustomContentRequest(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="custom_requests", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, backref="custom_requests", on_delete="CASCADE")
    media_type = CharField()
    description = TextField()
    stars_price = IntegerField()
    status = CharField(default="pending")
    fulfilled_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)


class CustomContentDelivery(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="custom_deliveries", on_delete="CASCADE")
    avatar = ForeignKeyField(Avatar, null=True, backref="custom_deliveries", on_delete="SET NULL")
    request = ForeignKeyField(CustomContentRequest, null=True, backref="deliveries", on_delete="SET NULL")
    media_type = CharField()
    description = TextField(default="")
    caption_text = TextField(default="")
    stars_price = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)


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
    Gift,
    PremiumPhoto,
    GiftPurchase,
    PremiumPhotoPurchase,
    CustomContentRequest,
    CustomContentDelivery,
)
