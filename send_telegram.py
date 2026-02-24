import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

def get_chat_id():
    """Get your chat ID from recent messages."""
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not set in environment")
        return None
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('ok') and data.get('result'):
            print("📱 Recent messages found:")
            for update in data['result']:
                if 'message' in update:
                    chat_id = update['message']['chat']['id']
                    username = update['message']['from'].get('username', 'Unknown')
                    first_name = update['message']['from'].get('first_name', 'Unknown')
                    message_text = update['message'].get('text', 'No text')
                    
                    print(f"  Chat ID: {chat_id}")
                    print(f"  User: {first_name} (@{username})")
                    print(f"  Message: {message_text}")
                    print(f"  Time: {datetime.fromtimestamp(update['message']['date'])}")
                    print("-" * 40)
            
            return data['result'][-1]['message']['chat']['id'] if data['result'] else None
        else:
            print("❌ No messages found")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def send_message(chat_id, message):
    """Send a message to your phone."""
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not set in environment")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    data = {
        'chat_id': chat_id,
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
    print("🤖 Telegram Message Sender")
    print("=" * 40)
    
    # Get your chat ID
    chat_id = get_chat_id()
    
    if chat_id:
        print(f"\n✅ Found your chat ID: {chat_id}")
        
        # Send a test message
        test_message = """
🤖 <b>Energy Trading Bot</b>

📊 <b>Test Message</b>
This is a test message from your energy trading bot!

⚡ <b>Quick Stats:</b>
• Price: 48.53 EUR/MWh
• Load: 5217 MW
• Volatility: High

Send /start to receive regular energy reports.
        """
        
        if send_message(chat_id, test_message):
            print("📱 Check your phone - you should have received a message!")
        else:
            print("❌ Failed to send message")
    else:
        print("\n❌ No chat ID found. Please:")
        print("1. Open Telegram on your phone")
        print("2. Search for your bot")
        print("3. Send any message to the bot")
        print("4. Run this script again")

if __name__ == "__main__":
    from datetime import datetime
    main()
