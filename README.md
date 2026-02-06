# Valentine's Love Request Website 💕

A complete web application where users can create accounts, send Valentine requests, chat, share gifts, and create custom love cards!

## ✨ Features

### 👤 Profile Management
- **Profile Pictures** - Upload and display profile pictures
- **Bio/About Me** - Add a personal bio visible to others
- **Profile View** - See others' profiles with pictures and bios

### 💌 Valentine Requests
- **Search Users** - Find users by username
- **Send Requests** - Send personalized Valentine requests
- **Track Status** - See pending/accepted/rejected requests
- **Respond** - Accept/reject requests with your own message

### 💬 Direct Messaging
- **Chat System** - Real-time messaging between users
- **Conversation History** - View past conversations
- **Easy Interface** - Simple chat with timestamps

### 🎁 Gift Recommendations
- **8 Pre-made Gift Ideas** - Flowers, jewelry, experiences, and more
- **Budget Options** - Cheap to luxury gifts
- **Easy Browsing** - Beautiful grid view

### 🎨 Custom Love Cards
- **4 Card Templates** - Different romantic designs
- **Custom Messages** - Write your own message
- **Card Delivery** - Send cards to other users
- **View Cards** - Receive cards in dashboard

### 📧 Email Notifications (Optional)
- Valentine request emails
- Response notification emails
- Fully configurable via .env

## 🚀 Quick Start

### 1. Install Dependencies
`bash
pip install -r requirements.txt
`

### 2. Configure Email (Optional)
Copy .env.example to .env and add email credentials for Gmail/Outlook.

### 3. Run the App
`bash
python app.py
`

Visit: http://localhost:5000

## 📋 Project Structure

- **app.py** - Flask backend with all features
- **requirements.txt** - Dependencies (Flask, Flask-Mail, Pillow)
- **.env** - Email configuration
- **templates/** - HTML files
  - index.html - Login/Register
  - dashboard.html - Main application
- **data/** - JSON storage
  - users.json
  - requests.json
  - messages.json
  - cards.json

## 📧 Email Setup (Optional)

### For Gmail:
1. Enable 2-Factor Authentication
2. Go to myaccount.google.com/apppasswords
3. Generate app password
4. Add to .env:
   - MAIL_USERNAME=your_email@gmail.com
   - MAIL_PASSWORD=16_char_password

### For Other Providers:
- Outlook: smtp.office365.com:587
- Yahoo: smtp.mail.yahoo.com:587
- Custom: Use your provider's SMTP settings

### Without Email:
- App works perfectly without email setup
- Notifications log to console instead

## 💻 How to Use

1. **Create Accounts** - Both users register
2. **Add Profiles** - Upload pictures, add bios
3. **Search & Send** - Find each other, send valentine request
4. **Accept/Reject** - Receive and respond
5. **Chat & Share** - Message, send cards, share gifts

## 🔐 Security

- Passwords hashed with Werkzeug
- Secure session management
- Profile pictures stored as base64
- Environment variables for secrets

## 🌟 Features Included

✅ Profile pictures
✅ Chat/messaging
✅ Gift recommendations
✅ Email notifications
✅ Custom love cards
✅ User search
✅ Request tracking
✅ Response messages

## 📞 Support

- Check data/users.json to verify accounts
- Usernames are case-sensitive
- Profile pictures must be under 5MB
- For Gmail, use app password not regular password

Made with ❤️ for Valentine's Day 2026
