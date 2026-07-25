#!/usr/bin/env python3

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from datetime import datetime
# Load environment variables
load_dotenv()

def test_smtp_connection():
    """Test SMTP connection and send a test email."""

    print("🧪 Testing SMTP Configuration")
    print("=" * 40)

    # Get SMTP settings from environment
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("FROM_EMAIL")
    from_name = os.getenv("FROM_NAME", "Tech News Digest")

    # Validate required settings
    missing_settings = []
    if not smtp_server:
        missing_settings.append("SMTP_SERVER")
    if not smtp_username:
        missing_settings.append("SMTP_USERNAME")
    if not smtp_password:
        missing_settings.append("SMTP_PASSWORD")
    if not from_email:
        missing_settings.append("FROM_EMAIL")

    if missing_settings:
        print(f"❌ Missing required settings: {', '.join(missing_settings)}")
        print("\n💡 Please update your .env file with these settings:")
        for setting in missing_settings:
            print(f"   {setting}=your_value_here")
        return False

    print(f"📧 SMTP Server: {smtp_server}:{smtp_port}")
    print(f"👤 Username: {smtp_username}")
    print(f"📤 From: {from_name} <{from_email}>")
    print(f"📥 Test recipient: {smtp_username}")
    print()

    try:
        # Create test email
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = smtp_username  # Send to yourself for testing
        msg['Subject'] = "🧪 SMTP Test - Digest System Configuration"

        # Create email body
        text_body = """
✅ SMTP Configuration Test Successful!
Your digest system email configuration is working correctly.
System Details:
- SMTP Server: {smtp_server}:{smtp_port}
- From Address: {from_email}
- Test Time: {timestamp}
🎉 Your personalized digest emails will be delivered successfully!
---
Tech News Digest System
        """.format(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            from_email=from_email,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        html_body = f"""
        <html>
        <head></head>
        <body>
            <h2 style="color: #2c3e50;">✅ SMTP Test Successful!</h2>
            <p>Your digest system email configuration is working correctly.</p>
            
            <h3 style="color: #34495e;">System Details:</h3>
            <ul>
                <li><strong>SMTP Server:</strong> {smtp_server}:{smtp_port}</li>
                <li><strong>From Address:</strong> {from_email}</li>
                <li><strong>Test Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            
            <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #155724; margin: 0;">🎉 Success!</h4>
                <p style="color: #155724; margin: 5px 0 0 0;">Your personalized digest emails will be delivered successfully!</p>
            </div>
            
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">Tech News Digest System</p>
        </body>
        </html>
        """

        # Attach both versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        print("🔄 Connecting to SMTP server...")

        # Connect and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(0)  # Set to 1 for debug output

        print("🔐 Starting TLS encryption...")
        server.starttls()

        print("🔑 Authenticating...")
        server.login(smtp_username, smtp_password)

        print("📤 Sending test email...")
        server.send_message(msg)
        server.quit()

        print()
        print("✅ SUCCESS! Test email sent successfully!")
        print(f"📬 Check your inbox at: {smtp_username}")
        print()
        print("🎯 Next steps:")
        print("   1. Check your email inbox for the test message")
        print("   2. If received, your SMTP is configured correctly")
        print("   3. You can now send digest emails to users")
        print("   4. Start the scheduler: python scheduler_service.py")

        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ AUTHENTICATION FAILED: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   - Gmail: Use App Password, not regular password")
        print("   - Yahoo: Enable 2FA and use App Password")
        print("   - Outlook: Use regular password")
        print("   - Check username/password are correct")
        return False

    except smtplib.SMTPConnectError as e:
        print(f"❌ CONNECTION FAILED: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   - Check SMTP_SERVER and SMTP_PORT settings")
        print("   - Ensure internet connection is working")
        print("   - Check firewall allows outbound connections")
        return False

    except smtplib.SMTPRecipientsRefused as e:
        print(f"❌ RECIPIENT REJECTED: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   - Ensure FROM_EMAIL matches SMTP_USERNAME")
        print("   - Check email address format is valid")
        return False

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("\n💡 Please check your .env configuration and try again")
        return False

def show_current_config():
    """Display current SMTP configuration (without showing password)."""
    print("\n📋 Current SMTP Configuration:")
    print("-" * 40)

    settings = [
        ("SMTP_SERVER", os.getenv("SMTP_SERVER", "Not set")),
        ("SMTP_PORT", os.getenv("SMTP_PORT", "Not set")),
        ("SMTP_USERNAME", os.getenv("SMTP_USERNAME", "Not set")),
        ("SMTP_PASSWORD", "***hidden***" if os.getenv("SMTP_PASSWORD") else "Not set"),
        ("FROM_EMAIL", os.getenv("FROM_EMAIL", "Not set")),
        ("FROM_NAME", os.getenv("FROM_NAME", "Not set")),
    ]

    for key, value in settings:
        status = "✅" if value != "Not set" else "❌"
        print(f"{status} {key}: {value}")

if __name__ == "__main__":
    print("Tech News Digest - SMTP Configuration Test")
    print("=" * 50)

    show_current_config()
    print()

    if test_smtp_connection():
        print("\n🚀 Your digest system is ready for email delivery!")
    else:
        print("\n🔧 Please fix the configuration issues above and try again.")
        print("📖 See SMTP_SETUP_GUIDE.md for detailed setup instructions.")