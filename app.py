from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
try:
    from flask_mail import Mail, Message
except ImportError:
    Mail, Message = None, None
from functools import wraps
from datetime import datetime
import json
import os
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'valentine_secret_2026')
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size
app.config['UPLOAD_FOLDER'] = 'data/uploads'

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', True)
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@valentineslove.com')

mail = Mail(app)

# Data files
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

# Gift recommendations
GIFTS = [
    {'id': 1, 'name': 'Red Roses Bouquet', 'emoji': '🌹', 'description': 'A classic dozen red roses', 'price': '$50-100', 'link': '#', 'category': 'flowers'},
    {'id': 2, 'name': 'Chocolate Gift Box', 'emoji': '🍫', 'description': 'Luxury chocolates', 'price': '$20-50', 'link': '#', 'category': 'sweets'},
    {'id': 3, 'name': 'Diamond Ring', 'emoji': '💎', 'description': 'Elegant diamond jewelry', 'price': '$200-1000+', 'link': '#', 'category': 'jewelry'},
    {'id': 4, 'name': 'Perfume', 'emoji': '💐', 'description': 'Luxury fragrance', 'price': '$30-100', 'link': '#', 'category': 'perfume'},
    {'id': 5, 'name': 'Love Pendant', 'emoji': '❤️', 'description': 'Matching couple necklaces', 'price': '$40-150', 'link': '#', 'category': 'jewelry'},
    {'id': 6, 'name': 'Romantic Dinner', 'emoji': '🍽️', 'description': 'Dinner reservation at fancy restaurant', 'price': '$100-300', 'link': '#', 'category': 'experiences'},
    {'id': 7, 'name': 'Spa Package', 'emoji': '🧖', 'description': 'Couples spa treatment', 'price': '$150-300', 'link': '#', 'category': 'experiences'},
    {'id': 8, 'name': 'Teddy Bear', 'emoji': '🧸', 'description': 'Big fluffy teddy bear', 'price': '$20-80', 'link': '#', 'category': 'gifts'}
]

# Card templates
CARD_TEMPLATES = [
    {'id': 1, 'name': 'Classic Romance', 'bg': 'linear-gradient(135deg, #ff1744 0%, #f50057 100%)', 'icon': '💕'},
    {'id': 2, 'name': 'Cute & Sweet', 'bg': 'linear-gradient(135deg, #ff6b9d 0%, #c44569 100%)', 'icon': '🌸'},
    {'id': 3, 'name': 'Bold & Romantic', 'bg': 'linear-gradient(135deg, #ff1744 0%, #c51162 100%)', 'icon': '💖'},
    {'id': 4, 'name': 'Playful Love', 'bg': 'linear-gradient(135deg, #ff6b9d 0%, #ff1744 100%)', 'icon': '🎉'}
]

# Ensure directories exist
os.makedirs('data/uploads', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Initialize JSON files if they don't exist
def init_data_files():
    files = {
        USERS_FILE: {},
        REQUESTS_FILE: [],
        MESSAGES_FILE: [],
        CARDS_FILE: [],
        FOLLOWS_FILE: [],  # List of {follower, following} pairs
        LIKES_FILE: [],    # List of {user, likes_username} pairs
        NOTIFICATIONS_FILE: [],  # List of notifications
        ANALYTICS_FILE: {},  # Analytics data
        BLOCKS_FILE: [],  # List of {blocker, blocked} pairs
        REPORTS_FILE: []  # List of reports
    }
    for file, default_data in files.items():
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump(default_data, f)

init_data_files()

# Helper functions
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_requests():
    try:
        with open(REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_requests(requests_list):
    with open(REQUESTS_FILE, 'w') as f:
        json.dump(requests_list, f, indent=4)

def load_messages():
    try:
        with open(MESSAGES_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_messages(messages_list):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages_list, f, indent=4)

def load_cards():
    try:
        with open(CARDS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_cards(cards_list):
    with open(CARDS_FILE, 'w') as f:
        json.dump(cards_list, f, indent=4)

def load_follows():
    try:
        with open(FOLLOWS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_follows(follows_list):
    with open(FOLLOWS_FILE, 'w') as f:
        json.dump(follows_list, f, indent=4)

def load_likes():
    try:
        with open(LIKES_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_likes(likes_list):
    with open(LIKES_FILE, 'w') as f:
        json.dump(likes_list, f, indent=4)

def load_notifications():
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_notifications(notifications_list):
    with open(NOTIFICATIONS_FILE, 'w') as f:
        json.dump(notifications_list, f, indent=4)

def load_analytics():
    try:
        with open(ANALYTICS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_analytics(analytics_data):
    with open(ANALYTICS_FILE, 'w') as f:
        json.dump(analytics_data, f, indent=4)

def load_blocks():
    try:
        with open(BLOCKS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_blocks(blocks_list):
    with open(BLOCKS_FILE, 'w') as f:
        json.dump(blocks_list, f, indent=4)

def load_reports():
    try:
        with open(REPORTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_reports(reports_list):
    with open(REPORTS_FILE, 'w') as f:
        json.dump(reports_list, f, indent=4)

def is_blocked(user1, user2):
    """Check if user1 has blocked user2"""
    blocks = load_blocks()
    for block in blocks:
        if block['blocker'] == user1 and block['blocked'] == user2:
            return True
    return False

def track_event(event_type, username, details=None):
    """Track user events for analytics"""
    analytics = load_analytics()
    if username not in analytics:
        analytics[username] = {'page_views': 0, 'messages_sent': 0, 'follows': 0, 'likes': 0, 'requests_sent': 0}
    
    if event_type == 'page_view':
        analytics[username]['page_views'] = analytics[username].get('page_views', 0) + 1
    elif event_type == 'message':
        analytics[username]['messages_sent'] = analytics[username].get('messages_sent', 0) + 1
    elif event_type == 'follow':
        analytics[username]['follows'] = analytics[username].get('follows', 0) + 1
    elif event_type == 'like':
        analytics[username]['likes'] = analytics[username].get('likes', 0) + 1
    elif event_type == 'request':
        analytics[username]['requests_sent'] = analytics[username].get('requests_sent', 0) + 1
    
    save_analytics(analytics)

def is_admin(username):
    """Check if user is an admin"""
    users = load_users()
    user = users.get(username, {})
    return user.get('is_admin', False)

def send_email(recipient, subject, html_content):
    """Send email notification"""
    if not app.config['MAIL_USERNAME']:
        print(f"Email would be sent to {recipient}: {subject}")
        return True
    
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            html=html_content
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
        if not is_admin(session['user_id']):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/setup-admin')
def setup_admin():
    """Allow the first user to become an admin (setup only)"""
    users = load_users()
    
    # If no users exist, return error
    if not users:
        return jsonify({'success': False, 'message': 'No users exist yet. Register first.'}), 400
    
    # If an admin already exists, return error
    if any(u.get('is_admin', False) for u in users.values()):
        return jsonify({'success': False, 'message': 'An admin already exists.'}), 400
    
    # Make the first user an admin
    first_user = next(iter(users.keys()))
    users[first_user]['is_admin'] = True
    save_users(users)
    
    return jsonify({'success': True, 'message': f'{first_user} is now an admin!', 'admin': first_user}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not all([username, email, password]):
        return jsonify({'success': False, 'message': 'All fields required'}), 400
    
    users = load_users()
    
    if username in users:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    if any(u['email'] == email for u in users.values()):
        return jsonify({'success': False, 'message': 'Email already registered'}), 400
    
    users[username] = {
        'username': username,
        'email': email,
        'password': generate_password_hash(password),
        'profile_picture': None,
        'bio': '',
        'created_at': datetime.now().isoformat(),
        'is_admin': False,
        'interests': '',
        'relationship_status': 'Looking',
        'theme': 'default'
    }
    
    save_users(users)
    session['user_id'] = username
    
    return jsonify({'success': True, 'message': 'Account created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    users = load_users()
    user = users.get(username)
    
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    
    session['user_id'] = username
    return jsonify({'success': True, 'message': 'Logged in successfully'}), 200

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

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
        'created_at': user['created_at']
    }), 200

@app.route('/api/user/<username>')
def get_user_profile(username):
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    return jsonify({
        'username': user['username'],
        'email': user['email'],
        'profile_picture': user.get('profile_picture'),
        'bio': user.get('bio', ''),
        'created_at': user['created_at']
    }), 200

@app.route('/api/user/profile-picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if not file.content_type.startswith('image/'):
        return jsonify({'success': False, 'message': 'File must be an image'}), 400
    
    try:
        # Read and convert to base64
        image_data = file.read()
        encoded = base64.b64encode(image_data).decode('utf-8')
        image_base64 = f"data:{file.content_type};base64,{encoded}"
        
        # Save to user
        users = load_users()
        users[session['user_id']]['profile_picture'] = image_base64
        save_users(users)
        
        return jsonify({'success': True, 'message': 'Profile picture updated'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/user/bio', methods=['POST'])
@login_required
def update_bio():
    data = request.json
    bio = data.get('bio', '').strip()[:200]
    
    users = load_users()
    users[session['user_id']]['bio'] = bio
    save_users(users)
    
    return jsonify({'success': True, 'message': 'Bio updated'}), 200

@app.route('/api/user/profile', methods=['POST'])
@login_required
def update_profile():
    data = request.json
    interests = data.get('interests', '').strip()[:200]
    relationship_status = data.get('relationship_status', 'Looking').strip()
    theme = data.get('theme', 'default').strip()
    
    users = load_users()
    users[session['user_id']]['interests'] = interests
    users[session['user_id']]['relationship_status'] = relationship_status
    users[session['user_id']]['theme'] = theme
    save_users(users)
    
    track_event('profile_update', session['user_id'])
    
    return jsonify({'success': True, 'message': 'Profile updated'}), 200

@app.route('/api/send-request', methods=['POST'])
@login_required
def send_request():
    data = request.json
    recipient_username = data.get('recipient_username', '').strip()
    message = data.get('message', '').strip()
    
    users = load_users()
    requester = session['user_id']
    
    if requester == recipient_username:
        return jsonify({'success': False, 'message': 'Cannot send request to yourself'}), 400
    
    if recipient_username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Check if sender is blocked by recipient
    if is_blocked(recipient_username, requester):
        return jsonify({'success': False, 'message': 'You cannot send a request to this user'}), 403
    
    requests_list = load_requests()
    
    # Check if request already exists
    existing = any(r['from'] == requester and r['to'] == recipient_username for r in requests_list)
    if existing:
        return jsonify({'success': False, 'message': 'You already sent a request to this user'}), 400
    
    new_request = {
        'id': len(requests_list) + 1,
        'from': requester,
        'to': recipient_username,
        'message': message,
        'status': 'pending',
        'response_message': '',
        'sent_at': datetime.now().isoformat(),
        'responded_at': None
    }
    
    requests_list.append(new_request)
    save_requests(requests_list)
    
    # Send email notification if enabled
    recipient_user = users.get(recipient_username, {})
    if recipient_user.get('email_on_request', True):
        send_email_notification(
            recipient_user.get('email'),
            f'New Valentine Request from {requester}',
            f'<h2>💌 New Request from {requester}</h2><p>{message}</p><p><a href="http://localhost:5000/dashboard">View Request</a></p>'
        )
    
    # Send notification
    notification = {
        'id': len(load_notifications()) + 1,
        'from': requester,
        'type': 'request',
        'message': f'{requester} sent you a Valentine request',
        'created_at': datetime.now().isoformat(),
        'read': False
    }
    notifications_list = load_notifications()
    notifications_list.append(notification)
    save_notifications(notifications_list)
    
    socketio.emit('user_notification', {
        'message': f'{requester} sent you a Valentine request'
    }, room=recipient_username)
    # Send email notification
    recipient_email = users[recipient_username]['email']
    email_html = f"""
    <h2>You got a Valentine Request! 💕</h2>
    <p><strong>{requester}</strong> sent you a Valentine request!</p>
    <p><em>"{message}"</em></p>
    <p><a href="http://localhost:5000/dashboard">Login to respond</a></p>
    """
    send_email(recipient_email, "Valentine Request from " + requester, email_html)
    
    return jsonify({'success': True, 'message': 'Request sent successfully'}), 201

@app.route('/api/requests/sent')
@login_required
def get_sent_requests():
    requester = session['user_id']
    requests_list = load_requests()
    sent = [r for r in requests_list if r['from'] == requester]
    return jsonify(sent), 200

@app.route('/api/requests/received')
@login_required
def get_received_requests():
    recipient = session['user_id']
    requests_list = load_requests()
    received = [r for r in requests_list if r['to'] == recipient]
    return jsonify(received), 200

@app.route('/api/requests/<int:request_id>/respond', methods=['POST'])
@login_required
def respond_to_request(request_id):
    data = request.json
    response = data.get('response', '').lower()  # 'accept' or 'reject'
    response_message = data.get('response_message', '').strip()
    
    recipient = session['user_id']
    requests_list = load_requests()
    
    req = next((r for r in requests_list if r['id'] == request_id and r['to'] == recipient), None)
    
    if not req:
        return jsonify({'success': False, 'message': 'Request not found'}), 404
    
    if req['status'] != 'pending':
        return jsonify({'success': False, 'message': 'Request already responded to'}), 400
    
    if response == 'accept':
        req['status'] = 'accepted'
    elif response == 'reject':
        req['status'] = 'rejected'
    else:
        return jsonify({'success': False, 'message': 'Invalid response'}), 400
    
    req['response_message'] = response_message
    req['responded_at'] = datetime.now().isoformat()
    
    save_requests(requests_list)
    
    # Send email to the requester
    users = load_users()
    requester_email = users[req['from']]['email']
    status_text = "accepted your Valentine request! 💚" if response == 'accept' else "declined your Valentine request 💔"
    email_html = f"""
    <h2>{recipient} {status_text}</h2>
    <p><em>"{response_message}"</em></p>
    <p><a href="http://localhost:5000/dashboard">View response</a></p>
    """
    send_email(requester_email, f"Valentine Response from {recipient}", email_html)
    
    return jsonify({'success': True, 'message': f'Request {response}ed successfully'}), 200

@app.route('/api/search-user', methods=['GET'])
@login_required
def search_user():
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short'}), 400
    
    users = load_users()
    results = [u for username, u in users.items() if query in username.lower() and username != session['user_id']]
    
    return jsonify({
        'success': True,
        'results': [{
            'username': u['username'],
            'email': u['email'],
            'profile_picture': u.get('profile_picture'),
            'bio': u.get('bio', '')
        } for u in results]
    }), 200

# Messaging endpoints
@app.route('/api/messages/send', methods=['POST'])
@login_required
def send_message():
    data = request.json
    recipient = data.get('to', '').strip()
    content = data.get('content', '').strip()
    sender = session['user_id']
    
    users = load_users()
    
    if recipient not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if not content:
        return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
    
    # Check if sender is blocked by recipient
    if is_blocked(recipient, sender):
        return jsonify({'success': False, 'message': 'You cannot message this user'}), 403
    
    message = {
        'from': sender,
        'to': recipient,
        'content': content,
        'sent_at': datetime.now().isoformat(),
        'read': False,
        'type': 'text'
    }
    
    messages_list = load_messages()
    messages_list.append(message)
    save_messages(messages_list)
    
    # Send email notification if enabled
    recipient_user = users.get(recipient, {})
    if recipient_user.get('email_on_message', True):
        sender_user = users.get(sender, {})
        send_email_notification(
            recipient_user.get('email'),
            f'New Message from {sender}',
            f'<h2>💬 New Message from {sender}</h2><p>{content}</p><p><a href="http://localhost:5000/dashboard">View Message</a></p>'
        )
    
    # Emit via WebSocket
    socketio.emit('new_message', {
        'from': sender,
        'content': content,
        'sent_at': message['sent_at'],
        'type': 'text'
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
    
    # Convert image to base64
    try:
        img_data = file.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        message = {
            'from': session['user_id'],
            'to': recipient,
            'content': f'data:image/png;base64,{img_base64}',
            'sent_at': datetime.now().isoformat(),
            'read': False,
            'type': 'image'
        }
        
        messages_list = load_messages()
        messages_list.append(message)
        save_messages(messages_list)
        
        # Emit via WebSocket
        socketio.emit('new_message', {
            'from': session['user_id'],
            'content': f'[Image shared]',
            'sent_at': message['sent_at'],
            'type': 'image'
        }, room=recipient)
        
        return jsonify({'success': True, 'message': 'Image shared'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/messages/<username>', methods=['GET'])
@login_required
def get_messages(username):
    current_user = session['user_id']
    messages_list = load_messages()
    
    conversation = [m for m in messages_list if 
                   (m['from'] == current_user and m['to'] == username) or 
                   (m['from'] == username and m['to'] == current_user)]
    
    return jsonify(conversation), 200

@app.route('/api/gifts')
def get_gifts():
    return jsonify(GIFTS), 200

@app.route('/api/card-templates')
def get_card_templates():
    return jsonify(CARD_TEMPLATES), 200

@app.route('/api/cards/create', methods=['POST'])
@login_required
def create_card():
    data = request.json
    card = {
        'id': len(load_cards()) + 1,
        'from': session['user_id'],
        'to': data.get('to', '').strip(),
        'template_id': data.get('template_id'),
        'message': data.get('message', '').strip(),
        'created_at': datetime.now().isoformat(),
        'viewed': False
    }
    
    cards_list = load_cards()
    cards_list.append(card)
    save_cards(cards_list)
    
    return jsonify({'success': True, 'message': 'Card created', 'card': card}), 201

@app.route('/api/cards/received')
@login_required
def get_received_cards():
    cards_list = load_cards()
    received = [c for c in cards_list if c['to'] == session['user_id']]
    return jsonify(received), 200

@app.route('/api/cards/<int:card_id>/view', methods=['POST'])
@login_required
def view_card(card_id):
    cards_list = load_cards()
    card = next((c for c in cards_list if c['id'] == card_id and c['to'] == session['user_id']), None)
    
    if not card:
        return jsonify({'success': False, 'message': 'Card not found'}), 404
    
    card['viewed'] = True
    save_cards(cards_list)
    
    return jsonify({'success': True, 'card': card}), 200

# ============= NEW FEATURES =============

# Following System
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
    
    # Check if already following
    if any(f['follower'] == current_user and f['following'] == username for f in follows):
        return jsonify({'success': False, 'message': 'Already following'}), 400
    
    follows.append({
        'follower': current_user,
        'following': username,
        'followed_at': datetime.now().isoformat()
    })
    save_follows(follows)
    
    # Add notification
    notifications = load_notifications()
    notifications.append({
        'id': len(notifications) + 1,
        'type': 'follow',
        'from': current_user,
        'to': username,
        'message': f'{current_user} started following you',
        'created_at': datetime.now().isoformat(),
        'read': False
    })
    save_notifications(notifications)
    
    # Emit WebSocket event
    socketio.emit('user_notification', {
        'type': 'follow',
        'message': f'{current_user} started following you',
        'from': current_user
    }, room=username)
    
    return jsonify({'success': True, 'message': 'Following user'}), 201

@app.route('/api/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    current_user = session['user_id']
    follows = load_follows()
    
    follows[:] = [f for f in follows if not (f['follower'] == current_user and f['following'] == username)]
    save_follows(follows)
    
    return jsonify({'success': True, 'message': 'Unfollowed user'}), 200

@app.route('/api/followers/<username>', methods=['GET'])
def get_followers(username):
    follows = load_follows()
    followers = [f['follower'] for f in follows if f['following'] == username]
    return jsonify({'followers': followers, 'count': len(followers)}), 200

@app.route('/api/following/<username>', methods=['GET'])
def get_following(username):
    follows = load_follows()
    following = [f['following'] for f in follows if f['follower'] == username]
    return jsonify({'following': following, 'count': len(following)}), 200

# Likes/Favorites System
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
    
    # Check if already liked
    if any(l['user'] == current_user and l['likes_username'] == username for l in likes):
        return jsonify({'success': False, 'message': 'Already liked'}), 400
    
    likes.append({
        'user': current_user,
        'likes_username': username,
        'liked_at': datetime.now().isoformat()
    })
    save_likes(likes)
    
    # Add notification
    notifications = load_notifications()
    notifications.append({
        'id': len(notifications) + 1,
        'type': 'like',
        'from': current_user,
        'to': username,
        'message': f'{current_user} liked you! 💕',
        'created_at': datetime.now().isoformat(),
        'read': False
    })
    save_notifications(notifications)
    
    # Emit WebSocket event
    socketio.emit('user_notification', {
        'type': 'like',
        'message': f'{current_user} liked you! 💕',
        'from': current_user
    }, room=username)
    
    return jsonify({'success': True, 'message': 'Liked user'}), 201

@app.route('/api/unlike/<username>', methods=['POST'])
@login_required
def unlike_user(username):
    current_user = session['user_id']
    likes = load_likes()
    
    likes[:] = [l for l in likes if not (l['user'] == current_user and l['likes_username'] == username)]
    save_likes(likes)
    
    return jsonify({'success': True, 'message': 'Unliked user'}), 200

@app.route('/api/likes/<username>', methods=['GET'])
def get_user_likes(username):
    likes = load_likes()
    users_who_liked = [l['user'] for l in likes if l['likes_username'] == username]
    return jsonify({'likes': users_who_liked, 'count': len(users_who_liked)}), 200

# Notifications
@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = load_notifications()
    user_notifications = [n for n in notifications if n['to'] == session['user_id']]
    return jsonify(user_notifications), 200

@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notifications = load_notifications()
    notif = next((n for n in notifications if n['id'] == notif_id and n['to'] == session['user_id']), None)
    
    if not notif:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    
    notif['read'] = True
    save_notifications(notifications)
    
    return jsonify({'success': True}), 200

# Admin Dashboard
@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/api/admin/users')
@admin_required
def admin_get_users():
    users = load_users()
    user_list = []
    follows = load_follows()
    likes = load_likes()
    
    for username, user_data in users.items():
        followers_count = len([f for f in follows if f['following'] == username])
        following_count = len([f for f in follows if f['follower'] == username])
        likes_count = len([l for l in likes if l['likes_username'] == username])
        
        user_list.append({
            'username': username,
            'email': user_data['email'],
            'created_at': user_data['created_at'],
            'is_admin': user_data.get('is_admin', False),
            'followers': followers_count,
            'following': following_count,
            'likes_received': likes_count
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
    
    del users[username]
    save_users(users)
    
    return jsonify({'success': True, 'message': f'User {username} deleted'}), 200

@app.route('/api/user/analytics', methods=['GET'])
@login_required
def get_user_analytics():
    analytics = load_analytics()
    user_analytics = analytics.get(session['user_id'], {
        'page_views': 0,
        'messages_sent': 0,
        'follows': 0,
        'likes': 0,
        'requests_sent': 0
    })
    return jsonify(user_analytics), 200

@app.route('/api/block/<username>', methods=['POST'])
@login_required
def block_user(username):
    current_user = session['user_id']
    users = load_users()
    
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if username == current_user:
        return jsonify({'success': False, 'message': 'Cannot block yourself'}), 400
    
    blocks = load_blocks()
    
    # Check if already blocked
    if is_blocked(current_user, username):
        return jsonify({'success': False, 'message': 'User already blocked'}), 400
    
    blocks.append({'blocker': current_user, 'blocked': username, 'created_at': datetime.now().isoformat()})
    save_blocks(blocks)
    
    return jsonify({'success': True, 'message': f'You blocked {username}'}), 201

@app.route('/api/unblock/<username>', methods=['POST'])
@login_required
def unblock_user(username):
    current_user = session['user_id']
    blocks = load_blocks()
    
    blocks = [b for b in blocks if not (b['blocker'] == current_user and b['blocked'] == username)]
    save_blocks(blocks)
    
    return jsonify({'success': True, 'message': f'You unblocked {username}'}), 200

@app.route('/api/user/blocked-list', methods=['GET'])
@login_required
def get_blocked_list():
    current_user = session['user_id']
    blocks = load_blocks()
    blocked_users = [b['blocked'] for b in blocks if b['blocker'] == current_user]
    return jsonify({'blocked': blocked_users}), 200

@app.route('/api/report/<username>', methods=['POST'])
@login_required
def report_user(username):
    current_user = session['user_id']
    data = request.json
    reason = data.get('reason', '').strip()
    message_text = data.get('message', '').strip()
    
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    reports = load_reports()
    reports.append({
        'reporter': current_user,
        'reported': username,
        'reason': reason,
        'message': message_text,
        'created_at': datetime.now().isoformat()
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
            'email_on_follow': user.get('email_on_follow', False)
        }), 200
    
    # POST - Update settings
    data = request.json
    users[username]['email_on_message'] = data.get('email_on_message', True)
    users[username]['email_on_request'] = data.get('email_on_request', True)
    users[username]['email_on_like'] = data.get('email_on_like', False)
    users[username]['email_on_follow'] = data.get('email_on_follow', False)
    save_users(users)
    
    return jsonify({'success': True, 'message': 'Notification settings updated'}), 200

def send_email_notification(to_email, subject, body):
    """Send email notification"""
    if not mail or not Mail:
        print(f'Email disabled. Would send to {to_email}: {subject}')
        return
    
    try:
        msg = Message(subject, recipients=[to_email], body=body, html=body.replace('\n', '<br>'))
        mail.send(msg)
        return True
    except Exception as e:
        print(f'Error sending email: {e}')
        return False

@app.route('/api/admin/stats')
@admin_required
def get_admin_stats():
    users = load_users()
    requests_list = load_requests()
    messages_list = load_messages()
    cards_list = load_cards()
    follows = load_follows()
    likes = load_likes()
    
    return jsonify({
        'total_users': len(users),
        'total_valentine_requests': len(requests_list),
        'total_messages': len(messages_list),
        'total_cards': len(cards_list),
        'total_follows': len(follows),
        'total_likes': len(likes),
        'pending_requests': len([r for r in requests_list if r['status'] == 'pending']),
        'accepted_requests': len([r for r in requests_list if r['status'] == 'accepted'])
    }), 200

# WebSocket Events
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
    
    # Save message
    message = {
        'from': sender,
        'to': recipient,
        'content': content,
        'sent_at': datetime.now().isoformat(),
        'read': False
    }
    
    messages_list = load_messages()
    messages_list.append(message)
    save_messages(messages_list)
    
    # Emit to recipient in real-time
    socketio.emit('new_message', {
        'from': sender,
        'content': content,
        'sent_at': message['sent_at']
    }, room=recipient)
    
    # Also emit to sender to confirm
    emit('message_sent', {'success': True, 'message': message})

if __name__ == '__main__':
    # Production or development settings
    import os
    debug_mode = os.getenv('FLASK_ENV', 'development') == 'development'
    port = int(os.getenv('PORT', 5000))
    
    if debug_mode:
        socketio.run(app, debug=True, port=port, host='0.0.0.0')
    else:
        socketio.run(app, debug=False, port=port, host='0.0.0.0')
