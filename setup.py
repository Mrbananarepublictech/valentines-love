#!/usr/bin/env python3
"""TextLink — local setup helper."""
import os
import secrets


def main():
    print("=" * 60)
    print("  TextLink — Setup")
    print("=" * 60)
    os.makedirs('data/uploads', exist_ok=True)
    if not os.path.exists('.env'):
        key = secrets.token_hex(32)
        with open('.env', 'w') as f:
            f.write(f"""SECRET_KEY={key}
FLASK_ENV=development
APP_NAME=TextLink
REQUIRE_EMAIL_CONFIRM=true
REQUIRE_CONNECTION_TO_MESSAGE=true
# MAIL_USERNAME=
# MAIL_PASSWORD=
# STRIPE_SECRET_KEY=
# STRIPE_PUBLISHABLE_KEY=
# DATABASE_URL=
""")
        print("Created .env with a random SECRET_KEY")
    else:
        print(".env already exists — left unchanged")
    print("\nNext:")
    print("  pip install -r requirements.txt")
    print("  python3 app.py")
    print("  Open http://localhost:5000")
    print("\nBefore hosting, read HOSTING.md\n")


if __name__ == '__main__':
    main()
