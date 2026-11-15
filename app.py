from flask import (
    Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, abort
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, or_, and_, func, desc
from dotenv import load_dotenv
from PIL import Image
import io
import json
import os
import re
import secrets
import uuid

load_dotenv()

try:
    from flask_mail import Mail, Message as MailMessage
except ImportError:
    Mail, MailMessage = None, None

try:
    import stripe
except ImportError:
    stripe = None

from models import (
    init_db, migrate_json_if_needed, get_db, SessionLocal, utcnow, new_id,
    User, AuthToken, ConnectionRequest, Message, Card, Follow, Like,
    Notification, Block, Report, Order, GiftSent, UserAnalytics,
    PlatformSettings, PlatformPayment, get_platform_settings,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
IS_PRODUCTION = os.getenv('FLASK_ENV', 'development').lower() == 'production'
APP_NAME = os.getenv('APP_NAME', 'TextLink')
APP_URL = os.getenv('APP_URL', '').rstrip('/')
REQUIRE_EMAIL_CONFIRM = os.getenv('REQUIRE_EMAIL_CONFIRM', 'true').lower() in ('1', 'true', 'yes')
REQUIRE_CONNECTION_TO_MESSAGE = os.getenv('REQUIRE_CONNECTION_TO_MESSAGE', 'true').lower() in ('1', 'true', 'yes')
TOKEN_TTL_HOURS = int(os.getenv('AUTH_TOKEN_TTL_HOURS', '48'))
CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
if not CORS_ORIGINS:
    CORS_ORIGINS = [APP_URL] if (IS_PRODUCTION and APP_URL) else ['*']

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

_secret = os.getenv('SECRET_KEY')
if IS_PRODUCTION and (not _secret or _secret in (
    'your_secret_key_here', 'valentine_secret_2026', 'valentine_secret_2026_dev',
    'dev-only-insecure-textlink-key', 'textlink_change_me',
)):
    raise RuntimeError('Set a strong SECRET_KEY before running in production.')
app.secret_key = _secret or 'dev-only-insecure-textlink-key'

UPLOAD_FOLDER = os.path.abspath(os.getenv('UPLOAD_FOLDER', 'data/uploads'))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

app.config.update(
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
    MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
    MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes'),
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER', f'noreply@{APP_NAME.lower()}.app'),
)

socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGINS, async_mode='eventlet')
mail = Mail(app) if Mail else None
limiter = Limiter(get_remote_address, app=app, default_limits=['200 per hour'], storage_uri='memory://')

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip()
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
STRIPE_CURRENCY = (os.getenv('STRIPE_CURRENCY', 'usd') or 'usd').lower()
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY and stripe)
if STRIPE_ENABLED:
    stripe.api_key = STRIPE_SECRET_KEY

MAIL_CONFIGURED = bool(app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD') and mail)

GIFTS = [
    {'id': 1, 'name': 'Red Roses Bouquet', 'emoji': '🌹', 'description': 'A classic dozen red roses as a digital gift', 'price_cents': 1999, 'category': 'flowers'},
    {'id': 2, 'name': 'Chocolate Gift Box', 'emoji': '🍫', 'description': 'Luxury chocolates for someone special', 'price_cents': 1499, 'category': 'sweets'},
    {'id': 3, 'name': 'Sparkle Ring', 'emoji': '💎', 'description': 'Elegant jewelry gift token', 'price_cents': 4999, 'category': 'jewelry'},
    {'id': 4, 'name': 'Signature Perfume', 'emoji': '💐', 'description': 'Luxury fragrance gift', 'price_cents': 2999, 'category': 'perfume'},
    {'id': 5, 'name': 'Love Pendant', 'emoji': '❤️', 'description': 'Matching couple necklace gift', 'price_cents': 2499, 'category': 'jewelry'},
    {'id': 6, 'name': 'Dinner Night Out', 'emoji': '🍽️', 'description': 'Romantic dinner experience voucher', 'price_cents': 7999, 'category': 'experiences'},
    {'id': 7, 'name': 'Spa Package', 'emoji': '🧖', 'description': 'Relaxing spa treatment voucher', 'price_cents': 8999, 'category': 'experiences'},
    {'id': 8, 'name': 'Giant Teddy Bear', 'emoji': '🧸', 'description': 'Big fluffy teddy bear gift', 'price_cents': 3499, 'category': 'toys'},
    {'id': 9, 'name': 'Coffee Date', 'emoji': '☕', 'description': 'Treat them to coffee', 'price_cents': 599, 'category': 'experiences'},
    {'id': 10, 'name': 'Movie Night', 'emoji': '🎬', 'description': 'Streaming movie night gift card', 'price_cents': 1299, 'category': 'experiences'},
]

CARD_TEMPLATES = [
    {'id': 1, 'name': 'Warm Hello', 'bg': 'linear-gradient(135deg, #0f766e 0%, #14b8a6 100%)', 'icon': '💬'},
    {'id': 2, 'name': 'Soft Note', 'bg': 'linear-gradient(135deg, #be123c 0%, #fb7185 100%)', 'icon': '🌸'},
    {'id': 3, 'name': 'Bold Thanks', 'bg': 'linear-gradient(135deg, #1e3a5f 0%, #3b82f6 100%)', 'icon': '✨'},
    {'id': 4, 'name': 'Playful Vibes', 'bg': 'linear-gradient(135deg, #c2410c 0%, #f97316 100%)', 'icon': '🎉'},
]

init_db()
migrate_json_if_needed()


@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_app_url():
    if APP_URL:
        return APP_URL
    return request.url_root.rstrip('/')


def format_price(cents, currency=None):
    currency = (currency or STRIPE_CURRENCY).upper()
    amount = (cents or 0) / 100.0
    if currency == 'USD':
        return f'${amount:.2f}'
    return f'{amount:.2f} {currency}'


def get_gift_by_id(gift_id):
    try:
        gift_id = int(gift_id)
    except (TypeError, ValueError):
        return None
    return next((g for g in GIFTS if g['id'] == gift_id), None)


def gift_price_for_user(db, gift, user):
    """Platform keeps 100% of gift sales; premium members get a discount."""
    price = int(gift['price_cents'])
    settings = get_platform_settings(db)
    if user and user.is_premium_active():
        pct = max(0, min(50, int(settings.premium_gift_discount_percent or 0)))
        if pct:
            price = max(50, price - (price * pct // 100))
    return price


def record_platform_payment(db, *, kind, username, amount_cents, currency, description,
                            reference_id=None, stripe_session_id=None, stripe_payment_intent=None,
                            status='paid', meta=None):
    """Every paid dollar is logged so the admin can see earnings."""
    existing = None
    if reference_id:
        existing = db.scalar(select(PlatformPayment).where(
            PlatformPayment.reference_id == reference_id,
            PlatformPayment.kind == kind,
            PlatformPayment.status == 'paid',
        ))
    if existing:
        return existing
    row = PlatformPayment(
        id=new_id(),
        kind=kind,
        username=username,
        amount_cents=int(amount_cents),
        currency=(currency or STRIPE_CURRENCY),
        status=status,
        description=description or '',
        reference_id=reference_id,
        stripe_session_id=stripe_session_id,
        stripe_payment_intent=stripe_payment_intent,
        meta_json=json.dumps(meta or {}),
        created_at=utcnow(),
        paid_at=utcnow() if status == 'paid' else None,
    )
    db.add(row)
    db.flush()
    return row


def extend_datetime(current, days):
    base = current
    if base:
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        if base < utcnow():
            base = utcnow()
    else:
        base = utcnow()
    return base + timedelta(days=int(days))


def fulfill_platform_product(db, payment: PlatformPayment):
    """Activate premium/boost after successful payment (idempotent)."""
    if payment.status == 'paid' and payment.paid_at and payment.kind in ('premium', 'boost'):
        # still ensure entitlements applied
        pass
    user = db.get(User, payment.username)
    if not user:
        payment.status = 'error'
        return payment
    settings = get_platform_settings(db)
    if payment.kind == 'premium':
        user.premium_until = extend_datetime(user.premium_until, settings.premium_days or 30)
        payment.description = payment.description or f'Premium {settings.premium_days} days'
    elif payment.kind == 'boost':
        user.boost_until = extend_datetime(user.boost_until, settings.boost_days or 7)
        payment.description = payment.description or f'Profile boost {settings.boost_days} days'
    payment.status = 'paid'
    payment.paid_at = payment.paid_at or utcnow()
    return payment


def send_email(recipient, subject, html_content):
    if not recipient:
        return False
    if not MAIL_CONFIGURED:
        print(f'[email skipped] to={recipient} subject={subject}\n{html_content[:500]}')
        return False
    try:
        msg = MailMessage(subject=subject, recipients=[recipient], html=html_content)
        mail.send(msg)
        return True
    except Exception as e:
        print(f'Email error: {e}')
        return False


def create_auth_token(db, username, purpose, hours=None):
    token = secrets.token_urlsafe(32)
    hours = hours or TOKEN_TTL_HOURS
    row = AuthToken(
        id=new_id(),
        username=username,
        token=token,
        purpose=purpose,
        created_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=hours),
    )
    db.add(row)
    db.flush()
    return token


def consume_auth_token(db, token, purpose):
    row = db.scalar(select(AuthToken).where(AuthToken.token == token, AuthToken.purpose == purpose))
    if not row or row.used_at:
        return None
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utcnow():
        return None
    row.used_at = utcnow()
    return row


def send_verification_email(db, user):
    token = create_auth_token(db, user.username, 'verify_email')
    link = f"{get_app_url()}/verify-email/{token}"
    sent = send_email(
        user.email,
        f'Confirm your {APP_NAME} email',
        f'<h2>Welcome to {APP_NAME}!</h2>'
        f'<p>Hi {user.username}, confirm your email to activate messaging and gifts.</p>'
        f'<p><a href="{link}" style="display:inline-block;padding:12px 20px;background:#0f766e;color:#fff;'
        f'text-decoration:none;border-radius:8px;font-weight:600;">Confirm email</a></p>'
        f'<p>Or open: {link}</p>'
        f'<p>This link expires in {TOKEN_TTL_HOURS} hours.</p>'
    )
    return token, sent, link


def send_password_reset_email(db, user):
    token = create_auth_token(db, user.username, 'reset_password', hours=2)
    link = f"{get_app_url()}/reset-password/{token}"
    sent = send_email(
        user.email,
        f'Reset your {APP_NAME} password',
        f'<h2>Password reset</h2>'
        f'<p>Hi {user.username}, click below to choose a new password.</p>'
        f'<p><a href="{link}">Reset password</a></p>'
        f'<p>Or open: {link}</p>'
        f'<p>This link expires in 2 hours. If you did not ask for this, ignore the email.</p>'
    )
    return token, sent, link


def current_user(db):
    username = session.get('user_id')
    if not username:
        return None
    return db.get(User, username)


def is_blocked(db, user1, user2):
    return db.scalar(
        select(Block.id).where(Block.blocker == user1, Block.blocked == user2)
    ) is not None


def either_blocked(db, a, b):
    return is_blocked(db, a, b) or is_blocked(db, b, a)


def are_connected(db, a, b):
    return db.scalar(
        select(ConnectionRequest.id).where(
            ConnectionRequest.status == 'accepted',
            or_(
                and_(ConnectionRequest.from_user == a, ConnectionRequest.to_user == b),
                and_(ConnectionRequest.from_user == b, ConnectionRequest.to_user == a),
            )
        )
    ) is not None


def can_interact(db, sender, recipient, *, require_connection=None):
    if sender == recipient:
        return False, 'Cannot target yourself'
    recipient_user = db.get(User, recipient)
    if not recipient_user:
        return False, 'User not found'
    if recipient_user.is_banned:
        return False, 'User is unavailable'
    if either_blocked(db, sender, recipient):
        return False, 'You cannot contact this user'
    require_connection = REQUIRE_CONNECTION_TO_MESSAGE if require_connection is None else require_connection
    sender_user = db.get(User, sender)
    if require_connection and not (sender_user and sender_user.is_admin) and not are_connected(db, sender, recipient):
        return False, 'You need an accepted connection request before messaging or sending gifts'
    return True, None


def add_notification(db, to_user, from_user, notif_type, message, emit=True):
    n = Notification(
        id=new_id(), to_user=to_user, from_user=from_user,
        notif_type=notif_type, message=message, created_at=utcnow(),
    )
    db.add(n)
    db.flush()
    if emit:
        socketio.emit('user_notification', {
            'type': notif_type, 'message': message, 'from': from_user,
        }, room=to_user)
    return n


def track_event(db, event_type, username):
    row = db.get(UserAnalytics, username)
    if not row:
        row = UserAnalytics(username=username)
        db.add(row)
        db.flush()
    mapping = {
        'page_view': 'page_views',
        'message': 'messages_sent',
        'follow': 'follows',
        'like': 'likes',
        'request': 'requests_sent',
        'gift_sent': 'gifts_sent',
        'gift_bought': 'gifts_bought',
    }
    key = mapping.get(event_type)
    if key:
        setattr(row, key, (getattr(row, key) or 0) + 1)


def save_image_upload(file_storage, subdir='misc'):
    if not file_storage or not file_storage.filename:
        raise ValueError('No file')
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError('Unsupported image type')
    raw = file_storage.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img = Image.open(io.BytesIO(raw))
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        fmt = 'JPEG' if ext in ('.jpg', '.jpeg') else ('PNG' if ext == '.png' else img.format or 'JPEG')
        out_ext = '.jpg' if fmt == 'JPEG' else ('.png' if fmt == 'PNG' else ext)
    except Exception:
        raise ValueError('Invalid image file')

    folder = os.path.join(UPLOAD_FOLDER, subdir)
    os.makedirs(folder, exist_ok=True)
    name = f'{uuid.uuid4().hex}{out_ext}'
    path = os.path.join(folder, name)
    save_kwargs = {'quality': 85, 'optimize': True} if fmt == 'JPEG' else {}
    if fmt == 'JPEG' and img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(path, format=fmt, **save_kwargs)
    return f'/uploads/{subdir}/{name}'


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Not logged in'}), 401
            return redirect(url_for('index'))
        db = get_db()
        user = db.get(User, session['user_id'])
        if not user or user.is_banned:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Account unavailable'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def verified_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not REQUIRE_EMAIL_CONFIRM:
            return f(*args, **kwargs)
        db = get_db()
        user = db.get(User, session['user_id'])
        if user and not user.email_verified:
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'message': 'Please confirm your email first',
                    'needs_verification': True,
                }), 403
            return redirect(url_for('verify_pending'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        db = get_db()
        user = db.get(User, session['user_id'])
        if not user or not user.is_admin:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', app_name=APP_NAME)


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = db.get(User, session['user_id'])
    if REQUIRE_EMAIL_CONFIRM and user and not user.email_verified:
        return redirect(url_for('verify_pending'))
    track_event(db, 'page_view', user.username)
    db.commit()
    return render_template(
        'dashboard.html',
        app_name=APP_NAME,
        stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
        stripe_enabled=STRIPE_ENABLED,
        currency=STRIPE_CURRENCY.upper(),
        require_connection=REQUIRE_CONNECTION_TO_MESSAGE,
    )


@app.route('/verify-pending')
@login_required
def verify_pending():
    db = get_db()
    user = db.get(User, session['user_id'])
    if user and user.email_verified:
        return redirect(url_for('dashboard'))
    return render_template('verify_pending.html', app_name=APP_NAME, email=user.email if user else '')


@app.route('/verify-email/<token>')
def verify_email(token):
    db = get_db()
    row = consume_auth_token(db, token, 'verify_email')
    if not row:
        return render_template('verify_result.html', app_name=APP_NAME, success=False,
                               message='This confirmation link is invalid or expired.'), 400
    user = db.get(User, row.username)
    if not user:
        return render_template('verify_result.html', app_name=APP_NAME, success=False,
                               message='Account not found.'), 404
    user.email_verified = True
    db.commit()
    session.permanent = True
    session['user_id'] = user.username
    return render_template('verify_result.html', app_name=APP_NAME, success=True,
                           message='Email confirmed! You can use TextLink now.')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password_page():
    if request.method == 'GET':
        return render_template('forgot_password.html', app_name=APP_NAME)
    return redirect(url_for('forgot_password_page'))


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_page(token):
    return render_template('reset_password.html', app_name=APP_NAME, token=token)


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html', app_name=APP_NAME)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/gifts/success')
@login_required
def gift_success():
    session_id = request.args.get('session_id', '').strip()
    if session_id and STRIPE_ENABLED:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            if checkout.payment_status == 'paid':
                db = get_db()
                order_id = (checkout.metadata or {}).get('order_id')
                order = None
                if order_id:
                    order = db.get(Order, order_id)
                if not order:
                    order = db.scalar(select(Order).where(Order.stripe_session_id == session_id))
                if order:
                    order.stripe_session_id = session_id
                    order.stripe_payment_intent = checkout.get('payment_intent')
                    fulfill_gift_order(db, order)
                    db.commit()
        except Exception as e:
            print(f'Gift success fulfill error: {e}')
    return redirect(url_for('dashboard') + '?gift=success')


@app.route('/gifts/cancel')
@login_required
def gift_cancel():
    session_id = request.args.get('session_id', '').strip()
    if session_id:
        db = get_db()
        order = db.scalar(select(Order).where(Order.stripe_session_id == session_id))
        if order and order.status == 'pending':
            order.status = 'cancelled'
            order.cancelled_at = utcnow()
            db.commit()
    return redirect(url_for('dashboard') + '?gift=cancelled')


# ---------------------------------------------------------------------------
# Auth APIs
# ---------------------------------------------------------------------------
@app.route('/register', methods=['POST'])
@limiter.limit('10 per minute')
def register():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not all([username, email, password]):
        return jsonify({'success': False, 'message': 'All fields required'}), 400
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', username):
        return jsonify({'success': False, 'message': 'Username must be 3–32 letters, numbers, or _'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'success': False, 'message': 'Invalid email address'}), 400

    db = get_db()
    if db.get(User, username):
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    if db.scalar(select(User).where(User.email == email)):
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    auto_verify = (not REQUIRE_EMAIL_CONFIRM) or (not MAIL_CONFIGURED and not IS_PRODUCTION)

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        created_at=utcnow(),
        is_admin=(user_count == 0),
        email_verified=auto_verify,
    )
    db.add(user)
    db.flush()

    verify_link = None
    if not user.email_verified:
        token, sent, verify_link = send_verification_email(db, user)
        if not sent and not IS_PRODUCTION:
            print(f'[dev] Verify link for {username}: {verify_link}')

    db.commit()
    session.permanent = True
    session['user_id'] = username

    payload = {
        'success': True,
        'message': 'Account created. Please confirm your email.' if not user.email_verified else 'Account created successfully',
        'email_verified': bool(user.email_verified),
        'needs_verification': not bool(user.email_verified),
    }
    if verify_link and not MAIL_CONFIGURED and not IS_PRODUCTION:
        payload['dev_verify_link'] = verify_link
    return jsonify(payload), 201


@app.route('/login', methods=['POST'])
@limiter.limit('20 per minute')
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    db = get_db()
    user = db.get(User, username)
    if not user or not check_password_hash(user.password, password):
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    if user.is_banned:
        return jsonify({'success': False, 'message': f'Account banned. {user.ban_reason or ""}'.strip()}), 403

    session.permanent = True
    session['user_id'] = username
    needs = REQUIRE_EMAIL_CONFIRM and not user.email_verified
    return jsonify({
        'success': True,
        'message': 'Logged in successfully',
        'email_verified': bool(user.email_verified),
        'needs_verification': needs,
    }), 200


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/api/resend-verification', methods=['POST'])
@login_required
@limiter.limit('5 per minute')
def resend_verification():
    db = get_db()
    user = db.get(User, session['user_id'])
    if user.email_verified:
        return jsonify({'success': True, 'message': 'Email already confirmed'}), 200
    token, sent, link = send_verification_email(db, user)
    db.commit()
    payload = {'success': True, 'message': 'Confirmation email sent' if sent else 'Confirmation link generated'}
    if not MAIL_CONFIGURED and not IS_PRODUCTION:
        payload['dev_verify_link'] = link
        payload['message'] = 'Mail not configured — use the link below (dev only)'
    return jsonify(payload), 200


@app.route('/api/forgot-password', methods=['POST'])
@limiter.limit('5 per minute')
def forgot_password():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    # Always return success to avoid email enumeration
    db = get_db()
    user = db.scalar(select(User).where(User.email == email)) if email else None
    payload = {'success': True, 'message': 'If that email exists, a reset link was sent.'}
    if user:
        token, sent, link = send_password_reset_email(db, user)
        db.commit()
        if not MAIL_CONFIGURED and not IS_PRODUCTION:
            payload['dev_reset_link'] = link
    return jsonify(payload), 200


@app.route('/api/reset-password', methods=['POST'])
@limiter.limit('10 per minute')
def reset_password():
    data = request.json or {}
    token = (data.get('token') or '').strip()
    password = (data.get('password') or '').strip()
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    db = get_db()
    row = consume_auth_token(db, token, 'reset_password')
    if not row:
        return jsonify({'success': False, 'message': 'Invalid or expired reset link'}), 400
    user = db.get(User, row.username)
    if not user:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    user.password = generate_password_hash(password)
    user.email_verified = True
    db.commit()
    return jsonify({'success': True, 'message': 'Password updated. You can log in now.'}), 200


# ---------------------------------------------------------------------------
# Config / health
# ---------------------------------------------------------------------------
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'app': APP_NAME,
        'stripe': STRIPE_ENABLED,
        'mail': MAIL_CONFIGURED,
        'email_confirm_required': REQUIRE_EMAIL_CONFIRM,
        'env': 'production' if IS_PRODUCTION else 'development',
    }), 200


@app.route('/api/config')
def public_config():
    return jsonify({
        'app_name': APP_NAME,
        'stripe_enabled': STRIPE_ENABLED,
        'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY if STRIPE_ENABLED else '',
        'currency': STRIPE_CURRENCY.upper(),
        'require_connection': REQUIRE_CONNECTION_TO_MESSAGE,
        'email_confirm_required': REQUIRE_EMAIL_CONFIRM,
    }), 200


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@app.route('/api/user')
@login_required
def get_user():
    db = get_db()
    user = db.get(User, session['user_id'])
    return jsonify(user.private_dict()), 200


@app.route('/api/user/<username>')
@login_required
def get_user_profile(username):
    db = get_db()
    me = session['user_id']
    if either_blocked(db, me, username):
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user = db.get(User, username)
    if not user or user.is_banned:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify(user.public_dict()), 200


@app.route('/api/user/profile-picture', methods=['POST'])
@verified_required
def upload_profile_picture():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    try:
        url = save_image_upload(request.files['file'], 'profiles')
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    db = get_db()
    user = db.get(User, session['user_id'])
    user.profile_picture = url
    db.commit()
    return jsonify({'success': True, 'message': 'Profile picture updated', 'url': url}), 200


@app.route('/api/user/bio', methods=['POST'])
@verified_required
def update_bio():
    data = request.json or {}
    bio = (data.get('bio') or '').strip()[:200]
    db = get_db()
    user = db.get(User, session['user_id'])
    user.bio = bio
    db.commit()
    return jsonify({'success': True, 'message': 'Bio updated'}), 200


@app.route('/api/user/profile', methods=['POST'])
@verified_required
def update_profile():
    data = request.json or {}
    db = get_db()
    user = db.get(User, session['user_id'])
    user.interests = (data.get('interests') or '').strip()[:200]
    user.relationship_status = (data.get('relationship_status') or 'Open').strip()[:64]
    user.theme = (data.get('theme') or 'default').strip()[:32]
    db.commit()
    return jsonify({'success': True, 'message': 'Profile updated'}), 200


@app.route('/api/user/change-password', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def change_password():
    data = request.json or {}
    current = (data.get('current_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400
    db = get_db()
    user = db.get(User, session['user_id'])
    if not check_password_hash(user.password, current):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
    user.password = generate_password_hash(new_password)
    db.commit()
    return jsonify({'success': True, 'message': 'Password changed'}), 200


@app.route('/api/user/delete-account', methods=['POST'])
@login_required
@limiter.limit('3 per minute')
def delete_own_account():
    data = request.json or {}
    password = (data.get('password') or '').strip()
    db = get_db()
    user = db.get(User, session['user_id'])
    if not check_password_hash(user.password, password):
        return jsonify({'success': False, 'message': 'Password incorrect'}), 400
    username = user.username
    _purge_user_data(db, username)
    db.delete(user)
    db.commit()
    session.clear()
    return jsonify({'success': True, 'message': 'Account deleted'}), 200


@app.route('/api/user/export', methods=['GET'])
@login_required
def export_own_data():
    db = get_db()
    me = session['user_id']
    user = db.get(User, me)
    payload = {
        'user': user.private_dict(),
        'messages': [m.to_dict() for m in db.scalars(
            select(Message).where(or_(Message.from_user == me, Message.to_user == me)).limit(5000)
        )],
        'requests': [r.to_dict() for r in db.scalars(
            select(ConnectionRequest).where(or_(ConnectionRequest.from_user == me, ConnectionRequest.to_user == me))
        )],
        'orders': [o.to_dict() for o in db.scalars(select(Order).where(Order.from_user == me))],
        'gifts_received': [g.to_dict() for g in db.scalars(select(GiftSent).where(GiftSent.to_user == me))],
    }
    return jsonify(payload), 200


@app.route('/api/search-user', methods=['GET'])
@verified_required
def search_user():
    query = (request.args.get('q') or '').strip().lower()
    if len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short'}), 400
    db = get_db()
    me = session['user_id']
    blocked = {b.blocked for b in db.scalars(select(Block).where(Block.blocker == me))}
    blocked |= {b.blocker for b in db.scalars(select(Block).where(Block.blocked == me))}
    users = db.scalars(
        select(User).where(
            User.is_banned.is_(False),
            User.username != me,
            or_(
                User.username.ilike(f'%{query}%'),
                User.bio.ilike(f'%{query}%'),
                User.interests.ilike(f'%{query}%'),
            )
        ).limit(40)
    )
    results = []
    for u in users:
        if u.username in blocked:
            continue
        d = u.public_dict()
        d['connected'] = are_connected(db, me, u.username)
        results.append(d)
    # Boosted profiles first (admin monetization), then premium, then others
    results.sort(key=lambda r: (0 if r.get('is_boosted') else 1, 0 if r.get('is_premium') else 1, r['username'].lower()))
    return jsonify({'success': True, 'results': results}), 200


# ---------------------------------------------------------------------------
# Connection requests
# ---------------------------------------------------------------------------
@app.route('/api/send-request', methods=['POST'])
@verified_required
@limiter.limit('30 per minute')
def send_request():
    data = request.json or {}
    recipient = (data.get('recipient_username') or '').strip()
    message = (data.get('message') or '').strip()
    requester = session['user_id']
    db = get_db()

    ok, err = can_interact(db, requester, recipient, require_connection=False)
    if not ok:
        return jsonify({'success': False, 'message': err}), 400

    existing = db.scalar(
        select(ConnectionRequest).where(
            ConnectionRequest.from_user == requester,
            ConnectionRequest.to_user == recipient,
        )
    )
    if existing:
        return jsonify({'success': False, 'message': 'You already sent a request to this user'}), 400

    if are_connected(db, requester, recipient):
        return jsonify({'success': False, 'message': 'Already connected'}), 400

    req = ConnectionRequest(
        id=new_id(), from_user=requester, to_user=recipient,
        message=message, status='pending', sent_at=utcnow(),
    )
    db.add(req)
    track_event(db, 'request', requester)
    add_notification(db, recipient, requester, 'request', f'{requester} sent you a connection request')
    recipient_user = db.get(User, recipient)
    if recipient_user and recipient_user.email_on_request:
        send_email(
            recipient_user.email,
            f'New connection request from {requester}',
            f'<h2>New request from {requester}</h2><p>{message}</p>'
            f'<p><a href="{get_app_url()}/dashboard">View request</a></p>'
        )
    db.commit()
    return jsonify({'success': True, 'message': 'Request sent successfully', 'request': req.to_dict()}), 201


@app.route('/api/requests/sent')
@verified_required
def get_sent_requests():
    db = get_db()
    rows = db.scalars(select(ConnectionRequest).where(ConnectionRequest.from_user == session['user_id']))
    return jsonify([r.to_dict() for r in rows]), 200


@app.route('/api/requests/received')
@verified_required
def get_received_requests():
    db = get_db()
    rows = db.scalars(select(ConnectionRequest).where(ConnectionRequest.to_user == session['user_id']))
    return jsonify([r.to_dict() for r in rows]), 200


@app.route('/api/requests/<request_id>/respond', methods=['POST'])
@verified_required
def respond_to_request(request_id):
    data = request.json or {}
    response = (data.get('response') or '').lower()
    response_message = (data.get('response_message') or '').strip()
    db = get_db()
    req = db.get(ConnectionRequest, str(request_id))
    if not req or req.to_user != session['user_id']:
        return jsonify({'success': False, 'message': 'Request not found'}), 404
    if req.status != 'pending':
        return jsonify({'success': False, 'message': 'Request already responded to'}), 400
    if response not in ('accept', 'reject'):
        return jsonify({'success': False, 'message': 'Invalid response'}), 400
    req.status = 'accepted' if response == 'accept' else 'rejected'
    req.response_message = response_message
    req.responded_at = utcnow()
    status_word = 'accepted' if response == 'accept' else 'declined'
    add_notification(db, req.from_user, session['user_id'], 'request_response',
                     f'{session["user_id"]} {status_word} your connection request')
    requester = db.get(User, req.from_user)
    if requester:
        send_email(
            requester.email,
            f'Connection response from {session["user_id"]}',
            f'<h2>{session["user_id"]} {status_word} your request</h2><p>{response_message}</p>'
        )
    db.commit()
    return jsonify({'success': True, 'message': f'Request {response}ed successfully'}), 200


# ---------------------------------------------------------------------------
# Messaging / inbox
# ---------------------------------------------------------------------------
@app.route('/api/conversations')
@verified_required
def list_conversations():
    db = get_db()
    me = session['user_id']
    messages = db.scalars(
        select(Message).where(or_(Message.from_user == me, Message.to_user == me))
        .order_by(desc(Message.sent_at)).limit(1000)
    )
    convos = {}
    for m in messages:
        other = m.to_user if m.from_user == me else m.from_user
        if other in convos:
            if not m.read and m.to_user == me:
                convos[other]['unread'] += 1
            continue
        other_user = db.get(User, other)
        preview = m.content
        if m.msg_type == 'image':
            preview = '[Image]'
        elif m.msg_type == 'gift':
            preview = preview.split('\n')[0][:80]
        else:
            preview = (preview or '')[:80]
        convos[other] = {
            'username': other,
            'profile_picture': other_user.profile_picture if other_user else None,
            'last_message': preview,
            'last_at': m.sent_at.isoformat() if m.sent_at else None,
            'unread': 0 if m.read or m.to_user != me else 1,
            'connected': are_connected(db, me, other),
        }
    items = sorted(convos.values(), key=lambda c: c.get('last_at') or '', reverse=True)
    return jsonify(items), 200


@app.route('/api/messages/send', methods=['POST'])
@verified_required
@limiter.limit('60 per minute')
def send_message():
    data = request.json or {}
    recipient = (data.get('to') or '').strip()
    content = (data.get('content') or '').strip()
    sender = session['user_id']
    if not content:
        return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
    db = get_db()
    ok, err = can_interact(db, sender, recipient)
    if not ok:
        return jsonify({'success': False, 'message': err}), 403

    msg = Message(
        id=new_id(), from_user=sender, to_user=recipient,
        content=content, msg_type='text', sent_at=utcnow(),
    )
    db.add(msg)
    track_event(db, 'message', sender)
    recipient_user = db.get(User, recipient)
    if recipient_user and recipient_user.email_on_message:
        send_email(
            recipient_user.email,
            f'New message from {sender}',
            f'<h2>New message from {sender}</h2><p>{content}</p>'
            f'<p><a href="{get_app_url()}/dashboard">View message</a></p>'
        )
    db.commit()
    socketio.emit('new_message', msg.to_dict(), room=recipient)
    return jsonify({'success': True, 'message': 'Message sent', 'data': msg.to_dict()}), 201


@app.route('/api/messages/share-image', methods=['POST'])
@verified_required
@limiter.limit('20 per minute')
def share_image():
    recipient = (request.form.get('to') or '').strip()
    if 'file' not in request.files or not recipient:
        return jsonify({'success': False, 'message': 'Missing file or recipient'}), 400
    db = get_db()
    ok, err = can_interact(db, session['user_id'], recipient)
    if not ok:
        return jsonify({'success': False, 'message': err}), 403
    try:
        url = save_image_upload(request.files['file'], 'chat')
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    msg = Message(
        id=new_id(), from_user=session['user_id'], to_user=recipient,
        content=url, msg_type='image', sent_at=utcnow(),
    )
    db.add(msg)
    track_event(db, 'message', session['user_id'])
    db.commit()
    payload = msg.to_dict()
    socketio.emit('new_message', payload, room=recipient)
    return jsonify({'success': True, 'message': 'Image shared', 'data': payload}), 201


@app.route('/api/messages/<username>', methods=['GET'])
@verified_required
def get_messages(username):
    db = get_db()
    me = session['user_id']
    if either_blocked(db, me, username):
        return jsonify({'success': False, 'message': 'Unavailable'}), 403
    before = request.args.get('before')
    limit = min(int(request.args.get('limit', 50)), 100)
    q = select(Message).where(
        or_(
            and_(Message.from_user == me, Message.to_user == username),
            and_(Message.from_user == username, Message.to_user == me),
        )
    ).order_by(desc(Message.sent_at)).limit(limit)
    if before:
        q = select(Message).where(
            or_(
                and_(Message.from_user == me, Message.to_user == username),
                and_(Message.from_user == username, Message.to_user == me),
            ),
            Message.sent_at < before,
        ).order_by(desc(Message.sent_at)).limit(limit)
    rows = list(db.scalars(q))
    # mark read
    for m in rows:
        if m.to_user == me and not m.read:
            m.read = True
    db.commit()
    rows.reverse()
    return jsonify([m.to_dict() for m in rows]), 200


# ---------------------------------------------------------------------------
# Gifts / Stripe
# ---------------------------------------------------------------------------
def fulfill_gift_order(db, order: Order):
    if order.status == 'paid' and order.delivered:
        return order
    gift = get_gift_by_id(order.gift_id)
    if not gift:
        order.status = 'error'
        order.error = 'Gift not found'
        return order
    order.status = 'paid'
    order.paid_at = order.paid_at or utcnow()
    if order.delivered:
        return order

    gift_row = GiftSent(
        id=new_id(), order_id=order.id, gift_id=gift['id'], gift_name=gift['name'],
        gift_emoji=gift['emoji'], price_cents=gift['price_cents'], currency=order.currency,
        from_user=order.from_user, to_user=order.to_user, message=order.message or '',
        created_at=utcnow(),
    )
    db.add(gift_row)

    note = order.message or ''
    content = f"{gift['emoji']} Sent you a gift: {gift['name']}"
    if note:
        content += f"\n“{note}”"
    content += f"\n({format_price(gift['price_cents'], order.currency)})"
    msg = Message(
        id=new_id(), from_user=order.from_user, to_user=order.to_user,
        content=content, msg_type='gift', gift_id=gift['id'], order_id=order.id, sent_at=utcnow(),
    )
    db.add(msg)
    add_notification(db, order.to_user, order.from_user, 'gift',
                     f"{order.from_user} sent you {gift['emoji']} {gift['name']}")
    recipient = db.get(User, order.to_user)
    if recipient and recipient.email_on_gift:
        send_email(
            recipient.email,
            f'You received a gift on {APP_NAME}!',
            f"<h2>{gift['emoji']} New gift from {order.from_user}</h2>"
            f"<p><strong>{gift['name']}</strong> ({format_price(gift['price_cents'])})</p>"
            f"<p>{note}</p>"
        )
    socketio.emit('new_message', msg.to_dict(), room=order.to_user)
    track_event(db, 'gift_sent', order.from_user)
    track_event(db, 'gift_bought', order.from_user)
    order.delivered = True
    order.delivered_at = utcnow()
    # Admin revenue: 100% of gift sale goes to the platform Stripe account
    record_platform_payment(
        db,
        kind='gift',
        username=order.from_user,
        amount_cents=order.price_cents,
        currency=order.currency,
        description=f"Gift sale: {gift['name']} → @{order.to_user}",
        reference_id=order.id,
        stripe_session_id=order.stripe_session_id,
        stripe_payment_intent=order.stripe_payment_intent,
        meta={'gift_id': gift['id'], 'to': order.to_user},
    )
    return order


@app.route('/api/gifts')
def get_gifts():
    db = get_db()
    user = db.get(User, session['user_id']) if session.get('user_id') else None
    settings = get_platform_settings(db)
    catalog = []
    for g in GIFTS:
        charged = gift_price_for_user(db, g, user)
        catalog.append({
            **g,
            'list_price_cents': g['price_cents'],
            'price_cents': charged,
            'price': format_price(charged),
            'list_price': format_price(g['price_cents']),
            'discount_applied': charged < g['price_cents'],
            'currency': STRIPE_CURRENCY.upper(),
            'purchasable': True,
            'premium_discount_percent': settings.premium_gift_discount_percent if (user and user.is_premium_active()) else 0,
        })
    return jsonify(catalog), 200


@app.route('/api/gifts/checkout', methods=['POST'])
@verified_required
@limiter.limit('15 per minute')
def create_gift_checkout():
    data = request.json or {}
    gift = get_gift_by_id(data.get('gift_id'))
    recipient = (data.get('to') or '').strip()
    note = (data.get('message') or '').strip()[:500]
    sender = session['user_id']
    if not gift:
        return jsonify({'success': False, 'message': 'Gift not found'}), 404
    db = get_db()
    ok, err = can_interact(db, sender, recipient)
    if not ok:
        return jsonify({'success': False, 'message': err}), 403

    sender_user = db.get(User, sender)
    charged = gift_price_for_user(db, gift, sender_user)
    order = Order(
        id=new_id(), gift_id=gift['id'], gift_name=gift['name'],
        price_cents=charged, currency=STRIPE_CURRENCY,
        from_user=sender, to_user=recipient, message=note,
        status='pending', created_at=utcnow(),
    )
    db.add(order)
    db.flush()
    base = get_app_url()

    if not STRIPE_ENABLED:
        if IS_PRODUCTION:
            db.rollback()
            return jsonify({'success': False, 'message': 'Payments are not configured.'}), 503
        order.payment_mode = 'demo'
        fulfill_gift_order(db, order)
        db.commit()
        return jsonify({
            'success': True, 'demo': True,
            'message': f'Demo gift delivered to {recipient} (configure Stripe for real payments)',
            'order': order.to_dict(), 'checkout_url': None,
        }), 200

    try:
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': STRIPE_CURRENCY,
                    'unit_amount': charged,
                    'product_data': {
                        'name': f"{gift['emoji']} {gift['name']}",
                        'description': f'Gift for @{recipient} on {APP_NAME}' + (f' — {note}' if note else ''),
                    },
                },
                'quantity': 1,
            }],
            success_url=f"{base}/gifts/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/gifts/cancel?session_id={{CHECKOUT_SESSION_ID}}",
            client_reference_id=order.id,
            customer_email=sender_user.email,
            metadata={
                'product_type': 'gift',
                'order_id': order.id,
                'gift_id': str(gift['id']),
                'from': sender,
                'to': recipient,
            },
        )
        order.stripe_session_id = checkout_session.id
        db.commit()
        return jsonify({
            'success': True,
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
            'order_id': order.id,
        }), 200
    except Exception as e:
        db.rollback()
        print(f'Stripe checkout error: {e}')
        return jsonify({'success': False, 'message': f'Payment error: {str(e)}'}), 500


@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    if not STRIPE_ENABLED:
        return jsonify({'success': False, 'message': 'Stripe not configured'}), 503
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            if IS_PRODUCTION:
                return jsonify({'success': False, 'message': 'Webhook secret required'}), 400
            event = json.loads(payload)
    except Exception as e:
        print(f'Webhook signature error: {e}')
        return jsonify({'success': False, 'message': 'Invalid signature'}), 400

    event_type = event['type'] if isinstance(event, dict) else event.type
    data_object = event['data']['object'] if isinstance(event, dict) else event.data.object

    if event_type == 'checkout.session.completed':
        payment_status = data_object.get('payment_status') if isinstance(data_object, dict) else data_object.payment_status
        if payment_status == 'paid':
            metadata = data_object.get('metadata') if isinstance(data_object, dict) else (data_object.metadata or {})
            product_type = (metadata.get('product_type') if metadata else None) or 'gift'
            order_id = metadata.get('order_id') if metadata else None
            payment_id = metadata.get('payment_id') if metadata else None
            session_id = data_object.get('id') if isinstance(data_object, dict) else data_object.id
            payment_intent = data_object.get('payment_intent') if isinstance(data_object, dict) else data_object.payment_intent
            db = get_db()
            if product_type in ('premium', 'boost'):
                payment = db.get(PlatformPayment, payment_id) if payment_id else None
                if not payment and session_id:
                    payment = db.scalar(select(PlatformPayment).where(PlatformPayment.stripe_session_id == session_id))
                if payment:
                    payment.stripe_session_id = session_id
                    payment.stripe_payment_intent = payment_intent
                    fulfill_platform_product(db, payment)
                    db.commit()
            else:
                order = db.get(Order, order_id) if order_id else None
                if not order and session_id:
                    order = db.scalar(select(Order).where(Order.stripe_session_id == session_id))
                if order:
                    order.stripe_session_id = session_id
                    order.stripe_payment_intent = payment_intent
                    fulfill_gift_order(db, order)
                    db.commit()
    return jsonify({'received': True}), 200


@app.route('/api/gifts/sent')
@verified_required
def get_sent_gifts():
    db = get_db()
    rows = db.scalars(select(GiftSent).where(GiftSent.from_user == session['user_id']).order_by(desc(GiftSent.created_at)))
    return jsonify([g.to_dict() for g in rows]), 200


@app.route('/api/gifts/received')
@verified_required
def get_received_gifts():
    db = get_db()
    rows = db.scalars(select(GiftSent).where(GiftSent.to_user == session['user_id']).order_by(desc(GiftSent.created_at)))
    return jsonify([g.to_dict() for g in rows]), 200


@app.route('/api/orders')
@verified_required
def get_my_orders():
    db = get_db()
    rows = db.scalars(select(Order).where(Order.from_user == session['user_id']).order_by(desc(Order.created_at)))
    return jsonify([o.to_dict() for o in rows]), 200


# ---------------------------------------------------------------------------
# Admin monetization — Premium, Boosts, revenue ledger
# Gifts + Premium + Boosts are paid to the platform Stripe account.
# Admin withdraws via Stripe Dashboard payouts.
# ---------------------------------------------------------------------------
@app.route('/api/monetization')
def monetization_catalog():
    db = get_db()
    settings = get_platform_settings(db)
    me = None
    if session.get('user_id'):
        me = db.get(User, session['user_id'])
    return jsonify({
        'enabled': bool(settings.monetization_enabled),
        'currency': (settings.currency or STRIPE_CURRENCY).upper(),
        'stripe_enabled': STRIPE_ENABLED,
        'premium': {
            'price_cents': settings.premium_price_cents,
            'price': format_price(settings.premium_price_cents, settings.currency),
            'days': settings.premium_days,
            'gift_discount_percent': settings.premium_gift_discount_percent,
            'benefits': [
                f'{settings.premium_gift_discount_percent}% off all gifts',
                'Premium badge on your profile',
                'Higher visibility in Discover',
            ],
            'active': bool(me and me.is_premium_active()),
            'until': me.premium_until.isoformat() if me and me.premium_until else None,
        },
        'boost': {
            'price_cents': settings.boost_price_cents,
            'price': format_price(settings.boost_price_cents, settings.currency),
            'days': settings.boost_days,
            'benefits': [
                f'Featured at the top of Discover for {settings.boost_days} days',
                'Boosted badge on your profile',
            ],
            'active': bool(me and me.is_boosted()),
            'until': me.boost_until.isoformat() if me and me.boost_until else None,
        },
        'how_admin_earns': [
            '100% of gift purchases go to the platform Stripe account',
            '100% of Premium memberships go to the platform',
            '100% of Profile Boosts go to the platform',
            'Withdraw anytime from Stripe Dashboard → Balances → Payouts',
        ],
    }), 200


def _create_platform_checkout(db, *, kind, username, amount_cents, description):
    settings = get_platform_settings(db)
    if not settings.monetization_enabled:
        return None, ({'success': False, 'message': 'Monetization is disabled'}, 503)
    user = db.get(User, username)
    payment = PlatformPayment(
        id=new_id(),
        kind=kind,
        username=username,
        amount_cents=amount_cents,
        currency=settings.currency or STRIPE_CURRENCY,
        status='pending',
        description=description,
        reference_id=new_id(),
        created_at=utcnow(),
    )
    db.add(payment)
    db.flush()
    base = get_app_url()

    if not STRIPE_ENABLED:
        if IS_PRODUCTION:
            db.rollback()
            return None, ({'success': False, 'message': 'Payments are not configured.'}, 503)
        payment.meta_json = json.dumps({'payment_mode': 'demo'})
        fulfill_platform_product(db, payment)
        db.commit()
        return payment, ({
            'success': True,
            'demo': True,
            'message': f'Demo {kind} activated (configure Stripe for real payments)',
            'payment': payment.to_dict(),
            'user': user.private_dict() if user else None,
            'checkout_url': None,
        }, 200)

    try:
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': settings.currency or STRIPE_CURRENCY,
                    'unit_amount': amount_cents,
                    'product_data': {
                        'name': description,
                        'description': f'{APP_NAME} platform purchase',
                    },
                },
                'quantity': 1,
            }],
            success_url=f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/billing/cancel?session_id={{CHECKOUT_SESSION_ID}}",
            client_reference_id=payment.id,
            customer_email=user.email,
            metadata={
                'product_type': kind,
                'payment_id': payment.id,
                'username': username,
            },
        )
        payment.stripe_session_id = checkout_session.id
        db.commit()
        return payment, ({
            'success': True,
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
            'payment_id': payment.id,
        }, 200)
    except Exception as e:
        db.rollback()
        return None, ({'success': False, 'message': f'Payment error: {str(e)}'}, 500)


@app.route('/api/billing/premium/checkout', methods=['POST'])
@verified_required
@limiter.limit('10 per minute')
def checkout_premium():
    db = get_db()
    settings = get_platform_settings(db)
    _, result = _create_platform_checkout(
        db,
        kind='premium',
        username=session['user_id'],
        amount_cents=settings.premium_price_cents,
        description=f'{APP_NAME} Premium ({settings.premium_days} days)',
    )
    return jsonify(result[0]), result[1]


@app.route('/api/billing/boost/checkout', methods=['POST'])
@verified_required
@limiter.limit('10 per minute')
def checkout_boost():
    db = get_db()
    settings = get_platform_settings(db)
    _, result = _create_platform_checkout(
        db,
        kind='boost',
        username=session['user_id'],
        amount_cents=settings.boost_price_cents,
        description=f'{APP_NAME} Profile Boost ({settings.boost_days} days)',
    )
    return jsonify(result[0]), result[1]


@app.route('/billing/success')
@login_required
def billing_success():
    session_id = request.args.get('session_id', '').strip()
    if session_id and STRIPE_ENABLED:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            if checkout.payment_status == 'paid':
                db = get_db()
                payment_id = (checkout.metadata or {}).get('payment_id')
                payment = db.get(PlatformPayment, payment_id) if payment_id else None
                if not payment:
                    payment = db.scalar(select(PlatformPayment).where(PlatformPayment.stripe_session_id == session_id))
                if payment:
                    payment.stripe_session_id = session_id
                    payment.stripe_payment_intent = checkout.get('payment_intent')
                    fulfill_platform_product(db, payment)
                    db.commit()
        except Exception as e:
            print(f'Billing success fulfill error: {e}')
    return redirect(url_for('dashboard') + '?billing=success')


@app.route('/billing/cancel')
@login_required
def billing_cancel():
    session_id = request.args.get('session_id', '').strip()
    if session_id:
        db = get_db()
        payment = db.scalar(select(PlatformPayment).where(PlatformPayment.stripe_session_id == session_id))
        if payment and payment.status == 'pending':
            payment.status = 'cancelled'
            db.commit()
    return redirect(url_for('dashboard') + '?billing=cancelled')


@app.route('/api/admin/monetization', methods=['GET', 'POST'])
@admin_required
def admin_monetization_settings():
    db = get_db()
    settings = get_platform_settings(db)
    if request.method == 'GET':
        return jsonify(settings.to_dict()), 200
    data = request.json or {}
    if 'monetization_enabled' in data:
        settings.monetization_enabled = bool(data['monetization_enabled'])
    for key, lo, hi in (
        ('premium_price_cents', 100, 1000000),
        ('boost_price_cents', 100, 1000000),
        ('premium_days', 1, 365),
        ('boost_days', 1, 90),
        ('premium_gift_discount_percent', 0, 50),
    ):
        if key in data:
            try:
                val = int(data[key])
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': f'Invalid {key}'}), 400
            if not (lo <= val <= hi):
                return jsonify({'success': False, 'message': f'{key} must be between {lo} and {hi}'}), 400
            setattr(settings, key, val)
    if 'payout_note' in data:
        settings.payout_note = str(data['payout_note'])[:500]
    if 'currency' in data:
        settings.currency = str(data['currency']).lower()[:8]
    settings.updated_at = utcnow()
    db.commit()
    return jsonify({'success': True, 'settings': settings.to_dict()}), 200


@app.route('/api/admin/revenue')
@admin_required
def admin_revenue():
    db = get_db()
    settings = get_platform_settings(db)
    paid = list(db.scalars(select(PlatformPayment).where(PlatformPayment.status == 'paid')))
    by_kind = {'gift': 0, 'premium': 0, 'boost': 0}
    for p in paid:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + (p.amount_cents or 0)
    total = sum(by_kind.values())
    recent = list(db.scalars(
        select(PlatformPayment).where(PlatformPayment.status.in_(['paid', 'refunded']))
        .order_by(desc(PlatformPayment.created_at)).limit(100)
    ))
    premium_users = db.scalar(select(func.count()).select_from(User).where(User.premium_until.is_not(None))) or 0
    boosted_users = db.scalar(select(func.count()).select_from(User).where(User.boost_until.is_not(None))) or 0
    return jsonify({
        'total_revenue_cents': total,
        'total_revenue': format_price(total),
        'by_kind_cents': by_kind,
        'by_kind': {k: format_price(v) for k, v in by_kind.items()},
        'paid_payments': len(paid),
        'active_premium_approx': premium_users,
        'boosted_approx': boosted_users,
        'payout_note': settings.payout_note,
        'stripe_enabled': STRIPE_ENABLED,
        'settings': settings.to_dict(),
        'recent': [p.to_dict() for p in recent],
        'how_to_withdraw': (
            '1) Open https://dashboard.stripe.com/balance/overview\n'
            '2) Connect a bank account if needed\n'
            '3) Request a payout — gift, Premium, and Boost payments all land in this Stripe account'
        ),
    }), 200


@app.route('/api/admin/revenue/<payment_id>/refund', methods=['POST'])
@admin_required
def admin_refund_platform_payment(payment_id):
    db = get_db()
    payment = db.get(PlatformPayment, str(payment_id))
    if not payment:
        return jsonify({'success': False, 'message': 'Payment not found'}), 404
    if payment.status != 'paid':
        return jsonify({'success': False, 'message': 'Only paid items can be refunded'}), 400
    if payment.kind == 'gift':
        return jsonify({'success': False, 'message': 'Refund gift orders from the Orders section'}), 400

    def _deactivate():
        user = db.get(User, payment.username)
        if not user:
            return
        # Best-effort: clear entitlement immediately on refund
        if payment.kind == 'premium':
            user.premium_until = utcnow()
        elif payment.kind == 'boost':
            user.boost_until = utcnow()

    meta = {}
    try:
        meta = json.loads(payment.meta_json or '{}')
    except Exception:
        pass
    if meta.get('payment_mode') == 'demo' or not payment.stripe_payment_intent or not STRIPE_ENABLED:
        payment.status = 'refunded'
        payment.refunded_at = utcnow()
        _deactivate()
        db.commit()
        return jsonify({'success': True, 'message': 'Marked refunded', 'payment': payment.to_dict()}), 200
    try:
        refund = stripe.Refund.create(payment_intent=payment.stripe_payment_intent)
        payment.status = 'refunded'
        payment.stripe_refund_id = refund.id
        payment.refunded_at = utcnow()
        _deactivate()
        db.commit()
        return jsonify({'success': True, 'message': 'Refund issued', 'payment': payment.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
@app.route('/api/card-templates')
def get_card_templates():
    return jsonify(CARD_TEMPLATES), 200


@app.route('/api/cards/create', methods=['POST'])
@verified_required
def create_card():
    data = request.json or {}
    recipient = (data.get('to') or '').strip()
    db = get_db()
    ok, err = can_interact(db, session['user_id'], recipient)
    if not ok:
        return jsonify({'success': False, 'message': err}), 403
    card = Card(
        id=new_id(), from_user=session['user_id'], to_user=recipient,
        template_id=data.get('template_id'), message=(data.get('message') or '').strip(),
        created_at=utcnow(),
    )
    db.add(card)
    add_notification(db, recipient, session['user_id'], 'card', f"{session['user_id']} sent you a card")
    db.commit()
    return jsonify({'success': True, 'message': 'Card created', 'card': card.to_dict()}), 201


@app.route('/api/cards/received')
@verified_required
def get_received_cards():
    db = get_db()
    rows = db.scalars(select(Card).where(Card.to_user == session['user_id']).order_by(desc(Card.created_at)))
    return jsonify([c.to_dict() for c in rows]), 200


@app.route('/api/cards/<card_id>/view', methods=['POST'])
@verified_required
def view_card(card_id):
    db = get_db()
    card = db.get(Card, str(card_id))
    if not card or card.to_user != session['user_id']:
        return jsonify({'success': False, 'message': 'Card not found'}), 404
    card.viewed = True
    db.commit()
    return jsonify({'success': True, 'card': card.to_dict()}), 200


# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------
@app.route('/api/follow/<username>', methods=['POST'])
@verified_required
def follow_user(username):
    db = get_db()
    me = session['user_id']
    ok, err = can_interact(db, me, username, require_connection=False)
    if not ok:
        return jsonify({'success': False, 'message': err}), 400
    if db.scalar(select(Follow).where(Follow.follower == me, Follow.following == username)):
        return jsonify({'success': False, 'message': 'Already following'}), 400
    db.add(Follow(id=new_id(), follower=me, following=username, followed_at=utcnow()))
    track_event(db, 'follow', me)
    add_notification(db, username, me, 'follow', f'{me} started following you')
    db.commit()
    return jsonify({'success': True, 'message': 'Following user'}), 201


@app.route('/api/unfollow/<username>', methods=['POST'])
@verified_required
def unfollow_user(username):
    db = get_db()
    row = db.scalar(select(Follow).where(Follow.follower == session['user_id'], Follow.following == username))
    if row:
        db.delete(row)
        db.commit()
    return jsonify({'success': True, 'message': 'Unfollowed user'}), 200


@app.route('/api/followers/<username>', methods=['GET'])
@login_required
def get_followers(username):
    db = get_db()
    followers = [f.follower for f in db.scalars(select(Follow).where(Follow.following == username))]
    return jsonify({'followers': followers, 'count': len(followers)}), 200


@app.route('/api/following/<username>', methods=['GET'])
@login_required
def get_following(username):
    db = get_db()
    following = [f.following for f in db.scalars(select(Follow).where(Follow.follower == username))]
    return jsonify({'following': following, 'count': len(following)}), 200


@app.route('/api/like/<username>', methods=['POST'])
@verified_required
def like_user(username):
    db = get_db()
    me = session['user_id']
    ok, err = can_interact(db, me, username, require_connection=False)
    if not ok:
        return jsonify({'success': False, 'message': err}), 400
    if db.scalar(select(Like).where(Like.user == me, Like.likes_username == username)):
        return jsonify({'success': False, 'message': 'Already liked'}), 400
    db.add(Like(id=new_id(), user=me, likes_username=username, liked_at=utcnow()))
    track_event(db, 'like', me)
    add_notification(db, username, me, 'like', f'{me} liked you')
    db.commit()
    return jsonify({'success': True, 'message': 'Liked user'}), 201


@app.route('/api/unlike/<username>', methods=['POST'])
@verified_required
def unlike_user(username):
    db = get_db()
    row = db.scalar(select(Like).where(Like.user == session['user_id'], Like.likes_username == username))
    if row:
        db.delete(row)
        db.commit()
    return jsonify({'success': True, 'message': 'Unliked user'}), 200


@app.route('/api/likes/<username>', methods=['GET'])
@login_required
def get_user_likes(username):
    db = get_db()
    users_who_liked = [l.user for l in db.scalars(select(Like).where(Like.likes_username == username))]
    return jsonify({'likes': users_who_liked, 'count': len(users_who_liked)}), 200


@app.route('/api/notifications')
@verified_required
def get_notifications():
    db = get_db()
    rows = db.scalars(
        select(Notification).where(Notification.to_user == session['user_id'])
        .order_by(desc(Notification.created_at)).limit(100)
    )
    return jsonify([n.to_dict() for n in rows]), 200


@app.route('/api/notifications/<notif_id>/read', methods=['POST'])
@verified_required
def mark_notification_read(notif_id):
    db = get_db()
    n = db.get(Notification, str(notif_id))
    if not n or n.to_user != session['user_id']:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    n.read = True
    db.commit()
    return jsonify({'success': True}), 200


@app.route('/api/user/analytics')
@verified_required
def get_user_analytics():
    db = get_db()
    row = db.get(UserAnalytics, session['user_id'])
    return jsonify(row.to_dict() if row else {
        'page_views': 0, 'messages_sent': 0, 'follows': 0, 'likes': 0,
        'requests_sent': 0, 'gifts_sent': 0, 'gifts_bought': 0,
    }), 200


@app.route('/api/block/<username>', methods=['POST'])
@verified_required
def block_user(username):
    db = get_db()
    me = session['user_id']
    if username == me:
        return jsonify({'success': False, 'message': 'Cannot block yourself'}), 400
    if not db.get(User, username):
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if is_blocked(db, me, username):
        return jsonify({'success': False, 'message': 'User already blocked'}), 400
    db.add(Block(id=new_id(), blocker=me, blocked=username, created_at=utcnow()))
    # remove follows both ways
    for row in list(db.scalars(select(Follow).where(
        or_(
            and_(Follow.follower == me, Follow.following == username),
            and_(Follow.follower == username, Follow.following == me),
        )
    ))):
        db.delete(row)
    db.commit()
    return jsonify({'success': True, 'message': f'You blocked {username}'}), 201


@app.route('/api/unblock/<username>', methods=['POST'])
@verified_required
def unblock_user(username):
    db = get_db()
    row = db.scalar(select(Block).where(Block.blocker == session['user_id'], Block.blocked == username))
    if row:
        db.delete(row)
        db.commit()
    return jsonify({'success': True, 'message': f'You unblocked {username}'}), 200


@app.route('/api/user/blocked-list')
@verified_required
def get_blocked_list():
    db = get_db()
    blocked = [b.blocked for b in db.scalars(select(Block).where(Block.blocker == session['user_id']))]
    return jsonify({'blocked': blocked}), 200


@app.route('/api/report/<username>', methods=['POST'])
@verified_required
def report_user(username):
    data = request.json or {}
    db = get_db()
    if not db.get(User, username):
        return jsonify({'success': False, 'message': 'User not found'}), 404
    db.add(Report(
        id=new_id(), reporter=session['user_id'], reported=username,
        reason=(data.get('reason') or '').strip(),
        message=(data.get('message') or '').strip(),
        status='open', created_at=utcnow(),
    ))
    db.commit()
    return jsonify({'success': True, 'message': 'User reported successfully'}), 201


@app.route('/api/user/notification-settings', methods=['GET', 'POST'])
@verified_required
def notification_settings():
    db = get_db()
    user = db.get(User, session['user_id'])
    keys = ('email_on_message', 'email_on_request', 'email_on_like', 'email_on_follow', 'email_on_gift')
    if request.method == 'GET':
        return jsonify({k: bool(getattr(user, k)) for k in keys}), 200
    data = request.json or {}
    for k in keys:
        if k in data:
            setattr(user, k, bool(data[k]))
    db.commit()
    return jsonify({'success': True, 'message': 'Notification settings updated'}), 200


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
def _purge_user_data(db, username):
    for model, cols in [
        (Message, (Message.from_user, Message.to_user)),
        (ConnectionRequest, (ConnectionRequest.from_user, ConnectionRequest.to_user)),
        (Card, (Card.from_user, Card.to_user)),
        (Follow, (Follow.follower, Follow.following)),
        (Like, (Like.user, Like.likes_username)),
        (Notification, (Notification.to_user, Notification.from_user)),
        (Block, (Block.blocker, Block.blocked)),
        (Report, (Report.reporter, Report.reported)),
        (Order, (Order.from_user, Order.to_user)),
        (GiftSent, (GiftSent.from_user, GiftSent.to_user)),
        (AuthToken, (AuthToken.username,)),
    ]:
        for col in cols:
            for row in list(db.scalars(select(model).where(col == username))):
                db.delete(row)
    analytics = db.get(UserAnalytics, username)
    if analytics:
        db.delete(analytics)


@app.route('/api/admin/users')
@admin_required
def admin_get_users():
    db = get_db()
    users = db.scalars(select(User))
    follows = list(db.scalars(select(Follow)))
    likes = list(db.scalars(select(Like)))
    out = []
    for u in users:
        out.append({
            'username': u.username,
            'email': u.email,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'is_admin': bool(u.is_admin),
            'is_banned': bool(u.is_banned),
            'email_verified': bool(u.email_verified),
            'followers': sum(1 for f in follows if f.following == u.username),
            'following': sum(1 for f in follows if f.follower == u.username),
            'likes_received': sum(1 for l in likes if l.likes_username == u.username),
        })
    return jsonify(out), 200


@app.route('/api/admin/users/<username>/make-admin', methods=['POST'])
@admin_required
def make_admin(username):
    db = get_db()
    user = db.get(User, username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.is_admin = True
    db.commit()
    return jsonify({'success': True, 'message': f'{username} is now an admin'}), 200


@app.route('/api/admin/users/<username>/remove-admin', methods=['POST'])
@admin_required
def remove_admin(username):
    db = get_db()
    user = db.get(User, username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.is_admin = False
    db.commit()
    return jsonify({'success': True, 'message': f'{username} is no longer an admin'}), 200


@app.route('/api/admin/users/<username>/ban', methods=['POST'])
@admin_required
def ban_user(username):
    data = request.json or {}
    db = get_db()
    user = db.get(User, username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user.username == session['user_id']:
        return jsonify({'success': False, 'message': 'Cannot ban yourself'}), 400
    user.is_banned = True
    user.ban_reason = (data.get('reason') or '').strip()
    db.commit()
    return jsonify({'success': True, 'message': f'{username} banned'}), 200


@app.route('/api/admin/users/<username>/unban', methods=['POST'])
@admin_required
def unban_user(username):
    db = get_db()
    user = db.get(User, username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    user.is_banned = False
    user.ban_reason = ''
    db.commit()
    return jsonify({'success': True, 'message': f'{username} unbanned'}), 200


@app.route('/api/admin/users/<username>/delete', methods=['POST'])
@admin_required
def delete_user(username):
    db = get_db()
    user = db.get(User, username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if username == session['user_id']:
        return jsonify({'success': False, 'message': 'Cannot delete yourself'}), 400
    _purge_user_data(db, username)
    db.delete(user)
    db.commit()
    return jsonify({'success': True, 'message': f'User {username} deleted'}), 200


@app.route('/api/admin/reports')
@admin_required
def admin_reports():
    db = get_db()
    status = request.args.get('status', 'open')
    q = select(Report).order_by(desc(Report.created_at))
    if status != 'all':
        q = q.where(Report.status == status)
    return jsonify([r.to_dict() for r in db.scalars(q.limit(200))]), 200


@app.route('/api/admin/reports/<report_id>/resolve', methods=['POST'])
@admin_required
def resolve_report(report_id):
    data = request.json or {}
    db = get_db()
    report = db.get(Report, str(report_id))
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404
    action = (data.get('action') or 'resolve').lower()
    report.admin_note = (data.get('admin_note') or '').strip()
    report.resolved_by = session['user_id']
    report.resolved_at = utcnow()
    report.status = 'dismissed' if action == 'dismiss' else 'resolved'
    if data.get('ban_user'):
        user = db.get(User, report.reported)
        if user:
            user.is_banned = True
            user.ban_reason = report.admin_note or report.reason or 'Banned after report'
    db.commit()
    return jsonify({'success': True, 'report': report.to_dict()}), 200


@app.route('/api/admin/orders')
@admin_required
def admin_orders():
    db = get_db()
    rows = db.scalars(select(Order).order_by(desc(Order.created_at)).limit(200))
    return jsonify([o.to_dict() for o in rows]), 200


@app.route('/api/admin/orders/<order_id>/refund', methods=['POST'])
@admin_required
def refund_order(order_id):
    db = get_db()
    order = db.get(Order, str(order_id))
    if not order:
        return jsonify({'success': False, 'message': 'Order not found'}), 404
    if order.status != 'paid':
        return jsonify({'success': False, 'message': 'Only paid orders can be refunded'}), 400
    if order.payment_mode == 'demo' or not order.stripe_payment_intent or not STRIPE_ENABLED:
        order.status = 'refunded'
        order.refunded_at = utcnow()
        ledger = db.scalar(select(PlatformPayment).where(
            PlatformPayment.reference_id == order.id, PlatformPayment.kind == 'gift'
        ))
        if ledger and ledger.status == 'paid':
            ledger.status = 'refunded'
            ledger.refunded_at = utcnow()
        db.commit()
        return jsonify({'success': True, 'message': 'Order marked refunded', 'order': order.to_dict()}), 200
    try:
        refund = stripe.Refund.create(payment_intent=order.stripe_payment_intent)
        order.status = 'refunded'
        order.stripe_refund_id = refund.id
        order.refunded_at = utcnow()
        ledger = db.scalar(select(PlatformPayment).where(
            PlatformPayment.reference_id == order.id, PlatformPayment.kind == 'gift'
        ))
        if ledger and ledger.status == 'paid':
            ledger.status = 'refunded'
            ledger.stripe_refund_id = refund.id
            ledger.refunded_at = utcnow()
        db.commit()
        return jsonify({'success': True, 'message': 'Refund issued', 'order': order.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/stats')
@admin_required
def get_admin_stats():
    db = get_db()
    paid_orders = list(db.scalars(select(Order).where(Order.status == 'paid')))
    paid_platform = list(db.scalars(select(PlatformPayment).where(PlatformPayment.status == 'paid')))
    revenue_cents = sum(p.amount_cents or 0 for p in paid_platform) or sum(o.price_cents or 0 for o in paid_orders)
    by_kind = {'gift': 0, 'premium': 0, 'boost': 0}
    for p in paid_platform:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + (p.amount_cents or 0)
    return jsonify({
        'total_users': db.scalar(select(func.count()).select_from(User)) or 0,
        'total_connection_requests': db.scalar(select(func.count()).select_from(ConnectionRequest)) or 0,
        'total_messages': db.scalar(select(func.count()).select_from(Message)) or 0,
        'total_cards': db.scalar(select(func.count()).select_from(Card)) or 0,
        'total_follows': db.scalar(select(func.count()).select_from(Follow)) or 0,
        'total_likes': db.scalar(select(func.count()).select_from(Like)) or 0,
        'pending_requests': db.scalar(select(func.count()).select_from(ConnectionRequest).where(ConnectionRequest.status == 'pending')) or 0,
        'accepted_requests': db.scalar(select(func.count()).select_from(ConnectionRequest).where(ConnectionRequest.status == 'accepted')) or 0,
        'total_gifts_sent': db.scalar(select(func.count()).select_from(GiftSent)) or 0,
        'total_orders': db.scalar(select(func.count()).select_from(Order)) or 0,
        'paid_orders': len(paid_orders),
        'open_reports': db.scalar(select(func.count()).select_from(Report).where(Report.status == 'open')) or 0,
        'revenue_cents': revenue_cents,
        'revenue': format_price(revenue_cents),
        'revenue_by_kind': {k: format_price(v) for k, v in by_kind.items()},
        'revenue_by_kind_cents': by_kind,
        'stripe_enabled': STRIPE_ENABLED,
        'mail_configured': MAIL_CONFIGURED,
    }), 200


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@socketio.on('connect')
def handle_connect():
    username = session.get('user_id')
    if username:
        join_room(username)
        emit('connection_response', {'data': 'Connected!'})


@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('user_id')
    if username:
        leave_room(username)


@socketio.on('send_message')
def handle_message(data):
    sender = session.get('user_id')
    recipient = data.get('to')
    content = (data.get('content') or '').strip()
    if not all([sender, recipient, content]):
        emit('error', {'message': 'Missing data'})
        return
    db = get_db()
    user = db.get(User, sender)
    if not user or user.is_banned or (REQUIRE_EMAIL_CONFIRM and not user.email_verified):
        emit('error', {'message': 'Unauthorized'})
        return
    ok, err = can_interact(db, sender, recipient)
    if not ok:
        emit('error', {'message': err})
        return
    msg = Message(
        id=new_id(), from_user=sender, to_user=recipient,
        content=content, msg_type='text', sent_at=utcnow(),
    )
    db.add(msg)
    track_event(db, 'message', sender)
    db.commit()
    socketio.emit('new_message', msg.to_dict(), room=recipient)
    emit('message_sent', {'success': True, 'message': msg.to_dict()})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=not IS_PRODUCTION, port=port, host='0.0.0.0')
