import os
from dotenv import load_dotenv
from entsoe import EntsoePandasClient
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

load_dotenv()

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

def main():
    """Main function to run the energy trading application."""
    print("Energy Trading Application Started")
    print("=" * 50)
    print("Useful Energy Trading Resources:")
    print("- EPEX Spot: https://www.epexspot.com/en")
    print("- EEX: https://www.eex.com")
    print("- ENTSOE Transparency: https://newtransparency.entsoe.eu/")
    print("- ENTSOE Python Docs: https://github.com/EnergieID/entsoe-py")
    print("=" * 50)
    
    # Get country selection from user
    country_code, country_code_from, country_code_to = get_country_selection()
    
    # Initialize the ENTSOE pandas client
    entsoe_api_key = os.getenv("ENTSOE_API_KEY")
    if not entsoe_api_key:
        print("Error: ENTSOE_API_KEY not set in environment")
        return
    client = EntsoePandasClient(api_key=entsoe_api_key)
    
    # Set up date range - using current dates for fresh data
    now = pd.Timestamp.now(tz='Europe/Brussels')
    start = now - pd.Timedelta(days=1)  # Yesterday
    end = now  # Current time
    
    print(f"Querying ENTSOE data for {country_code} from {start} to {end}")
    
    try:
        # Query day-ahead prices (returns pandas Series)
        print("Fetching day-ahead prices...")
        day_ahead_prices = client.query_day_ahead_prices(country_code, start=start, end=end)
        print("✓ Successfully retrieved day-ahead prices data")
        print(f"Data type: {type(day_ahead_prices)}")
        print(f"Data shape: {day_ahead_prices.shape}")
        print(f"Price range: {day_ahead_prices.min():.2f} - {day_ahead_prices.max():.2f} EUR/MWh")
        
        # Save to CSV
        day_ahead_prices.to_csv('day_ahead_prices.csv')
        print("✓ Day-ahead prices saved to day_ahead_prices.csv")
        
        # Query generation data (returns pandas DataFrame)
        print("Fetching generation data...")
        generation = client.query_generation(country_code, start=start, end=end)
        print("✓ Successfully retrieved generation data")
        print(f"Data type: {type(generation)}")
        print(f"Data shape: {generation.shape}")
        
        # Save generation data
        generation.to_csv('generation_data.csv')
        print("✓ Generation data saved to generation_data.csv")
        
        # Query load data (returns pandas DataFrame)
        print("Fetching load data...")
        load = client.query_load(country_code, start=start, end=end)
        print("✓ Successfully retrieved load data")
        print(f"Data type: {type(load)}")
        print(f"Data shape: {load.shape}")
        
        # Save load data
        load.to_csv('load_data.csv')
        print("✓ Load data saved to load_data.csv")
        
        # Query cross-border flows (returns pandas Series)
        print("Fetching cross-border flows...")
        flows = client.query_crossborder_flows(country_code_from, country_code_to, start=start, end=end)
        print("✓ Successfully retrieved cross-border flows data")
        print(f"Data type: {type(flows)}")
        print(f"Data shape: {flows.shape}")
        
        # Save flows data
        flows.to_csv('crossborder_flows.csv')
        print("✓ Cross-border flows saved to crossborder_flows.csv")
        
        print("\n" + "=" * 50)
        print("All data successfully retrieved and saved!")
        print("Files created:")
        print("- day_ahead_prices.csv")
        print("- generation_data.csv") 
        print("- load_data.csv")
        print("- crossborder_flows.csv")
        
        # Generate charts with country information
        generate_charts(country_code, country_code_from, country_code_to)
        
        # Perform data analytics
        from EnergyAnalysis import main_analysis
        main_analysis()
        
    except Exception as e:
        print(f"Error querying ENTSOE data: {e}")
        print("Please check your API key in config.py")
        print("\nTroubleshooting:")
        print("1. Check your API key in config.py")
        print("2. Verify your ENTSOE account is active")
        print("3. Check the ENTSOE documentation: https://github.com/EnergieID/entsoe-py")

def generate_charts(primary_country, from_country, to_country):
    """Generate charts from the CSV data with country information."""
    print("\nGenerating charts...")
    
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
        # Day-ahead prices
        print("Creating day-ahead prices chart...")
        prices = pd.read_csv("day_ahead_prices.csv", index_col=0, parse_dates=True)
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
        print("✓ Day-ahead prices chart saved")

        # Load
        print("Creating load chart...")
        load = pd.read_csv("load_data.csv", index_col=0, parse_dates=True)
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
        print("✓ Load chart saved")

        # Cross-border flows
        print("Creating cross-border flows chart...")
        flows = pd.read_csv("crossborder_flows.csv", index_col=0, parse_dates=True)
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
        print("✓ Cross-border flows chart saved")

        # Generation mix (stacked area)
        print("Creating generation mix chart...")
        gen = pd.read_csv("generation_data.csv", header=[0, 1])
        ts_col = gen.columns[0][0] if isinstance(gen.columns[0], tuple) else gen.columns[0]
        gen[ts_col] = pd.to_datetime(gen[ts_col])
        gen = gen.set_index(ts_col)
        gen_actual = gen[[c for c in gen.columns if "Actual Aggregated" in str(c)]].copy()
        gen_actual.columns = [c[0] for c in gen_actual.columns]
        fig, ax = plt.subplots(figsize=(12, 6))
        gen_actual.plot.area(ax=ax)
        title = f"Generation Mix - {primary_name} ({primary_country})"
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel("MW", fontsize=12)
        ax.set_xlabel("Time", fontsize=12)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("chart_generation_mix.png", dpi=150)
        plt.close()
        print("✓ Generation mix chart saved")

        print("\n✓ Charts saved as:")
        print("  - chart_day_ahead_prices.png")
        print("  - chart_load.png")
        print("  - chart_crossborder_flows.png")
        print("  - chart_generation_mix.png")
        
    except Exception as e:
        print(f"Error generating charts: {e}")
        print("Charts will be skipped, but CSV files are still available.")


if __name__ == "__main__":
    main()








def get_telegram_updates():
    """Get updates from Telegram bot API."""
    import requests
    import json
    
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN not set in environment")
        return None
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            print("\n" + "=" * 50)
            print("TELEGRAM BOT UPDATES")
            print("=" * 50)
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"❌ Error getting Telegram updates: {r.status_code}")
            print(f"Response: {r.text}")
            return None
    except Exception as e:
        print(f"❌ Error connecting to Telegram API: {e}")
        return None

# Uncomment the line below to get Telegram updates
# get_telegram_updates()
