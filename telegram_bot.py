import os
import requests
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = None
        
    def get_updates(self):
        """Get updates from Telegram bot."""
        url = f"{self.base_url}/getUpdates"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting updates: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def send_message(self, chat_id, message):
        """Send a message to a specific chat."""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print(f"✅ Message sent successfully to {chat_id}")
                return True
            else:
                print(f"❌ Failed to send message: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return False
    
    def get_chat_id_from_updates(self):
        """Get chat ID from recent updates."""
        updates = self.get_updates()
        if updates and updates.get('ok') and updates.get('result'):
            for update in updates['result']:
                if 'message' in update:
                    chat_id = update['message']['chat']['id']
                    username = update['message']['from'].get('username', 'Unknown')
                    print(f"Found chat ID: {chat_id} (User: @{username})")
                    return chat_id
        return None
    
    def send_energy_report(self, chat_id, price_stats, load_stats, flow_stats):
        """Send energy trading report to Telegram."""
        message = f"""
📊 <b>ENERGY TRADING REPORT</b>
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 <b>Price Analysis:</b>
• Average Price: {price_stats['avg_price']:.2f} EUR/MWh
• Min Price: {price_stats['min_price']:.2f} EUR/MWh
• Max Price: {price_stats['max_price']:.2f} EUR/MWh
• Volatility: {price_stats['volatility']:.2f} EUR/MWh

⚡ <b>Load Analysis:</b>
• Peak Load: {load_stats['peak_load']:.0f} MW
• Average Load: {load_stats['avg_load']:.0f} MW
• Load Factor: {load_stats['load_factor']:.1f}%

🌍 <b>Cross-Border Flows:</b>
• Net Flow: {flow_stats['net_flow']:.0f} MW
• Max Export: {flow_stats['max_export']:.0f} MW

📈 <b>Trading Insights:</b>
• Market Status: {'High Volatility' if price_stats['volatility'] > 20 else 'Normal'}
• Price Range: {price_stats['price_range']:.2f} EUR/MWh
• Risk Level: {'High' if price_stats['volatility'] > 20 else 'Moderate' if price_stats['volatility'] > 10 else 'Low'}
        """
        return self.send_message(chat_id, message)
    
    def send_alert(self, chat_id, alert_type, message):
        """Send trading alert to Telegram."""
        alert_emoji = {
            'price_spike': '🚨',
            'price_drop': '📉',
            'high_volatility': '⚠️',
            'arbitrage': '💰',
            'load_peak': '⚡'
        }
        
        emoji = alert_emoji.get(alert_type, '📊')
        alert_message = f"{emoji} <b>TRADING ALERT</b>\n\n{message}"
        return self.send_message(chat_id, alert_message)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN not set in environment")
        return
    
    # Create bot instance
    bot = TelegramBot(token)
    
    print("🤖 Telegram Bot Setup")
    print("=" * 40)
    
    # Get chat ID from recent messages
    print("Looking for recent messages...")
    chat_id = bot.get_chat_id_from_updates()
    
    if chat_id:
        print(f"✅ Found chat ID: {chat_id}")
        
        # Test message
        test_message = "🤖 Energy Trading Bot is online!\n\nSend /start to begin receiving energy reports."
        bot.send_message(chat_id, test_message)
        
        # Example energy report
        sample_stats = {
            'avg_price': 48.53,
            'min_price': -38.91,
            'max_price': 100.99,
            'volatility': 43.31,
            'price_range': 139.90
        }
        
        sample_load = {
            'peak_load': 6247,
            'avg_load': 5217,
            'load_factor': 83.5
        }
        
        sample_flows = {
            'net_flow': 608,
            'max_export': 1171,
            'max_import': 67
        }
        
        # Send sample report
        bot.send_energy_report(chat_id, sample_stats, sample_load, sample_flows)
        
        # Send trading alert
        bot.send_alert(chat_id, 'high_volatility', 
                      'High price volatility detected!\nPrice range: 139.90 EUR/MWh\nConsider risk management strategies.')
        
    else:
        print("❌ No chat ID found. Please:")
        print("1. Start a conversation with your bot on Telegram")
        print("2. Send any message to the bot")
        print("3. Run this script again")
        
        # Show how to find the bot
        print(f"\n🔍 To find your bot:")
        print(f"1. Open Telegram")
        print(f"2. Search for your bot using the token")
        print(f"3. Or use this link: https://t.me/your_bot_username")

if __name__ == "__main__":
    main()
