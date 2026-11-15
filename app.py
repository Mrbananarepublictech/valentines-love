from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from datetime import datetime, timezone
import json
import os
import base64
import uuid
import threading
from dotenv import load_dotenv

load_dotenv()

try:
    from flask_mail import Mail, Message
except ImportError:
    Mail, Message = None, None

try:
    import stripe
except ImportError:
    stripe = None

# ---------------------------------------------------------------------------
# App & production configuration
# ---------------------------------------------------------------------------
IS_PRODUCTION = os.getenv('FLASK_ENV', 'development').lower() == 'production'
APP_NAME = os.getenv('APP_NAME', 'TextLink')
APP_URL = os.getenv('APP_URL', '').rstrip('/')

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

_secret = os.getenv('SECRET_KEY')
if IS_PRODUCTION and (not _secret or _secret in ('your_secret_key_here', 'valentine_secret_2026', 'valentine_secret_2026_dev')):
    raise RuntimeError('Set a strong SECRET_KEY environment variable before running in production.')
app.secret_key = _secret or 'dev-only-insecure-textlink-key'

app.config.update(
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    UPLOAD_FOLDER='data/uploads',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
)

# Prefer eventlet for Socket.IO + gunicorn; fall back gracefully locally
socketio = SocketIO(app, cors_allowed_origins=os.getenv('CORS_ORIGINS', '*').split(','), async_mode='eventlet')

# Email
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', f'noreply@{APP_NAME.lower()}.com')
mail = Mail(app) if Mail else None

# Stripe (real money gift purchases)
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip()
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
STRIPE_CURRENCY = (os.getenv('STRIPE_CURRENCY', 'usd') or 'usd').lower()
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY and stripe)

if STRIPE_ENABLED:
    stripe.api_key = STRIPE_SECRET_KEY

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
USERS_FILE = 'data/users.json'
REQUESTS_FILE = 'data/requests.json'
MESSAGES_FILE = 'data/messages.json'
CARDS_FILE = 'data/cards.json'
FOLLOWS_FILE = 'data/follows.json'
LIKES_FILE = 'data/likes.json'
NOTIFICATIONS_FILE = 'data/notifications.json'
ANALYTICS_FILE = 'data/analytics.json'
BLOCKS_FILE = 'data/blocks.json'
REPORTS_FILE = 'data/reports.json'
ORDERS_FILE = 'data/orders.json'
GIFTS_SENT_FILE = 'data/gifts_sent.json'

_file_locks = {}
_file_locks_guard = threading.Lock()


def _lock_for(path):
    with _file_locks_guard:
        if path not in _file_locks:
            _file_locks[path] = threading.Lock()
        return _file_locks[path]


# Purchasable digital gifts (prices in cents for Stripe)
GIFTS = [
    {'id': 1, 'name': 'Red Roses Bouquet', 'emoji': '🌹', 'description': 'A classic dozen red roses delivered as a digital gift', 'price_cents': 1999, 'category': 'flowers'},
    {'id': 2, 'name': 'Chocolate Gift Box', 'emoji': '🍫', 'description': 'Luxury chocolates for someone special', 'price_cents': 1499, 'category': 'sweets'},
    {'id': 3, 'name': 'Sparkle Ring', 'emoji': '💎', 'description': 'Elegant jewelry gift token', 'price_cents': 4999, 'category': 'jewelry'},
    {'id': 4, 'name': 'Signature Perfume', 'emoji': '💐', 'description': 'Luxury fragrance gift', 'price_cents': 2999, 'category': 'perfume'},
    {'id': 5, 'name': 'Love Pendant', 'emoji': '❤️', 'description': 'Matching couple necklace gift', 'price_cents': 2499, 'category': 'jewelry'},
    {'id': 6, 'name': 'Dinner Night Out', 'emoji': '🍽️', 'description': 'Romantic dinner experience voucher', 'price_cents': 7999, 'category': 'experiences'},
    {'id': 7, 'name': 'Spa Package', 'emoji': '🧖', 'description': 'Relaxing spa treatment voucher', 'price_cents': 8999, 'category': 'experiences'},
    {'id': 8, 'name': 'Giant Teddy Bear', 'emoji': '🧸', 'description': 'Big fluffy teddy bear gift', 'price_cents': 3499, 'category': 'toys'},
    {'id': 9, 'name': 'Coffee Date', 'emoji': '☕', 'description': 'Treat them to coffee — a sweet small gift', 'price_cents': 599, 'category': 'experiences'},
    {'id': 10, 'name': 'Movie Night', 'emoji': '🎬', 'description': 'Streaming movie night gift card', 'price_cents': 1299, 'category': 'experiences'},
]

CARD_TEMPLATES = [
    {'id': 1, 'name': 'Warm Hello', 'bg': 'linear-gradient(135deg, #0f766e 0%, #14b8a6 100%)', 'icon': '💬'},
    {'id': 2, 'name': 'Soft Note', 'bg': 'linear-gradient(135deg, #be123c 0%, #fb7185 100%)', 'icon': '🌸'},
    {'id': 3, 'name': 'Bold Thanks', 'bg': 'linear-gradient(135deg, #1e3a5f 0%, #3b82f6 100%)', 'icon': '✨'},
    {'id': 4, 'name': 'Playful Vibes', 'bg': 'linear-gradient(135deg, #c2410c 0%, #f97316 100%)', 'icon': '🎉'},
]

os.makedirs('data/uploads', exist_ok=True)
os.makedirs('data', exist_ok=True)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_app_url():
    if APP_URL:
        return APP_URL
    return request.url_root.rstrip('/')


def init_data_files():
    defaults = {
        USERS_FILE: {},
        REQUESTS_FILE: [],
        MESSAGES_FILE: [],
        CARDS_FILE: [],
        FOLLOWS_FILE: [],
        LIKES_FILE: [],
        NOTIFICATIONS_FILE: [],
        ANALYTICS_FILE: {},
        BLOCKS_FILE: [],
        REPORTS_FILE: [],
        ORDERS_FILE: [],
        GIFTS_SENT_FILE: [],
    }
    for file, default_data in defaults.items():
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump(default_data, f)


init_data_files()


def load_json(path, default):
    lock = _lock_for(path)
    with lock:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return default if not callable(default) else default()


def save_json(path, data):
    lock = _lock_for(path)
    with lock:
        tmp = f'{path}.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)


def load_users():
    return load_json(USERS_FILE, {})


def save_users(users):
    save_json(USERS_FILE, users)


def load_requests():
    return load_json(REQUESTS_FILE, [])


def save_requests(requests_list):
    save_json(REQUESTS_FILE, requests_list)


def load_messages():
    return load_json(MESSAGES_FILE, [])


def save_messages(messages_list):
    save_json(MESSAGES_FILE, messages_list)


def load_cards():
    return load_json(CARDS_FILE, [])


def save_cards(cards_list):
    save_json(CARDS_FILE, cards_list)


def load_follows():
    return load_json(FOLLOWS_FILE, [])


def save_follows(follows_list):
    save_json(FOLLOWS_FILE, follows_list)


def load_likes():
    return load_json(LIKES_FILE, [])


def save_likes(likes_list):
    save_json(LIKES_FILE, likes_list)


def load_notifications():
    return load_json(NOTIFICATIONS_FILE, [])


def save_notifications(notifications_list):
    save_json(NOTIFICATIONS_FILE, notifications_list)


def load_analytics():
    return load_json(ANALYTICS_FILE, {})


def save_analytics(analytics_data):
    save_json(ANALYTICS_FILE, analytics_data)


def load_blocks():
    return load_json(BLOCKS_FILE, [])


def save_blocks(blocks_list):
    save_json(BLOCKS_FILE, blocks_list)


def load_reports():
    return load_json(REPORTS_FILE, [])


def save_reports(reports_list):
    save_json(REPORTS_FILE, reports_list)


def load_orders():
    return load_json(ORDERS_FILE, [])


def save_orders(orders_list):
    save_json(ORDERS_FILE, orders_list)


def load_gifts_sent():
    return load_json(GIFTS_SENT_FILE, [])


def save_gifts_sent(gifts_list):
    save_json(GIFTS_SENT_FILE, gifts_list)


def get_gift_by_id(gift_id):
    try:
        gift_id = int(gift_id)
    except (TypeError, ValueError):
        return None
    return next((g for g in GIFTS if g['id'] == gift_id), None)


def format_price(cents, currency=None):
    currency = (currency or STRIPE_CURRENCY).upper()
    amount = cents / 100.0
    if currency == 'USD':
        return f'${amount:.2f}'
    return f'{amount:.2f} {currency}'


def is_blocked(user1, user2):
    blocks = load_blocks()
    return any(b['blocker'] == user1 and b['blocked'] == user2 for b in blocks)


def track_event(event_type, username, details=None):
    analytics = load_analytics()
    if username not in analytics:
        analytics[username] = {
            'page_views': 0, 'messages_sent': 0, 'follows': 0,
            'likes': 0, 'requests_sent': 0, 'gifts_sent': 0, 'gifts_bought': 0
        }
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
        analytics[username][key] = analytics[username].get(key, 0) + 1
    save_analytics(analytics)


def is_admin(username):
    users = load_users()
    return users.get(username, {}).get('is_admin', False)


def add_notification(to_user, from_user, notif_type, message):
    notifications = load_notifications()
    notification = {
        'id': str(uuid.uuid4()),
        'to': to_user,
        'from': from_user,
        'type': notif_type,
        'message': message,
        'created_at': utc_now_iso(),
        'read': False,
    }
    notifications.append(notification)
    save_notifications(notifications)
    socketio.emit('user_notification', {
        'type': notif_type,
        'message': message,
        'from': from_user,
    }, room=to_user)
    return notification


def send_email(recipient, subject, html_content):
    if not recipient:
        return False
    if not mail or not app.config.get('MAIL_USERNAME'):
        print(f'[email skipped] to={recipient} subject={subject}')
        return True
    try:
        msg = Message(subject=subject, recipients=[recipient], html=html_content)
        mail.send(msg)
        return True
    except Exception as e:
        print(f'Email error: {e}')
        return False


def send_email_notification(to_email, subject, body):
    return send_email(to_email, subject, body)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Not logged in'}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'Not logged in'}), 401
            return redirect(url_for('index'))
        if not is_admin(session['user_id']):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def fulfill_gift_order(order):
    """Mark order paid and deliver the gift (idempotent)."""
    if order.get('status') == 'paid' and order.get('delivered'):
        return order

    gift = get_gift_by_id(order.get('gift_id'))
    if not gift:
        order['status'] = 'error'
        order['error'] = 'Gift not found'
        return order

    order['status'] = 'paid'
    order['paid_at'] = order.get('paid_at') or utc_now_iso()

    if order.get('delivered'):
        return order

    gift_record = {
        'id': str(uuid.uuid4()),
        'order_id': order['id'],
        'gift_id': gift['id'],
        'gift_name': gift['name'],
        'gift_emoji': gift['emoji'],
        'price_cents': gift['price_cents'],
        'currency': order.get('currency', STRIPE_CURRENCY),
        'from': order['from'],
        'to': order['to'],
        'message': order.get('message', ''),
        'created_at': utc_now_iso(),
    }

    gifts_sent = load_gifts_sent()
    gifts_sent.append(gift_record)
    save_gifts_sent(gifts_sent)

    # Also drop a chat message so it shows in conversations
    note = order.get('message') or ''
    content = f"{gift['emoji']} Sent you a gift: {gift['name']}"
    if note:
        content += f"\n“{note}”"
    content += f"\n({format_price(gift['price_cents'], order.get('currency'))})"

    messages_list = load_messages()
    messages_list.append({
        'from': order['from'],
        'to': order['to'],
        'content': content,
        'sent_at': utc_now_iso(),
        'read': False,
        'type': 'gift',
        'gift_id': gift['id'],
        'order_id': order['id'],
    })
    save_messages(messages_list)

    add_notification(
        order['to'],
        order['from'],
        'gift',
        f"{order['from']} sent you {gift['emoji']} {gift['name']}"
    )

    users = load_users()
    recipient = users.get(order['to'], {})
    if recipient.get('email'):
        send_email(
            recipient['email'],
            f"You received a gift on {APP_NAME}!",
            f"<h2>{gift['emoji']} New gift from {order['from']}</h2>"
            f"<p><strong>{gift['name']}</strong> ({format_price(gift['price_cents'])})</p>"
            f"<p>{note}</p>"
            f"<p><a href=\"{get_app_url()}/dashboard\">Open {APP_NAME}</a></p>"
        )

    socketio.emit('new_message', {
        'from': order['from'],
        'content': content,
        'sent_at': utc_now_iso(),
        'type': 'gift',
    }, room=order['to'])

    track_event('gift_sent', order['from'])
    track_event('gift_bought', order['from'])

    order['delivered'] = True
    order['delivered_at'] = utc_now_iso()
    return order


def update_order(order_id, updater):
    orders = load_orders()
    updated = None
    for i, order in enumerate(orders):
        if order.get('id') == order_id or order.get('stripe_session_id') == order_id:
            updated = updater(order)
            orders[i] = updated
            break
    if updated is not None:
        save_orders(orders)
    return updated


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', app_name=APP_NAME, stripe_enabled=STRIPE_ENABLED)


@app.route('/setup-admin')
def setup_admin():
    users = load_users()
    if not users:
        return jsonify({'success': False, 'message': 'No users exist yet. Register first.'}), 400
    if any(u.get('is_admin', False) for u in users.values()):
        return jsonify({'success': False, 'message': 'An admin already exists.'}), 400
    first_user = next(iter(users.keys()))
    users[first_user]['is_admin'] = True
    save_users(users)
    return jsonify({'success': True, 'message': f'{first_user} is now an admin!', 'admin': first_user}), 200


@app.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not all([username, email, password]):
        return jsonify({'success': False, 'message': 'All fields required'}), 400
    if len(username) < 3 or len(username) > 32:
        return jsonify({'success': False, 'message': 'Username must be 3–32 characters'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    users = load_users()
    if username in users:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    if any(u.get('email', '').lower() == email for u in users.values()):
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    users[username] = {
        'username': username,
        'email': email,
        'password': generate_password_hash(password),
        'profile_picture': None,
        'bio': '',
        'created_at': utc_now_iso(),
        'is_admin': len(users) == 0,  # first user becomes admin
        'interests': '',
        'relationship_status': 'Open',
        'theme': 'default',
        'email_on_message': True,
        'email_on_request': True,
        'email_on_like': False,
        'email_on_follow': False,
        'email_on_gift': True,
    }
    save_users(users)
    session.permanent = True
    session['user_id'] = username
    return jsonify({'success': True, 'message': 'Account created successfully'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    users = load_users()
    user = users.get(username)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    session.permanent = True
    session['user_id'] = username
    return jsonify({'success': True, 'message': 'Logged in successfully'}), 200


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    track_event('page_view', session['user_id'])
    return render_template(
        'dashboard.html',
        app_name=APP_NAME,
        stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
        stripe_enabled=STRIPE_ENABLED,
        currency=STRIPE_CURRENCY.upper(),
    )


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html', app_name=APP_NAME)


@app.route('/gifts/success')
@login_required
def gift_success():
    """Stripe redirects here after payment — fulfill if webhook has not yet."""
    session_id = request.args.get('session_id', '').strip()
    if session_id and STRIPE_ENABLED:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            if checkout.payment_status == 'paid':
                def _apply(order):
                    order['stripe_session_id'] = session_id
                    order['stripe_payment_intent'] = checkout.get('payment_intent')
                    return fulfill_gift_order(order)

                order_id = (checkout.metadata or {}).get('order_id')
                if order_id:
                    update_order(order_id, _apply)
                else:
                    update_order(session_id, _apply)
        except Exception as e:
            print(f'Gift success fulfill error: {e}')
    return redirect(url_for('dashboard') + '?gift=success')


@app.route('/gifts/cancel')
@login_required
def gift_cancel():
    session_id = request.args.get('session_id', '').strip()
    if session_id:
        update_order(session_id, lambda o: {**o, 'status': 'cancelled', 'cancelled_at': utc_now_iso()})
    return redirect(url_for('dashboard') + '?gift=cancelled')


# ---------------------------------------------------------------------------
# User APIs
# ---------------------------------------------------------------------------
@app.route('/api/config')
def public_config():
    return jsonify({
        'app_name': APP_NAME,
        'stripe_enabled': STRIPE_ENABLED,
        'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY if STRIPE_ENABLED else '',
        'currency': STRIPE_CURRENCY.upper(),
    }), 200


@app.route('/api/user')
@login_required
def get_user():
    users = load_users()
    user = users.get(session['user_id'])
    return jsonify({
        'username': user['username'],
        'email': user['email'],
        'profile_picture': user.get('profile_picture'),
        'bio': user.get('bio', ''),
        'created_at': user['created_at'],
        'is_admin': user.get('is_admin', False),
        'interests': user.get('interests', ''),
        'relationship_status': user.get('relationship_status', 'Open'),
        'theme': user.get('theme', 'default'),
    }), 200


@app.route('/api/user/<username>')
def get_user_profile(username):
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({
        'username': user['username'],
        'profile_picture': user.get('profile_picture'),
        'bio': user.get('bio', ''),
        'created_at': user['created_at'],
        'interests': user.get('interests', ''),
        'relationship_status': user.get('relationship_status', 'Open'),
    }), 200


@app.route('/api/user/profile-picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    if not file.content_type or not file.content_type.startswith('image/'):
        return jsonify({'success': False, 'message': 'File must be an image'}), 400
    try:
        image_data = file.read()
        encoded = base64.b64encode(image_data).decode('utf-8')
        image_base64 = f"data:{file.content_type};base64,{encoded}"
        users = load_users()
        users[session['user_id']]['profile_picture'] = image_base64
        save_users(users)
        return jsonify({'success': True, 'message': 'Profile picture updated'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/user/bio', methods=['POST'])
@login_required
def update_bio():
    data = request.json or {}
    bio = data.get('bio', '').strip()[:200]
    users = load_users()
    users[session['user_id']]['bio'] = bio
    save_users(users)
    return jsonify({'success': True, 'message': 'Bio updated'}), 200


@app.route('/api/user/profile', methods=['POST'])
@login_required
def update_profile():
    data = request.json or {}
    users = load_users()
    users[session['user_id']]['interests'] = data.get('interests', '').strip()[:200]
    users[session['user_id']]['relationship_status'] = data.get('relationship_status', 'Open').strip()
    users[session['user_id']]['theme'] = data.get('theme', 'default').strip()
    save_users(users)
    return jsonify({'success': True, 'message': 'Profile updated'}), 200


@app.route('/api/send-request', methods=['POST'])
@login_required
def send_request():
    data = request.json or {}
    recipient_username = data.get('recipient_username', '').strip()
    message = data.get('message', '').strip()
    users = load_users()
    requester = session['user_id']

    if requester == recipient_username:
        return jsonify({'success': False, 'message': 'Cannot send request to yourself'}), 400
    if recipient_username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if is_blocked(recipient_username, requester):
        return jsonify({'success': False, 'message': 'You cannot send a request to this user'}), 403

    requests_list = load_requests()
    if any(r['from'] == requester and r['to'] == recipient_username for r in requests_list):
        return jsonify({'success': False, 'message': 'You already sent a request to this user'}), 400

    new_request = {
        'id': str(uuid.uuid4()),
        'from': requester,
        'to': recipient_username,
        'message': message,
        'status': 'pending',
        'response_message': '',
        'sent_at': utc_now_iso(),
        'responded_at': None,
    }
    requests_list.append(new_request)
    save_requests(requests_list)
    track_event('request', requester)

    add_notification(recipient_username, requester, 'request', f'{requester} sent you a connection request')

    recipient_user = users.get(recipient_username, {})
    if recipient_user.get('email_on_request', True):
        send_email(
            recipient_user.get('email'),
            f'New connection request from {requester}',
            f'<h2>New request from {requester}</h2><p>{message}</p>'
            f'<p><a href="{get_app_url()}/dashboard">View request</a></p>'
        )

    return jsonify({'success': True, 'message': 'Request sent successfully'}), 201


@app.route('/api/requests/sent')
@login_required
def get_sent_requests():
    requester = session['user_id']
    return jsonify([r for r in load_requests() if r['from'] == requester]), 200


@app.route('/api/requests/received')
@login_required
def get_received_requests():
    recipient = session['user_id']
    return jsonify([r for r in load_requests() if r['to'] == recipient]), 200


@app.route('/api/requests/<request_id>/respond', methods=['POST'])
@login_required
def respond_to_request(request_id):
    data = request.json or {}
    response = data.get('response', '').lower()
    response_message = data.get('response_message', '').strip()
    recipient = session['user_id']
    requests_list = load_requests()

    req = next((r for r in requests_list if str(r['id']) == str(request_id) and r['to'] == recipient), None)
    if not req:
        return jsonify({'success': False, 'message': 'Request not found'}), 404
    if req['status'] != 'pending':
        return jsonify({'success': False, 'message': 'Request already responded to'}), 400
    if response not in ('accept', 'reject'):
        return jsonify({'success': False, 'message': 'Invalid response'}), 400

    req['status'] = 'accepted' if response == 'accept' else 'rejected'
    req['response_message'] = response_message
    req['responded_at'] = utc_now_iso()
    save_requests(requests_list)

    status_word = 'accepted' if response == 'accept' else 'declined'
    add_notification(req['from'], recipient, 'request_response', f'{recipient} {status_word} your connection request')

    users = load_users()
    requester_email = users.get(req['from'], {}).get('email')
    send_email(
        requester_email,
        f'Connection response from {recipient}',
        f'<h2>{recipient} {status_word} your request</h2><p>{response_message}</p>'
        f'<p><a href="{get_app_url()}/dashboard">Open {APP_NAME}</a></p>'
    )
    return jsonify({'success': True, 'message': f'Request {response}ed successfully'}), 200


@app.route('/api/search-user', methods=['GET'])
@login_required
def search_user():
    query = request.args.get('q', '').strip().lower()
    if len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short'}), 400
    users = load_users()
    me = session['user_id']
    results = [
        {
            'username': u['username'],
            'email': u['email'],
            'profile_picture': u.get('profile_picture'),
            'bio': u.get('bio', ''),
        }
        for username, u in users.items()
        if query in username.lower() and username != me and not is_blocked(me, username)
    ]
    return jsonify({'success': True, 'results': results}), 200


@app.route('/api/messages/send', methods=['POST'])
@login_required
def send_message():
    data = request.json or {}
    recipient = data.get('to', '').strip()
    content = data.get('content', '').strip()
    sender = session['user_id']
    users = load_users()

    if recipient not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not content:
        return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
    if is_blocked(recipient, sender) or is_blocked(sender, recipient):
        return jsonify({'success': False, 'message': 'You cannot message this user'}), 403

    message = {
        'from': sender,
        'to': recipient,
        'content': content,
        'sent_at': utc_now_iso(),
        'read': False,
        'type': 'text',
    }
    messages_list = load_messages()
    messages_list.append(message)
    save_messages(messages_list)
    track_event('message', sender)

    recipient_user = users.get(recipient, {})
    if recipient_user.get('email_on_message', True):
        send_email(
            recipient_user.get('email'),
            f'New message from {sender}',
            f'<h2>New message from {sender}</h2><p>{content}</p>'
            f'<p><a href="{get_app_url()}/dashboard">View message</a></p>'
        )

    socketio.emit('new_message', {
        'from': sender,
        'content': content,
        'sent_at': message['sent_at'],
        'type': 'text',
    }, room=recipient)
    return jsonify({'success': True, 'message': 'Message sent'}), 201


@app.route('/api/messages/share-image', methods=['POST'])
@login_required
def share_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    file = request.files['file']
    recipient = request.form.get('to', '').strip()
    if not file or not recipient:
        return jsonify({'success': False, 'message': 'Missing file or recipient'}), 400
    users = load_users()
    if recipient not in users:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    try:
        img_data = file.read()
        content_type = file.content_type or 'image/png'
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        message = {
            'from': session['user_id'],
            'to': recipient,
            'content': f'data:{content_type};base64,{img_base64}',
            'sent_at': utc_now_iso(),
            'read': False,
            'type': 'image',
        }
        messages_list = load_messages()
        messages_list.append(message)
        save_messages(messages_list)
        socketio.emit('new_message', {
            'from': session['user_id'],
            'content': '[Image shared]',
            'sent_at': message['sent_at'],
            'type': 'image',
        }, room=recipient)
        return jsonify({'success': True, 'message': 'Image shared'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/messages/<username>', methods=['GET'])
@login_required
def get_messages(username):
    current_user = session['user_id']
    conversation = [
        m for m in load_messages()
        if (m['from'] == current_user and m['to'] == username)
        or (m['from'] == username and m['to'] == current_user)
    ]
    return jsonify(conversation), 200


# ---------------------------------------------------------------------------
# Gifts + Stripe payments
# ---------------------------------------------------------------------------
@app.route('/api/gifts')
def get_gifts():
    catalog = []
    for g in GIFTS:
        catalog.append({
            **g,
            'price': format_price(g['price_cents']),
            'price_cents': g['price_cents'],
            'currency': STRIPE_CURRENCY.upper(),
            'purchasable': True,
        })
    return jsonify(catalog), 200


@app.route('/api/gifts/checkout', methods=['POST'])
@login_required
def create_gift_checkout():
    """Create a Stripe Checkout Session so the user can pay real money for a gift."""
    data = request.json or {}
    gift_id = data.get('gift_id')
    recipient = data.get('to', '').strip()
    note = (data.get('message') or '').strip()[:500]
    sender = session['user_id']
    users = load_users()

    gift = get_gift_by_id(gift_id)
    if not gift:
        return jsonify({'success': False, 'message': 'Gift not found'}), 404
    if not recipient:
        return jsonify({'success': False, 'message': 'Recipient username is required'}), 400
    if recipient == sender:
        return jsonify({'success': False, 'message': 'You cannot send a gift to yourself'}), 400
    if recipient not in users:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    if is_blocked(recipient, sender) or is_blocked(sender, recipient):
        return jsonify({'success': False, 'message': 'You cannot send a gift to this user'}), 403

    order = {
        'id': str(uuid.uuid4()),
        'gift_id': gift['id'],
        'gift_name': gift['name'],
        'price_cents': gift['price_cents'],
        'currency': STRIPE_CURRENCY,
        'from': sender,
        'to': recipient,
        'message': note,
        'status': 'pending',
        'delivered': False,
        'created_at': utc_now_iso(),
        'stripe_session_id': None,
    }

    base = get_app_url()

    if not STRIPE_ENABLED:
        # Development fallback — never charge real money without Stripe keys
        if IS_PRODUCTION:
            return jsonify({
                'success': False,
                'message': 'Payments are not configured. Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY.',
            }), 503
        order['status'] = 'paid'
        order['payment_mode'] = 'demo'
        order = fulfill_gift_order(order)
        orders = load_orders()
        orders.append(order)
        save_orders(orders)
        return jsonify({
            'success': True,
            'demo': True,
            'message': f'Demo gift delivered to {recipient} (configure Stripe for real payments)',
            'order': order,
            'checkout_url': None,
        }), 200

    try:
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': STRIPE_CURRENCY,
                    'unit_amount': gift['price_cents'],
                    'product_data': {
                        'name': f"{gift['emoji']} {gift['name']}",
                        'description': f"Gift for @{recipient} on {APP_NAME}" + (f' — {note}' if note else ''),
                    },
                },
                'quantity': 1,
            }],
            success_url=f"{base}/gifts/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/gifts/cancel?session_id={{CHECKOUT_SESSION_ID}}",
            client_reference_id=order['id'],
            customer_email=users[sender].get('email'),
            metadata={
                'order_id': order['id'],
                'gift_id': str(gift['id']),
                'from': sender,
                'to': recipient,
            },
        )
        order['stripe_session_id'] = checkout_session.id
        orders = load_orders()
        orders.append(order)
        save_orders(orders)
        return jsonify({
            'success': True,
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
            'order_id': order['id'],
        }), 200
    except Exception as e:
        print(f'Stripe checkout error: {e}')
        return jsonify({'success': False, 'message': f'Payment error: {str(e)}'}), 500


@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook — confirms real payments and delivers gifts."""
    if not STRIPE_ENABLED:
        return jsonify({'success': False, 'message': 'Stripe not configured'}), 503

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            # Allow unsigned events only outside production (local testing with Stripe CLI)
            if IS_PRODUCTION:
                return jsonify({'success': False, 'message': 'Webhook secret required'}), 400
            event = json.loads(payload)
    except Exception as e:
        print(f'Webhook signature error: {e}')
        return jsonify({'success': False, 'message': 'Invalid signature'}), 400

    event_type = event['type'] if isinstance(event, dict) else event.type
    data_object = event['data']['object'] if isinstance(event, dict) else event.data.object

    if event_type == 'checkout.session.completed':
        session_obj = data_object
        payment_status = session_obj.get('payment_status') if isinstance(session_obj, dict) else session_obj.payment_status
        if payment_status == 'paid':
            metadata = session_obj.get('metadata') if isinstance(session_obj, dict) else (session_obj.metadata or {})
            order_id = metadata.get('order_id') if metadata else None
            session_id = session_obj.get('id') if isinstance(session_obj, dict) else session_obj.id
            payment_intent = session_obj.get('payment_intent') if isinstance(session_obj, dict) else session_obj.payment_intent

            def _apply(order):
                order['stripe_session_id'] = session_id
                order['stripe_payment_intent'] = payment_intent
                return fulfill_gift_order(order)

            updated = None
            if order_id:
                updated = update_order(order_id, _apply)
            if updated is None and session_id:
                updated = update_order(session_id, _apply)
            if updated is None:
                print(f'Webhook: order not found for session {session_id}')

    return jsonify({'received': True}), 200


@app.route('/api/gifts/sent')
@login_required
def get_sent_gifts():
    me = session['user_id']
    return jsonify([g for g in load_gifts_sent() if g['from'] == me]), 200


@app.route('/api/gifts/received')
@login_required
def get_received_gifts():
    me = session['user_id']
    return jsonify([g for g in load_gifts_sent() if g['to'] == me]), 200


@app.route('/api/orders')
@login_required
def get_my_orders():
    me = session['user_id']
    return jsonify([o for o in load_orders() if o['from'] == me]), 200


@app.route('/api/card-templates')
def get_card_templates():
    return jsonify(CARD_TEMPLATES), 200


@app.route('/api/cards/create', methods=['POST'])
@login_required
def create_card():
    data = request.json or {}
    recipient = data.get('to', '').strip()
    users = load_users()
    if not recipient or recipient not in users:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    card = {
        'id': str(uuid.uuid4()),
        'from': session['user_id'],
        'to': recipient,
        'template_id': data.get('template_id'),
        'message': data.get('message', '').strip(),
        'created_at': utc_now_iso(),
        'viewed': False,
    }
    cards_list = load_cards()
    cards_list.append(card)
    save_cards(cards_list)
    add_notification(recipient, session['user_id'], 'card', f"{session['user_id']} sent you a card")
    return jsonify({'success': True, 'message': 'Card created', 'card': card}), 201


@app.route('/api/cards/received')
@login_required
def get_received_cards():
    return jsonify([c for c in load_cards() if c['to'] == session['user_id']]), 200


@app.route('/api/cards/<card_id>/view', methods=['POST'])
@login_required
def view_card(card_id):
    cards_list = load_cards()
    card = next((c for c in cards_list if str(c['id']) == str(card_id) and c['to'] == session['user_id']), None)
    if not card:
        return jsonify({'success': False, 'message': 'Card not found'}), 404
    card['viewed'] = True
    save_cards(cards_list)
    return jsonify({'success': True, 'card': card}), 200


@app.route('/api/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    current_user = session['user_id']
    users = load_users()
    if username == current_user:
        return jsonify({'success': False, 'message': 'Cannot follow yourself'}), 400
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    follows = load_follows()
    if any(f['follower'] == current_user and f['following'] == username for f in follows):
        return jsonify({'success': False, 'message': 'Already following'}), 400
    follows.append({'follower': current_user, 'following': username, 'followed_at': utc_now_iso()})
    save_follows(follows)
    track_event('follow', current_user)
    add_notification(username, current_user, 'follow', f'{current_user} started following you')
    return jsonify({'success': True, 'message': 'Following user'}), 201


@app.route('/api/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    current_user = session['user_id']
    follows = [f for f in load_follows() if not (f['follower'] == current_user and f['following'] == username)]
    save_follows(follows)
    return jsonify({'success': True, 'message': 'Unfollowed user'}), 200


@app.route('/api/followers/<username>', methods=['GET'])
def get_followers(username):
    followers = [f['follower'] for f in load_follows() if f['following'] == username]
    return jsonify({'followers': followers, 'count': len(followers)}), 200


@app.route('/api/following/<username>', methods=['GET'])
def get_following(username):
    following = [f['following'] for f in load_follows() if f['follower'] == username]
    return jsonify({'following': following, 'count': len(following)}), 200


@app.route('/api/like/<username>', methods=['POST'])
@login_required
def like_user(username):
    current_user = session['user_id']
    users = load_users()
    if username == current_user:
        return jsonify({'success': False, 'message': 'Cannot like yourself'}), 400
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    likes = load_likes()
    if any(l['user'] == current_user and l['likes_username'] == username for l in likes):
        return jsonify({'success': False, 'message': 'Already liked'}), 400
    likes.append({'user': current_user, 'likes_username': username, 'liked_at': utc_now_iso()})
    save_likes(likes)
    track_event('like', current_user)
    add_notification(username, current_user, 'like', f'{current_user} liked you')
    return jsonify({'success': True, 'message': 'Liked user'}), 201


@app.route('/api/unlike/<username>', methods=['POST'])
@login_required
def unlike_user(username):
    current_user = session['user_id']
    likes = [l for l in load_likes() if not (l['user'] == current_user and l['likes_username'] == username)]
    save_likes(likes)
    return jsonify({'success': True, 'message': 'Unliked user'}), 200


@app.route('/api/likes/<username>', methods=['GET'])
def get_user_likes(username):
    users_who_liked = [l['user'] for l in load_likes() if l['likes_username'] == username]
    return jsonify({'likes': users_who_liked, 'count': len(users_who_liked)}), 200


@app.route('/api/notifications')
@login_required
def get_notifications():
    user_notifications = [n for n in load_notifications() if n.get('to') == session['user_id']]
    user_notifications.sort(key=lambda n: n.get('created_at', ''), reverse=True)
    return jsonify(user_notifications), 200


@app.route('/api/notifications/<notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notifications = load_notifications()
    notif = next((n for n in notifications if str(n['id']) == str(notif_id) and n.get('to') == session['user_id']), None)
    if not notif:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    notif['read'] = True
    save_notifications(notifications)
    return jsonify({'success': True}), 200


@app.route('/api/admin/users')
@admin_required
def admin_get_users():
    users = load_users()
    follows = load_follows()
    likes = load_likes()
    user_list = []
    for username, user_data in users.items():
        user_list.append({
            'username': username,
            'email': user_data['email'],
            'created_at': user_data['created_at'],
            'is_admin': user_data.get('is_admin', False),
            'followers': len([f for f in follows if f['following'] == username]),
            'following': len([f for f in follows if f['follower'] == username]),
            'likes_received': len([l for l in likes if l['likes_username'] == username]),
        })
    return jsonify(user_list), 200


@app.route('/api/admin/users/<username>/make-admin', methods=['POST'])
@admin_required
def make_admin(username):
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    users[username]['is_admin'] = True
    save_users(users)
    return jsonify({'success': True, 'message': f'{username} is now an admin'}), 200


@app.route('/api/admin/users/<username>/remove-admin', methods=['POST'])
@admin_required
def remove_admin(username):
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    users[username]['is_admin'] = False
    save_users(users)
    return jsonify({'success': True, 'message': f'{username} is no longer an admin'}), 200


@app.route('/api/admin/users/<username>/delete', methods=['POST'])
@admin_required
def delete_user(username):
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if username == session['user_id']:
        return jsonify({'success': False, 'message': 'Cannot delete yourself'}), 400
    del users[username]
    save_users(users)
    return jsonify({'success': True, 'message': f'User {username} deleted'}), 200


@app.route('/api/user/analytics', methods=['GET'])
@login_required
def get_user_analytics():
    analytics = load_analytics()
    return jsonify(analytics.get(session['user_id'], {
        'page_views': 0, 'messages_sent': 0, 'follows': 0,
        'likes': 0, 'requests_sent': 0, 'gifts_sent': 0, 'gifts_bought': 0,
    })), 200


@app.route('/api/block/<username>', methods=['POST'])
@login_required
def block_user(username):
    current_user = session['user_id']
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if username == current_user:
        return jsonify({'success': False, 'message': 'Cannot block yourself'}), 400
    if is_blocked(current_user, username):
        return jsonify({'success': False, 'message': 'User already blocked'}), 400
    blocks = load_blocks()
    blocks.append({'blocker': current_user, 'blocked': username, 'created_at': utc_now_iso()})
    save_blocks(blocks)
    return jsonify({'success': True, 'message': f'You blocked {username}'}), 201


@app.route('/api/unblock/<username>', methods=['POST'])
@login_required
def unblock_user(username):
    current_user = session['user_id']
    blocks = [b for b in load_blocks() if not (b['blocker'] == current_user and b['blocked'] == username)]
    save_blocks(blocks)
    return jsonify({'success': True, 'message': f'You unblocked {username}'}), 200


@app.route('/api/user/blocked-list', methods=['GET'])
@login_required
def get_blocked_list():
    current_user = session['user_id']
    blocked_users = [b['blocked'] for b in load_blocks() if b['blocker'] == current_user]
    return jsonify({'blocked': blocked_users}), 200


@app.route('/api/report/<username>', methods=['POST'])
@login_required
def report_user(username):
    current_user = session['user_id']
    data = request.json or {}
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    reports = load_reports()
    reports.append({
        'reporter': current_user,
        'reported': username,
        'reason': data.get('reason', '').strip(),
        'message': data.get('message', '').strip(),
        'created_at': utc_now_iso(),
    })
    save_reports(reports)
    return jsonify({'success': True, 'message': 'User reported successfully'}), 201


@app.route('/api/user/notification-settings', methods=['GET', 'POST'])
@login_required
def notification_settings():
    users = load_users()
    username = session['user_id']
    if request.method == 'GET':
        user = users.get(username, {})
        return jsonify({
            'email_on_message': user.get('email_on_message', True),
            'email_on_request': user.get('email_on_request', True),
            'email_on_like': user.get('email_on_like', False),
            'email_on_follow': user.get('email_on_follow', False),
            'email_on_gift': user.get('email_on_gift', True),
        }), 200
    data = request.json or {}
    for key in ('email_on_message', 'email_on_request', 'email_on_like', 'email_on_follow', 'email_on_gift'):
        if key in data:
            users[username][key] = bool(data[key])
    save_users(users)
    return jsonify({'success': True, 'message': 'Notification settings updated'}), 200


@app.route('/api/admin/stats')
@admin_required
def get_admin_stats():
    orders = load_orders()
    paid_orders = [o for o in orders if o.get('status') == 'paid']
    revenue_cents = sum(o.get('price_cents', 0) for o in paid_orders)
    return jsonify({
        'total_users': len(load_users()),
        'total_valentine_requests': len(load_requests()),
        'total_connection_requests': len(load_requests()),
        'total_messages': len(load_messages()),
        'total_cards': len(load_cards()),
        'total_follows': len(load_follows()),
        'total_likes': len(load_likes()),
        'pending_requests': len([r for r in load_requests() if r['status'] == 'pending']),
        'accepted_requests': len([r for r in load_requests() if r['status'] == 'accepted']),
        'total_gifts_sent': len(load_gifts_sent()),
        'total_orders': len(orders),
        'paid_orders': len(paid_orders),
        'revenue_cents': revenue_cents,
        'revenue': format_price(revenue_cents),
        'stripe_enabled': STRIPE_ENABLED,
    }), 200


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'app': APP_NAME,
        'stripe': STRIPE_ENABLED,
        'env': 'production' if IS_PRODUCTION else 'development',
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
    content = data.get('content')
    if not all([sender, recipient, content]):
        emit('error', {'message': 'Missing data'})
        return
    if is_blocked(recipient, sender) or is_blocked(sender, recipient):
        emit('error', {'message': 'Blocked'})
        return
    message = {
        'from': sender,
        'to': recipient,
        'content': content,
        'sent_at': utc_now_iso(),
        'read': False,
        'type': 'text',
    }
    messages_list = load_messages()
    messages_list.append(message)
    save_messages(messages_list)
    track_event('message', sender)
    socketio.emit('new_message', {
        'from': sender,
        'content': content,
        'sent_at': message['sent_at'],
        'type': 'text',
    }, room=recipient)
    emit('message_sent', {'success': True, 'message': message})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=not IS_PRODUCTION, port=port, host='0.0.0.0')
