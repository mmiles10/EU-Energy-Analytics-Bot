import requests
import json
from datetime import datetime

# Your bot token and chat ID
TOKEN = "8482245238:AAE3xoevSzXoKpydteYBMcRkeYXZbge3ypM"
CHAT_ID = "8466265605"

def send_message(message):
    """Send a message to your phone."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🤖 Testing Telegram Bot")
    print("=" * 40)
    print(f"Chat ID: {CHAT_ID}")
    
    # Test message
    test_message = """
🤖 <b>Energy Trading Bot Test</b>

✅ <b>Connection Successful!</b>
Your bot is now connected to your phone.

📊 <b>Sample Energy Data:</b>
• Current Price: 48.53 EUR/MWh
• Load: 5217 MW
• Volatility: High
• Time: """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """

⚡ <b>Next Steps:</b>
• Run your energy analysis
• Get real-time trading alerts
• Receive market updates

Send /help for more commands.
    """
    
    print("Sending test message...")
    if send_message(test_message):
        print("📱 Check your phone - you should have received a message!")
    else:
        print("❌ Failed to send message. Check your bot token and chat ID.")

if __name__ == "__main__":
    main()
