import os
import time
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

load_dotenv()

# Telegram configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ENTSOE configuration
API_KEY = os.getenv("ENTSOE_API_KEY")
# Use country code (e.g., 'AT' for Austria) instead of zonal domain for better compatibility
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "AT")  # Austria - change to 'BE', 'FR', 'DE', 'NL', etc.
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SEC", "300"))
STATE_PATH = Path("last_price_state.json")

# Lazy-init: avoid crash at import when ENTSOE_API_KEY is missing (e.g. no .env yet).
client = None

def get_country_selection():
    """Interactive prompt for country selection."""
    print("\n" + "="*50)
    print("COUNTRY SELECTION")
    print("="*50)
    
    # ENTSOE-accepted country codes
    countries = {
        # Standard ISO codes
        'AT': 'Austria',
        'BE': 'Belgium',
        'CH': 'Switzerland',
        'DE': 'Germany',
        'FR': 'France',
        'NL': 'Netherlands',
        'IT': 'Italy',
        'ES': 'Spain',
        'PT': 'Portugal',
        'PL': 'Poland',
        'CZ': 'Czech Republic',
        'DK': 'Denmark',
        'SE': 'Sweden',
        'NO': 'Norway',
        'FI': 'Finland',
        'IE': 'Ireland',
        'GB': 'Great Britain',
        'GR': 'Greece',
        # Special combined codes
        'DE_LU': 'Germany-Luxembourg',
        'IT_SACODC': 'Italy (SACODC)',
        'IT_SACOAC': 'Italy (SACOAC)',
        'IT_BRNN': 'Italy (BRNN)',
        'IT_CNOR': 'Italy (CNOR)',
        'IT_CSUD': 'Italy (CSUD)',
        'IT_FOGN': 'Italy (FOGN)',
        'IT_GR': 'Italy (GR)',
        'IT_MACRO': 'Italy (MACRO)',
        'IT_MALTA': 'Italy (MALTA)',
        'IT_NORD': 'Italy (NORD)',
        'IT_PRGP': 'Italy (PRGP)',
        'IT_ROSN': 'Italy (ROSN)',
        'IT_SARD': 'Italy (SARD)',
        'IT_SICI': 'Italy (SICI)',
        'IT_SUD': 'Italy (SUD)',
    }
    
    # Primary market country
    print("\n1. PRIMARY MARKET (for prices, load, generation):")
    print("Enter country code (e.g., AT, DE, FR, DE_LU):")
    print("Common codes: AT=Austria, DE=Germany, FR=France, CH=Switzerland")
    
    primary = input("Country code (default: AT): ").strip().upper() or "AT"
    
    # Validate and show name if recognized
    if primary in countries:
        print(f"✓ Selected: {countries[primary]}")
    else:
        print(f"⚠️  '{primary}' not in common list, but will try anyway")
        print("   (Make sure it's a valid ENTSOE country code)")
    
    # Cross-border flow countries
    print("\n2. CROSS-BORDER FLOWS:")
    print("Enter source country (energy flows FROM):")
    print("Common codes: CH=Switzerland, DE=Germany, FR=France, AT=Austria")
    
    from_country = input("From country code (default: CH): ").strip().upper() or "CH"
    if from_country in countries:
        print(f"✓ Selected: {countries[from_country]}")
    else:
        print(f"⚠️  '{from_country}' not in common list, but will try anyway")
    
    print("\nEnter destination country (energy flows TO):")
    print("Common codes: DE_LU=Germany-Luxembourg, DE=Germany, FR=France")
    
    to_country = input("To country code (default: DE_LU): ").strip().upper() or "DE_LU"
    if to_country in countries:
        print(f"✓ Selected: {countries[to_country]}")
    else:
        print(f"⚠️  '{to_country}' not in common list, but will try anyway")
    
    print("\n" + "="*50)
    print(f"Configuration:")
    print(f"  Primary Market: {countries.get(primary, primary)} ({primary})")
    print(f"  Cross-Border Flow: {countries.get(from_country, from_country)} → {countries.get(to_country, to_country)}")
    print("="*50 + "\n")
    
    return primary, from_country, to_country

def send_telegram(text: str, parse_mode="HTML"):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in environment")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()

def send_photo(photo_path: str, caption: str = ""):
    """Send a photo to Telegram."""
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in environment")
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as photo:
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
        r = requests.post(url, files=files, data=data, timeout=30)
        r.raise_for_status()

def fetch_energy_data(primary_country, from_country, to_country):
    """Fetch all energy data from ENTSOE API."""
    global client
    if not API_KEY:
        print("Error: ENTSOE_API_KEY not set. Please set it in your .env file or environment.")
        return None, None, None
    if client is None:
        client = EntsoePandasClient(api_key=API_KEY)

    now = pd.Timestamp.now(tz='Europe/Brussels')
    start = (now - pd.Timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now
    
    try:
        # Fetch prices
        prices = client.query_day_ahead_prices(primary_country, start=start, end=end).dropna()
        
        # Fetch load data
        load = client.query_load(primary_country, start=start, end=end)
        
        # Fetch cross-border flows (from_country -> to_country; positive = export from from_country)
        flows = client.query_crossborder_flows(from_country, to_country, start=start, end=end).dropna()
        # ENTSO-E publishes some borders only in one direction (e.g. CH–DE_LU). If we get empty or all zeros, try reverse and negate.
        try:
            all_zero = flows is None or flows.empty or (not flows.empty and flows.abs().max() == 0)
        except Exception:
            all_zero = True
        if all_zero:
            try:
                flows_reverse = client.query_crossborder_flows(to_country, from_country, start=start, end=end).dropna()
                if flows_reverse is not None and not flows_reverse.empty and flows_reverse.abs().max() != 0:
                    flows = -flows_reverse.astype(float)  # positive = export from from_country
                    print("✓ Cross-border flow: using reverse direction (API publishes to→from)")
            except Exception:
                pass
        if flows is not None and not flows.empty:
            flows = flows.astype(float)
        
        return prices, load, flows
    except Exception as e:
        print(f"Error fetching energy data: {e}")
        return None, None, None

def create_comprehensive_report(prices, load, flows, primary_country, from_country, to_country):
    """Create a comprehensive energy trading report."""
    if prices is None or prices.empty:
        return None
    
    # Country name mapping
    country_names = {
        'AT': 'Austria', 'BE': 'Belgium', 'CH': 'Switzerland',
        'DE': 'Germany', 'DE_LU': 'Germany-Luxembourg', 'FR': 'France',
        'NL': 'Netherlands', 'IT': 'Italy', 'ES': 'Spain',
        'PT': 'Portugal', 'PL': 'Poland', 'CZ': 'Czech Republic',
        'DK': 'Denmark', 'SE': 'Sweden', 'NO': 'Norway',
        'FI': 'Finland', 'IE': 'Ireland', 'GB': 'Great Britain',
        'GR': 'Greece'
    }
    
    primary_name = country_names.get(primary_country, primary_country)
    from_name = country_names.get(from_country, from_country)
    to_name = country_names.get(to_country, to_country)
    
    # Calculate price statistics
    avg_price = float(prices.mean().iloc[0]) if hasattr(prices.mean(), 'iloc') else float(prices.mean())
    min_price = float(prices.min().iloc[0]) if hasattr(prices.min(), 'iloc') else float(prices.min())
    max_price = float(prices.max().iloc[0]) if hasattr(prices.max(), 'iloc') else float(prices.max())
    volatility = float(prices.std().iloc[0]) if hasattr(prices.std(), 'iloc') else float(prices.std())
    price_range = max_price - min_price
    
    # Calculate load statistics
    if load is not None and not load.empty:
        avg_load = float(load.mean().iloc[0]) if hasattr(load.mean(), 'iloc') else float(load.mean())
        peak_load = float(load.max().iloc[0]) if hasattr(load.max(), 'iloc') else float(load.max())
        load_factor = (avg_load / peak_load * 100) if peak_load > 0 else 0
    else:
        avg_load = peak_load = load_factor = 0
    
    # Calculate flow statistics
    if flows is not None and not flows.empty:
        net_flow = float(flows.mean().iloc[0]) if hasattr(flows.mean(), 'iloc') else float(flows.mean())
        max_export = float(flows.max().iloc[0]) if hasattr(flows.max(), 'iloc') else float(flows.max())
    else:
        net_flow = max_export = 0
    
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
    
    # Create the comprehensive report with clear country references
    report = f"""📊 <b>ENERGY TRADING REPORT</b>
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}

📍 <b>Market Coverage:</b>
• Primary Market: <b>{primary_name} ({primary_country})</b>
• Cross-Border Flow: {from_name} → {to_name}

💰 <b>Price Analysis ({primary_name}):</b>
• Average Price: <b>{avg_price:.2f} EUR/MWh</b>
• Min Price: {min_price:.2f} EUR/MWh
• Max Price: {max_price:.2f} EUR/MWh
• Volatility: {volatility:.2f} EUR/MWh
• Price Range: {price_range:.2f} EUR/MWh

⚡ <b>Load Analysis ({primary_name}):</b>
• Peak Load: <b>{peak_load:.0f} MW</b>
• Average Load: {avg_load:.0f} MW
• Load Factor: {load_factor:.1f}%

🌍 <b>Cross-Border Flows ({from_name} → {to_name}):</b>
• Net Flow: <b>{net_flow:.0f} MW</b>
• Status: {'Exporting from ' + from_name if net_flow > 0 else 'Importing to ' + from_name}

📈 <b>Market Status ({primary_name}):</b>
• {market_status}
• Risk Level: {risk_level}
• Data Points: {len(prices)} price points

💡 <b>Trading Insights:</b>
• Price Spread: {price_range:.2f} EUR/MWh
• Volatility: {'High' if volatility > 20 else 'Moderate' if volatility > 10 else 'Low'}
• Market: {'Active' if volatility > 20 else 'Stable'}"""
    
    return report

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state))

def generate_charts(prices, load, flows, primary_country, from_country, to_country):
    """Generate charts from the data and save them."""
    # Country name mapping
    country_names = {
        'AT': 'Austria', 'BE': 'Belgium', 'CH': 'Switzerland',
        'DE': 'Germany', 'DE_LU': 'Germany-Luxembourg', 'FR': 'France',
        'NL': 'Netherlands', 'IT': 'Italy', 'ES': 'Spain',
        'PT': 'Portugal', 'PL': 'Poland', 'CZ': 'Czech Republic',
        'DK': 'Denmark', 'SE': 'Sweden', 'NO': 'Norway',
        'FI': 'Finland', 'IE': 'Ireland', 'GB': 'Great Britain',
        'GR': 'Greece'
    }
    
    primary_name = country_names.get(primary_country, primary_country)
    from_name = country_names.get(from_country, from_country)
    to_name = country_names.get(to_country, to_country)
    
    try:
        # Day-ahead prices chart
        if prices is not None and not prices.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            prices.plot(ax=ax)
            title = f"Day-Ahead Prices - {primary_name} ({primary_country})"
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_ylabel("EUR/MWh", fontsize=12)
            ax.set_xlabel("Time", fontsize=12)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig("chart_day_ahead_prices.png", dpi=150)
            plt.close()
            print("✓ Generated price chart")
        
        # Load chart
        if load is not None and not load.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            load.plot(ax=ax)
            title = f"System Load - {primary_name} ({primary_country})"
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_ylabel("MW", fontsize=12)
            ax.set_xlabel("Time", fontsize=12)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig("chart_load.png", dpi=150)
            plt.close()
            print("✓ Generated load chart")
        
        # Cross-border flows chart
        if flows is not None and not flows.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            flows.plot(ax=ax)
            title = f"Cross-Border Flows - {from_name} ({from_country}) → {to_name} ({to_country})"
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_ylabel(f"MW (positive = export from {from_name})", fontsize=12)
            ax.set_xlabel("Time", fontsize=12)
            ax.axhline(y=0, color='r', linestyle='--', alpha=0.5, label='Zero flow')
            ax.grid(True, alpha=0.3)
            ax.legend()
            plt.tight_layout()
            plt.savefig("chart_crossborder_flows.png", dpi=150)
            plt.close()
            print("✓ Generated flows chart")
        
        return True
    except Exception as e:
        print(f"Error generating charts: {e}")
        return False

def main(primary_country, from_country, to_country):
    if not API_KEY:
        print("Error: ENTSOE_API_KEY not set. Please set it in your .env file or environment.")
        return
    if not CHAT_ID or not TOKEN:
        print("Error: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in your .env or environment.")
        print("You can get your chat ID by running: python send_telegram.py")
        return
    
    print(f"Fetching energy data for {primary_country}... (Chat ID: {CHAT_ID})")
    
    # Fetch all energy data with selected countries
    prices, load, flows = fetch_energy_data(primary_country, from_country, to_country)
    
    if prices is None or prices.empty:
        print("No price data available yet.")
        return
    
    # Get latest price for state tracking
    latest_price = float(prices.iloc[-1]) if hasattr(prices, 'iloc') else float(prices.values[-1])
    latest_ts = prices.index[-1].isoformat() if hasattr(prices.index[-1], 'isoformat') else str(prices.index[-1])
    
    # Load previous state
    state = load_state()
    last_price = state.get("price")
    last_ts = state.get("ts")
    
    # Always create and print the report to terminal
    report = create_comprehensive_report(prices, load, flows, primary_country, from_country, to_country)
    if report:
        # Print full report to terminal
        print(f"\n{'='*50}")
        print("COMPREHENSIVE ENERGY REPORT:")
        print('='*50)
        # Convert HTML tags to plain text for terminal display
        terminal_report = report.replace('<b>', '').replace('</b>', '').replace('&lt;', '<').replace('&gt;', '>')
        print(terminal_report)
        print(f"{'='*50}\n")
        
        # Check if we should send update to Telegram (new data or first run)
        should_send = False
        if last_price is None:
            should_send = True
            print("First run - sending initial report to Telegram")
        elif last_ts != latest_ts:
            should_send = True
            print(f"New data available - sending update to Telegram")
        else:
            print(f"No new data - not sending to Telegram (Latest price: {latest_price:.2f} €/MWh)")
        
        if should_send:
            # Generate charts
            print("Generating charts...")
            generate_charts(prices, load, flows, primary_country, from_country, to_country)
            
            # Send text report first
            send_telegram(report, parse_mode="HTML")
            print("✅ Sent text report to Telegram")
            
            # Send charts
            chart_files = [
                ("chart_day_ahead_prices.png", f"📊 Price Chart - {primary_country}"),
                ("chart_load.png", f"⚡ Load Chart - {primary_country}"),
                ("chart_crossborder_flows.png", f"🌍 Cross-Border Flows - {from_country} → {to_country}"),
            ]
            
            for chart_file, caption in chart_files:
                chart_path = Path(chart_file)
                if chart_path.exists():
                    try:
                        send_photo(str(chart_path), caption)
                        print(f"✅ Sent {chart_file} to Telegram")
                    except Exception as e:
                        print(f"⚠️  Failed to send {chart_file}: {e}")
                else:
                    print(f"⚠️  Chart not found: {chart_path}")
            
            save_state({"price": latest_price, "ts": latest_ts})
            print(f"✅ All messages sent to Telegram (Latest price: {latest_price:.2f} €/MWh)")
    else:
        print("Failed to create report")

if __name__ == "__main__":
    import sys

    # Run once with defaults (no prompts): python TelegramUpdaterBot.py --once
    # Uses env PRIMARY_COUNTRY, FROM_COUNTRY, TO_COUNTRY or defaults AT, CH, DE_LU
    if "--once" in sys.argv:
        primary_country = os.getenv("PRIMARY_COUNTRY", "AT").strip().upper()
        from_country = os.getenv("FROM_COUNTRY", "CH").strip().upper()
        to_country = os.getenv("TO_COUNTRY", "DE_LU").strip().upper()
        print("Starting Telegram Updater Bot (single run)...")
        print(f"Primary Market: {primary_country} | Cross-Border: {from_country} → {to_country}\n")
        main(primary_country, from_country, to_country)
        sys.exit(0)

    # Get country selection from user
    primary_country, from_country, to_country = get_country_selection()
    
    print("Starting Telegram Updater Bot...")
    print(f"Primary Market: {primary_country}")
    print(f"Cross-Border Flow: {from_country} → {to_country}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print("Press Ctrl+C to stop\n")
    
    # Run forever; use Ctrl+C to stop. Or call once from cron by running main() just once.
    while True:
        try:
            main(primary_country, from_country, to_country)
        except KeyboardInterrupt:
            print("\nStopping bot...")
            break
        except Exception as e:
            print(f"Error: {e}")
            # Optional: send_telegram(f"Bot error: {e}")
        time.sleep(CHECK_INTERVAL)
