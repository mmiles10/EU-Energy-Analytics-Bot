from entsoe import EntsoePandasClient
import pandas as pd
from config import ENTSOE_API_KEY
from datetime import datetime
import matplotlib.pyplot as plt

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
    
    # Initialize the ENTSOE pandas client
    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    
    # Set up date range and countries - using current dates for fresh data
    now = pd.Timestamp.now(tz='Europe/Brussels')
    start = now - pd.Timedelta(days=1)  # Yesterday
    end = now  # Current time
    country_code = 'AT'  # Austria
    country_code_from = 'CH'  # Switzerland
    country_code_to = 'DE_LU'  # Germany-Luxembourg
    
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
        
        # Generate charts
        generate_charts()
        
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

def generate_charts():
    """Generate charts from the CSV data."""
    print("\nGenerating charts...")
    
    try:
        # Day-ahead prices
        print("Creating day-ahead prices chart...")
        prices = pd.read_csv("day_ahead_prices.csv", index_col=0, parse_dates=True)
        prices.plot(title="Day-Ahead Prices (EUR/MWh)")
        plt.ylabel("EUR/MWh")
        plt.tight_layout()
        plt.savefig("chart_day_ahead_prices.png", dpi=150)
        plt.close()
        print("✓ Day-ahead prices chart saved")

        # Load
        print("Creating load chart...")
        load = pd.read_csv("load_data.csv", index_col=0, parse_dates=True)
        load.plot(title="System Load (MW)")
        plt.ylabel("MW")
        plt.tight_layout()
        plt.savefig("chart_load.png", dpi=150)
        plt.close()
        print("✓ Load chart saved")

        # Cross-border flows
        print("Creating cross-border flows chart...")
        flows = pd.read_csv("crossborder_flows.csv", index_col=0, parse_dates=True)
        flows.plot(title="Cross-Border Flows (MW)")
        plt.ylabel("MW (positive = export from first zone)")
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
        gen_actual.plot.area(title="Generation Mix – Actual Aggregated (MW)")
        plt.ylabel("MW")
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








        # --- Chart generation section ---
    import matplotlib.pyplot as plt

    print("\nGenerating charts...")

    # Day-ahead prices
    prices = pd.read_csv("day_ahead_prices.csv", index_col=0, parse_dates=True)
    prices.plot(title="Day-Ahead Prices (EUR/MWh)")
    plt.ylabel("EUR/MWh")
    plt.tight_layout()
    plt.savefig("chart_day_ahead_prices.png", dpi=150)
    plt.close()

    # Load
    load = pd.read_csv("load_data.csv", index_col=0, parse_dates=True)
    load.plot(title="System Load (MW)")
    plt.ylabel("MW")
    plt.tight_layout()
    plt.savefig("chart_load.png", dpi=150)
    plt.close()

    # Cross-border flows
    flows = pd.read_csv("crossborder_flows.csv", index_col=0, parse_dates=True)
    flows.plot(title="Cross-Border Flows (MW)")
    plt.ylabel("MW (positive = export from first zone)")
    plt.tight_layout()
    plt.savefig("chart_crossborder_flows.png", dpi=150)
    plt.close()

    # Generation mix (stacked area)
    print("Creating generation mix chart...")
    try:
        gen = pd.read_csv("generation_data.csv", header=[0, 1], index_col=0)
        
        # The first column is already the timestamp index, so we can use it directly
        gen.index = pd.to_datetime(gen.index)
        
        # Get only the "Actual Aggregated" columns
        gen_actual = gen[[c for c in gen.columns if "Actual Aggregated" in str(c)]].copy()
        gen_actual.columns = [c[0] for c in gen_actual.columns]
        
        # Create the stacked area chart
        gen_actual.plot.area(title="Generation Mix – Actual Aggregated (MW)")
        plt.ylabel("MW")
        plt.tight_layout()
        plt.savefig("chart_generation_mix.png", dpi=150)
        plt.close()
        print("✓ Generation mix chart saved")
        
    except Exception as e:
        print(f"⚠️ Could not create generation mix chart: {e}")
        print("Other charts will still be created")

    print("✓ Charts saved as:")
    print("  - chart_day_ahead_prices.png")
    print("  - chart_load.png")
    print("  - chart_crossborder_flows.png")
    print("  - chart_generation_mix.png")

def get_telegram_updates():
    """Get updates from Telegram bot API."""
    import requests
    import json
    
    TOKEN = "8482245238:AAE3xoevSzXoKpydteYBMcRkeYXZbge3ypM"  # Your bot token
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
