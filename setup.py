#!/usr/bin/env python
"""
Valentine's Love Request - Installation & Setup Guide
================================================================================

This script helps you set up the Valentine's website with all features.
Run this after installing requirements.txt

Features Added:
✅ Profile pictures
✅ Chat/messaging between users
✅ Gift recommendations
✅ Email notifications
✅ Custom love cards
✅ User bios
"""

import os
import json
import sys

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def check_files():
    """Check if all necessary files exist"""
    print_header("📋 Checking Project Files")
    
    files_to_check = [
        ('app.py', 'Python Flask app'),
        ('requirements.txt', 'Dependencies list'),
        ('.env', 'Email configuration'),
        ('templates/index.html', 'Login page'),
        ('templates/dashboard.html', 'Main dashboard'),
        ('data/users.json', 'Users database'),
        ('data/requests.json', 'Valentine requests'),
        ('data/messages.json', 'Chat messages'),
        ('data/cards.json', 'Love cards'),
    ]
    
    all_good = True
    for file, desc in files_to_check:
        if os.path.exists(file):
            print(f"✅ {file:30} - {desc}")
        else:
            print(f"❌ {file:30} - {desc} (MISSING)")
            all_good = False
    
    return all_good

def setup_email():
    """Guide through email setup"""
    print_header("📧 Email Notifications Setup (OPTIONAL)")
    
    print("Email notifications allow users to get alerts when:")
    print("  - They receive a Valentine request")
    print("  - Someone responds to their request")
    print("\n" + "-"*70)
    print("📌 IMPORTANT: Email setup is OPTIONAL")
    print("   The app works great without it!")
    print("-"*70 + "\n")
    
    setup = input("Do you want to set up email notifications? (y/n): ").lower()
    
    if setup != 'y':
        print("\n✓ Skipping email setup. You can add it later by editing .env")
        return
    
    print("\n" + "-"*70)
    print("🔧 Email Setup Instructions")
    print("-"*70 + "\n")
    
    print("1. CHOOSE YOUR EMAIL PROVIDER:\n")
    print("   Gmail:")
    print("     - Go to https://myaccount.google.com")
    print("     - Enable 2-Step Verification")
    print("     - Go to https://myaccount.google.com/apppasswords")
    print("     - Select 'Mail' and 'Windows Computer'")
    print("     - Google will give you a 16-character password")
    print("     - Copy that password (NOT your regular Gmail password!)\n")
    
    print("   Outlook/Microsoft:")
    print("     - SMTP: smtp.office365.com")
    print("     - Port: 587")
    print("     - Use your full email and password\n")
    
    print("   Yahoo:")
    print("     - SMTP: smtp.mail.yahoo.com")
    print("     - Port: 587\n")
    
    provider = input("Which email provider? (gmail/outlook/yahoo/other): ").lower()
    
    if provider == 'gmail':
        email = input("Gmail address: ").strip()
        password = input("16-character app password from step above: ").strip()
        server = "smtp.gmail.com"
        port = 587
    elif provider == 'outlook':
        email = input("Outlook/Microsoft email: ").strip()
        password = input("Your password: ").strip()
        server = "smtp.office365.com"
        port = 587
    elif provider == 'yahoo':
        email = input("Yahoo email: ").strip()
        password = input("Your password: ").strip()
        server = "smtp.mail.yahoo.com"
        port = 587
    else:
        server = input("SMTP server address: ").strip()
        port = input("SMTP port (usually 587): ").strip()
        email = input("Email address: ").strip()
        password = input("Email password: ").strip()
    
    # Save to .env
    env_content = f"""# Valentine's Love - Email Configuration
SECRET_KEY=valentine_secret_2026_dev

# Email Settings
MAIL_SERVER={server}
MAIL_PORT={port}
MAIL_USE_TLS=True
MAIL_USERNAME={email}
MAIL_PASSWORD={password}
MAIL_DEFAULT_SENDER=noreply@valentineslove.com
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print(f"\n✅ Email configuration saved to .env")
    print(f"   Provider: {provider}")
    print(f"   Email: {email}")
    print(f"   Server: {server}:{port}")

def create_test_accounts():
    """Create sample test accounts"""
    print_header("👥 Create Test Accounts (OPTIONAL)")
    
    create = input("Create sample test accounts? (y/n): ").lower()
    
    if create != 'y':
        return
    
    from werkzeug.security import generate_password_hash
    
    users = {
        "john": {
            "username": "john",
            "email": "john@example.com",
            "password": generate_password_hash("password123"),
            "profile_picture": None,
            "bio": "Romantic guy",
            "created_at": "2026-02-05T10:00:00"
        },
        "jane": {
            "username": "jane",
            "email": "jane@example.com",
            "password": generate_password_hash("password123"),
            "profile_picture": None,
            "bio": "Looking for love",
            "created_at": "2026-02-05T10:05:00"
        }
    }
    
    with open('data/users.json', 'w') as f:
        json.dump(users, f, indent=4)
    
    print("\n✅ Created test accounts:")
    print("   Username: john, Password: password123")
    print("   Username: jane, Password: password123")
    print("\n💡 You can use these to test the app!")

def show_features():
    """Show all features"""
    print_header("✨ All Features Now Available")
    
    features = {
        "💕 Valentine Requests": [
            "Search for users",
            "Send romantic requests",
            "Accept or reject requests",
            "Respond with your own message"
        ],
        "👤 Profile Management": [
            "Upload profile picture",
            "Add bio/about me",
            "View other profiles"
        ],
        "💬 Direct Messaging": [
            "Chat with other users",
            "View conversation history",
            "Real-time updates"
        ],
        "🎁 Gift Recommendations": [
            "Browse 8 pre-made gift ideas",
            "Different price ranges",
            "Share favorites with match"
        ],
        "🎨 Custom Love Cards": [
            "Choose from 4 card templates",
            "Write custom messages",
            "Send beautiful cards",
            "Receive and view cards"
        ],
        "📧 Email Notifications": [
            "Get emailed when request arrives",
            "Get emailed when someone responds",
            "(Optional - fully configurable)"
        ]
    }
    
    for category, items in features.items():
        print(f"\n{category}")
        for item in items:
            print(f"  ✓ {item}")

def show_next_steps():
    """Show next steps"""
    print_header("🚀 Next Steps")
    
    print("1. Install dependencies:")
    print("   $ pip install -r requirements.txt\n")
    
    print("2. (Optional) Configure email:")
    print("   $ python setup.py  (this script)\n")
    
    print("3. Start the app:")
    print("   $ python app.py\n")
    
    print("4. Open browser:")
    print("   http://localhost:5000\n")
    
    print("5. Create accounts and start sending Valentine requests!\n")
    
    print("-"*70)
    print("💡 Pro Tips:")
    print("   - Profile pictures make the app more fun!")
    print("   - Add a bio so others can learn about you")
    print("   - Custom cards are great for expressing feelings")
    print("   - Email notifications keep you updated")
    print("   - Chat lets you get to know each other better")
    print("-"*70 + "\n")

def main():
    """Main setup function"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  Valentine's Love Request - Setup & Installation Guide".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    if check_files():
        print("\n✅ All project files found!")
    else:
        print("\n⚠️  Some files are missing. Please check the project structure.")
        return
    
    setup_email()
    create_test_accounts()
    show_features()
    show_next_steps()
    
    print("Happy Valentine's Day! 💕\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
