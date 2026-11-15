"""SQLAlchemy models + DB helpers for TextLink."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, create_engine, select, func, or_, and_
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, scoped_session

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
if not DATABASE_URL:
    os.makedirs('data', exist_ok=True)
    DATABASE_URL = 'sqlite:///data/textlink.db'

connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = 'users'

    username = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    profile_picture = Column(String(512), nullable=True)  # URL path or legacy data URL
    bio = Column(Text, default='')
    interests = Column(Text, default='')
    relationship_status = Column(String(64), default='Open')
    theme = Column(String(32), default='default')
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(Text, default='')
    email_verified = Column(Boolean, default=False)
    email_on_message = Column(Boolean, default=True)
    email_on_request = Column(Boolean, default=True)
    email_on_like = Column(Boolean, default=False)
    email_on_follow = Column(Boolean, default=False)
    email_on_gift = Column(Boolean, default=True)
    premium_until = Column(DateTime(timezone=True), nullable=True)
    boost_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def _aware(self, dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def is_premium_active(self):
        until = self._aware(self.premium_until)
        return bool(until and until > utcnow())

    def is_boosted(self):
        until = self._aware(self.boost_until)
        return bool(until and until > utcnow())

    def public_dict(self):
        return {
            'username': self.username,
            'profile_picture': self.profile_picture,
            'bio': self.bio or '',
            'interests': self.interests or '',
            'relationship_status': self.relationship_status or 'Open',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_premium': self.is_premium_active(),
            'is_boosted': self.is_boosted(),
            'premium_until': self._aware(self.premium_until).isoformat() if self.premium_until else None,
            'boost_until': self._aware(self.boost_until).isoformat() if self.boost_until else None,
        }

    def private_dict(self):
        d = self.public_dict()
        d.update({
            'email': self.email,
            'is_admin': bool(self.is_admin),
            'email_verified': bool(self.email_verified),
            'theme': self.theme or 'default',
            'is_banned': bool(self.is_banned),
        })
        return d


class AuthToken(Base):
    __tablename__ = 'auth_tokens'

    id = Column(String(36), primary_key=True, default=new_id)
    username = Column(String(64), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    purpose = Column(String(32), nullable=False)  # verify_email | reset_password
    created_at = Column(DateTime(timezone=True), default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)


class ConnectionRequest(Base):
    __tablename__ = 'connection_requests'

    id = Column(String(36), primary_key=True, default=new_id)
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    message = Column(Text, default='')
    status = Column(String(16), default='pending')  # pending|accepted|rejected
    response_message = Column(Text, default='')
    sent_at = Column(DateTime(timezone=True), default=utcnow)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'from': self.from_user,
            'to': self.to_user,
            'message': self.message or '',
            'status': self.status,
            'response_message': self.response_message or '',
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }


class Message(Base):
    __tablename__ = 'messages'

    id = Column(String(36), primary_key=True, default=new_id)
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    msg_type = Column(String(16), default='text')  # text|image|gift
    gift_id = Column(Integer, nullable=True)
    order_id = Column(String(36), nullable=True)
    read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'from': self.from_user,
            'to': self.to_user,
            'content': self.content,
            'type': self.msg_type,
            'gift_id': self.gift_id,
            'order_id': self.order_id,
            'read': bool(self.read),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
        }


class Card(Base):
    __tablename__ = 'cards'

    id = Column(String(36), primary_key=True, default=new_id)
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    template_id = Column(Integer, nullable=True)
    message = Column(Text, default='')
    viewed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'from': self.from_user,
            'to': self.to_user,
            'template_id': self.template_id,
            'message': self.message or '',
            'viewed': bool(self.viewed),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Follow(Base):
    __tablename__ = 'follows'

    id = Column(String(36), primary_key=True, default=new_id)
    follower = Column(String(64), nullable=False, index=True)
    following = Column(String(64), nullable=False, index=True)
    followed_at = Column(DateTime(timezone=True), default=utcnow)


class Like(Base):
    __tablename__ = 'likes'

    id = Column(String(36), primary_key=True, default=new_id)
    user = Column(String(64), nullable=False, index=True)
    likes_username = Column(String(64), nullable=False, index=True)
    liked_at = Column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(String(36), primary_key=True, default=new_id)
    to_user = Column(String(64), nullable=False, index=True)
    from_user = Column(String(64), nullable=True)
    notif_type = Column(String(32), default='info')
    message = Column(Text, default='')
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'to': self.to_user,
            'from': self.from_user,
            'type': self.notif_type,
            'message': self.message,
            'read': bool(self.read),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Block(Base):
    __tablename__ = 'blocks'

    id = Column(String(36), primary_key=True, default=new_id)
    blocker = Column(String(64), nullable=False, index=True)
    blocked = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = 'reports'

    id = Column(String(36), primary_key=True, default=new_id)
    reporter = Column(String(64), nullable=False)
    reported = Column(String(64), nullable=False, index=True)
    reason = Column(Text, default='')
    message = Column(Text, default='')
    status = Column(String(16), default='open')  # open|resolved|dismissed
    admin_note = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(64), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'reporter': self.reporter,
            'reported': self.reported,
            'reason': self.reason,
            'message': self.message,
            'status': self.status,
            'admin_note': self.admin_note or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
        }


class Order(Base):
    __tablename__ = 'orders'

    id = Column(String(36), primary_key=True, default=new_id)
    gift_id = Column(Integer, nullable=False)
    gift_name = Column(String(128), default='')
    price_cents = Column(Integer, nullable=False)
    currency = Column(String(8), default='usd')
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    message = Column(Text, default='')
    status = Column(String(16), default='pending')  # pending|paid|cancelled|refunded|error
    delivered = Column(Boolean, default=False)
    payment_mode = Column(String(16), default='stripe')
    stripe_session_id = Column(String(255), nullable=True, index=True)
    stripe_payment_intent = Column(String(255), nullable=True)
    stripe_refund_id = Column(String(255), nullable=True)
    error = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), default=utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'gift_id': self.gift_id,
            'gift_name': self.gift_name,
            'price_cents': self.price_cents,
            'currency': self.currency,
            'from': self.from_user,
            'to': self.to_user,
            'message': self.message or '',
            'status': self.status,
            'delivered': bool(self.delivered),
            'payment_mode': self.payment_mode,
            'stripe_session_id': self.stripe_session_id,
            'stripe_payment_intent': self.stripe_payment_intent,
            'stripe_refund_id': self.stripe_refund_id,
            'error': self.error or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
        }


class GiftSent(Base):
    __tablename__ = 'gifts_sent'

    id = Column(String(36), primary_key=True, default=new_id)
    order_id = Column(String(36), nullable=False, index=True)
    gift_id = Column(Integer, nullable=False)
    gift_name = Column(String(128), default='')
    gift_emoji = Column(String(16), default='')
    price_cents = Column(Integer, default=0)
    currency = Column(String(8), default='usd')
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    message = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'gift_id': self.gift_id,
            'gift_name': self.gift_name,
            'gift_emoji': self.gift_emoji,
            'price_cents': self.price_cents,
            'currency': self.currency,
            'from': self.from_user,
            'to': self.to_user,
            'message': self.message or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserAnalytics(Base):
    __tablename__ = 'user_analytics'

    username = Column(String(64), primary_key=True)
    page_views = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    follows = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    requests_sent = Column(Integer, default=0)
    gifts_sent = Column(Integer, default=0)
    gifts_bought = Column(Integer, default=0)

    def to_dict(self):
        return {
            'page_views': self.page_views or 0,
            'messages_sent': self.messages_sent or 0,
            'follows': self.follows or 0,
            'likes': self.likes or 0,
            'requests_sent': self.requests_sent or 0,
            'gifts_sent': self.gifts_sent or 0,
            'gifts_bought': self.gifts_bought or 0,
        }


class PlatformSettings(Base):
    """Singleton row (id=1) controlling how the admin earns money."""
    __tablename__ = 'platform_settings'

    id = Column(Integer, primary_key=True, default=1)
    monetization_enabled = Column(Boolean, default=True)
    premium_price_cents = Column(Integer, default=999)       # $9.99 / period
    premium_days = Column(Integer, default=30)
    boost_price_cents = Column(Integer, default=499)         # $4.99
    boost_days = Column(Integer, default=7)
    premium_gift_discount_percent = Column(Integer, default=10)  # Premium users save on gifts
    currency = Column(String(8), default='usd')
    payout_note = Column(Text, default='Money is collected in your Stripe account. Withdraw from Stripe Dashboard → Balances → Payouts.')
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            'monetization_enabled': bool(self.monetization_enabled),
            'premium_price_cents': self.premium_price_cents or 0,
            'premium_days': self.premium_days or 30,
            'boost_price_cents': self.boost_price_cents or 0,
            'boost_days': self.boost_days or 7,
            'premium_gift_discount_percent': self.premium_gift_discount_percent or 0,
            'currency': (self.currency or 'usd').upper(),
            'payout_note': self.payout_note or '',
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PlatformPayment(Base):
    """Ledger of every dollar that belongs to the admin/platform."""
    __tablename__ = 'platform_payments'

    id = Column(String(36), primary_key=True, default=new_id)
    kind = Column(String(32), nullable=False, index=True)  # gift | premium | boost
    username = Column(String(64), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(8), default='usd')
    status = Column(String(16), default='pending')  # pending|paid|refunded|cancelled
    description = Column(Text, default='')
    reference_id = Column(String(64), nullable=True, index=True)  # order id etc.
    stripe_session_id = Column(String(255), nullable=True, index=True)
    stripe_payment_intent = Column(String(255), nullable=True)
    stripe_refund_id = Column(String(255), nullable=True)
    meta_json = Column(Text, default='{}')
    created_at = Column(DateTime(timezone=True), default=utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        meta = {}
        try:
            meta = json.loads(self.meta_json or '{}')
        except Exception:
            meta = {}
        return {
            'id': self.id,
            'kind': self.kind,
            'username': self.username,
            'amount_cents': self.amount_cents,
            'currency': self.currency,
            'status': self.status,
            'description': self.description or '',
            'reference_id': self.reference_id,
            'stripe_session_id': self.stripe_session_id,
            'stripe_payment_intent': self.stripe_payment_intent,
            'stripe_refund_id': self.stripe_refund_id,
            'meta': meta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
        }


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_monetization_schema()
    _ensure_default_settings()


def _ensure_monetization_schema():
    """Add new columns on existing DBs (SQLite/Postgres)."""
    from sqlalchemy import text, inspect
    try:
        insp = inspect(engine)
        if 'users' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('users')}
        alters = []
        if 'premium_until' not in cols:
            alters.append('ALTER TABLE users ADD COLUMN premium_until DATETIME')
        if 'boost_until' not in cols:
            alters.append('ALTER TABLE users ADD COLUMN boost_until DATETIME')
        if alters:
            with engine.begin() as conn:
                for stmt in alters:
                    conn.execute(text(stmt))
    except Exception as e:
        print(f'[schema] monetization migrate note: {e}')


def _ensure_default_settings():
    db = SessionLocal()
    try:
        row = db.get(PlatformSettings, 1)
        if not row:
            db.add(PlatformSettings(id=1))
            db.commit()
    except Exception as e:
        db.rollback()
        print(f'[settings] init note: {e}')
    finally:
        db.close()


def get_platform_settings(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, 1)
    if not row:
        row = PlatformSettings(id=1)
        db.add(row)
        db.flush()
    return row


def get_db() -> Session:
    return SessionLocal()


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return utcnow()


def migrate_json_if_needed():
    """One-time import from legacy data/*.json when DB has no users."""
    db = get_db()
    try:
        if db.scalar(select(func.count()).select_from(User)) > 0:
            return
        users_path = 'data/users.json'
        if not os.path.exists(users_path):
            return
        with open(users_path, 'r') as f:
            users = json.load(f)
        if not users:
            return

        for username, u in users.items():
            db.add(User(
                username=username,
                email=u.get('email', f'{username}@example.com'),
                password=u.get('password', ''),
                profile_picture=u.get('profile_picture'),
                bio=u.get('bio', ''),
                interests=u.get('interests', ''),
                relationship_status=u.get('relationship_status', 'Open'),
                theme=u.get('theme', 'default'),
                is_admin=bool(u.get('is_admin', False)),
                email_verified=True,  # legacy accounts treated as verified
                email_on_message=u.get('email_on_message', True),
                email_on_request=u.get('email_on_request', True),
                email_on_like=u.get('email_on_like', False),
                email_on_follow=u.get('email_on_follow', False),
                email_on_gift=u.get('email_on_gift', True),
                created_at=parse_dt(u.get('created_at')) or utcnow(),
            ))

        def load_list(path):
            if not os.path.exists(path):
                return []
            with open(path, 'r') as f:
                return json.load(f)

        for r in load_list('data/requests.json'):
            db.add(ConnectionRequest(
                id=str(r.get('id', new_id())),
                from_user=r.get('from'),
                to_user=r.get('to'),
                message=r.get('message', ''),
                status=r.get('status', 'pending'),
                response_message=r.get('response_message', ''),
                sent_at=parse_dt(r.get('sent_at')) or utcnow(),
                responded_at=parse_dt(r.get('responded_at')),
            ))

        for m in load_list('data/messages.json'):
            content = m.get('content', '')
            # Skip enormous base64 blobs for DB health — keep a placeholder
            msg_type = m.get('type', 'text')
            if isinstance(content, str) and content.startswith('data:image') and len(content) > 5000:
                content = '[Legacy image — re-share to restore]'
                msg_type = 'image'
            db.add(Message(
                from_user=m.get('from'),
                to_user=m.get('to'),
                content=content,
                msg_type=msg_type,
                read=bool(m.get('read', False)),
                sent_at=parse_dt(m.get('sent_at')) or utcnow(),
            ))

        for c in load_list('data/cards.json'):
            db.add(Card(
                id=str(c.get('id', new_id())),
                from_user=c.get('from'),
                to_user=c.get('to'),
                template_id=c.get('template_id'),
                message=c.get('message', ''),
                viewed=bool(c.get('viewed', False)),
                created_at=parse_dt(c.get('created_at')) or utcnow(),
            ))

        for f in load_list('data/follows.json'):
            db.add(Follow(follower=f.get('follower'), following=f.get('following'),
                          followed_at=parse_dt(f.get('followed_at')) or utcnow()))

        for l in load_list('data/likes.json'):
            db.add(Like(user=l.get('user'), likes_username=l.get('likes_username'),
                        liked_at=parse_dt(l.get('liked_at')) or utcnow()))

        for n in load_list('data/notifications.json'):
            db.add(Notification(
                id=str(n.get('id', new_id())),
                to_user=n.get('to') or '',
                from_user=n.get('from'),
                notif_type=n.get('type', 'info'),
                message=n.get('message', ''),
                read=bool(n.get('read', False)),
                created_at=parse_dt(n.get('created_at')) or utcnow(),
            ))

        for b in load_list('data/blocks.json'):
            db.add(Block(blocker=b.get('blocker'), blocked=b.get('blocked'),
                         created_at=parse_dt(b.get('created_at')) or utcnow()))

        for r in load_list('data/reports.json'):
            db.add(Report(
                reporter=r.get('reporter'), reported=r.get('reported'),
                reason=r.get('reason', ''), message=r.get('message', ''),
                created_at=parse_dt(r.get('created_at')) or utcnow(),
            ))

        for o in load_list('data/orders.json'):
            db.add(Order(
                id=str(o.get('id', new_id())),
                gift_id=o.get('gift_id', 0),
                gift_name=o.get('gift_name', ''),
                price_cents=o.get('price_cents', 0),
                currency=o.get('currency', 'usd'),
                from_user=o.get('from'),
                to_user=o.get('to'),
                message=o.get('message', ''),
                status=o.get('status', 'pending'),
                delivered=bool(o.get('delivered', False)),
                payment_mode=o.get('payment_mode', 'stripe'),
                stripe_session_id=o.get('stripe_session_id'),
                stripe_payment_intent=o.get('stripe_payment_intent'),
                created_at=parse_dt(o.get('created_at')) or utcnow(),
                paid_at=parse_dt(o.get('paid_at')),
                delivered_at=parse_dt(o.get('delivered_at')),
            ))

        for g in load_list('data/gifts_sent.json'):
            db.add(GiftSent(
                id=str(g.get('id', new_id())),
                order_id=str(g.get('order_id', '')),
                gift_id=g.get('gift_id', 0),
                gift_name=g.get('gift_name', ''),
                gift_emoji=g.get('gift_emoji', ''),
                price_cents=g.get('price_cents', 0),
                currency=g.get('currency', 'usd'),
                from_user=g.get('from'),
                to_user=g.get('to'),
                message=g.get('message', ''),
                created_at=parse_dt(g.get('created_at')) or utcnow(),
            ))

        analytics_path = 'data/analytics.json'
        if os.path.exists(analytics_path):
            with open(analytics_path, 'r') as f:
                analytics = json.load(f)
            for username, a in analytics.items():
                db.add(UserAnalytics(
                    username=username,
                    page_views=a.get('page_views', 0),
                    messages_sent=a.get('messages_sent', 0),
                    follows=a.get('follows', 0),
                    likes=a.get('likes', 0),
                    requests_sent=a.get('requests_sent', 0),
                    gifts_sent=a.get('gifts_sent', 0),
                    gifts_bought=a.get('gifts_bought', 0),
                ))

        db.commit()
        print('[migrate] Imported legacy JSON data into database')
    except Exception as e:
        db.rollback()
        print(f'[migrate] skipped/failed: {e}')
    finally:
        db.close()
