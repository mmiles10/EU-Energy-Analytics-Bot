import os
import requests
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_message(message):
    """Send a message to your phone."""
    if not TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in environment")
        return False
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
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def load_energy_data():
    """Load energy data from CSV files."""
    try:
        # Load the data
        prices = pd.read_csv("day_ahead_prices.csv", index_col=0, parse_dates=True)
        load = pd.read_csv("load_data.csv", index_col=0, parse_dates=True)
        flows = pd.read_csv("crossborder_flows.csv", index_col=0, parse_dates=True)
        
        return prices, load, flows
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None, None, None

def create_energy_report(prices, load, flows):
    """Create a formatted energy report."""
    # Calculate statistics
    avg_price = prices.mean().iloc[0]
    min_price = prices.min().iloc[0]
    max_price = prices.max().iloc[0]
    volatility = prices.std().iloc[0]
    
    avg_load = load.mean().iloc[0]
    peak_load = load.max().iloc[0]
    
    net_flow = flows.mean().iloc[0]
    
    # Determine market status
    if volatility > 20:
        market_status = "🔴 High Volatility"
        risk_level = "High Risk/Reward"
    elif volatility > 10:
        market_status = "🟡 Moderate Volatility"
        risk_level = "Standard Trading"
    else:
        market_status = "🟢 Low Volatility"
        risk_level = "Conservative"
    
    # Create the report
    report = f"""
📊 <b>ENERGY TRADING REPORT</b>
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 <b>Price Analysis:</b>
• Average Price: <b>{avg_price:.2f} EUR/MWh</b>
• Min Price: {min_price:.2f} EUR/MWh
• Max Price: {max_price:.2f} EUR/MWh
• Volatility: {volatility:.2f} EUR/MWh
• Price Range: {max_price - min_price:.2f} EUR/MWh

⚡ <b>Load Analysis:</b>
• Peak Load: <b>{peak_load:.0f} MW</b>
• Average Load: {avg_load:.0f} MW
• Load Factor: {(avg_load/peak_load*100):.1f}%

🌍 <b>Cross-Border Flows:</b>
• Net Flow: <b>{net_flow:.0f} MW</b>
• Status: {'Exporting' if net_flow > 0 else 'Importing'}

📈 <b>Market Status:</b>
• {market_status}
• Risk Level: {risk_level}
• Data Points: {len(prices)} price points

💡 <b>Trading Insights:</b>
• Price Spread: {max_price - min_price:.2f} EUR/MWh
• Volatility: {'High' if volatility > 20 else 'Moderate' if volatility > 10 else 'Low'}
• Market: {'Active' if volatility > 20 else 'Stable'}
    """
    
    return report

def send_trading_alert(alert_type, message):
    """Send a trading alert."""
    alerts = {
        'price_spike': '🚨 PRICE SPIKE ALERT',
        'price_drop': '📉 PRICE DROP ALERT', 
        'high_volatility': '⚠️ HIGH VOLATILITY ALERT',
        'arbitrage': '💰 ARBITRAGE OPPORTUNITY',
        'load_peak': '⚡ PEAK LOAD ALERT'
    }
    
    alert_title = alerts.get(alert_type, '📊 TRADING ALERT')
    full_message = f"{alert_title}\n\n{message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    return send_message(full_message)

def main():
    print("📱 Sending Energy Report to Phone")
    print("=" * 40)
    
    # Load energy data
    print("Loading energy data...")
    prices, load, flows = load_energy_data()
    
    if prices is None:
        print("❌ No energy data found. Run main.py first to generate data.")
        return
    
    # Create and send report
    print("Creating energy report...")
    report = create_energy_report(prices, load, flows)
    
    print("Sending report to your phone...")
    if send_message(report):
        print("📱 Energy report sent to your phone!")
    else:
        print("❌ Failed to send report")
    
    # Send a trading alert example
    print("\nSending trading alert...")
    alert_message = f"""
High price volatility detected!
Price range: {prices.max().iloc[0] - prices.min().iloc[0]:.2f} EUR/MWh
Consider risk management strategies.
    """
    send_trading_alert('high_volatility', alert_message)

if __name__ == "__main__":
    main()
