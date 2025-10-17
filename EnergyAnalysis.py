# Energy Data Analysis Module
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def load_energy_data():
    """Load all energy data from CSV files."""
    try:
        # Load CSV files
        day_ahead_prices = pd.read_csv("day_ahead_prices.csv", index_col=0, parse_dates=True)
        load_data = pd.read_csv("load_data.csv", index_col=0, parse_dates=True)
        generation_data = pd.read_csv("generation_data.csv", header=[0, 1])
        crossborder_flows = pd.read_csv("crossborder_flows.csv", index_col=0, parse_dates=True)
        
        print("✅ Energy data loaded successfully!")
        return day_ahead_prices, load_data, generation_data, crossborder_flows
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None, None, None, None

def analyze_prices(prices):
    """Analyze day-ahead prices data."""
    print("\n📊 DAY-AHEAD PRICES ANALYSIS")
    print("-" * 40)
    
    print(f"📈 Price Statistics:")
    print(f"   Average Price: {prices.mean().iloc[0]:.2f} EUR/MWh")
    print(f"   Min Price: {prices.min().iloc[0]:.2f} EUR/MWh")
    print(f"   Max Price: {prices.max().iloc[0]:.2f} EUR/MWh")
    print(f"   Price Volatility (std): {prices.std().iloc[0]:.2f} EUR/MWh")
    print(f"   Price Range: {prices.max().iloc[0] - prices.min().iloc[0]:.2f} EUR/MWh")
    
    # Find peak and off-peak hours
    max_price_idx = prices.idxmax().iloc[0]
    min_price_idx = prices.idxmin().iloc[0]
    print(f"   Peak Price Time: {max_price_idx.strftime('%Y-%m-%d %H:%M')} ({prices.max().iloc[0]:.2f} EUR/MWh)")
    print(f"   Off-Peak Time: {min_price_idx.strftime('%Y-%m-%d %H:%M')} ({prices.min().iloc[0]:.2f} EUR/MWh)")
    
    return {
        'avg_price': prices.mean().iloc[0],
        'min_price': prices.min().iloc[0],
        'max_price': prices.max().iloc[0],
        'volatility': prices.std().iloc[0],
        'price_range': prices.max().iloc[0] - prices.min().iloc[0]
    }

def analyze_load(load):
    """Analyze system load data."""
    print("\n📊 SYSTEM LOAD ANALYSIS")
    print("-" * 40)
    
    print(f"⚡ Load Statistics:")
    print(f"   Average Load: {load.mean().iloc[0]:.2f} MW")
    print(f"   Peak Load: {load.max().iloc[0]:.2f} MW")
    print(f"   Min Load: {load.min().iloc[0]:.2f} MW")
    print(f"   Load Factor: {(load.mean().iloc[0] / load.max().iloc[0] * 100):.1f}%")
    
    # Find peak and minimum load times
    max_load_idx = load.idxmax().iloc[0]
    min_load_idx = load.idxmin().iloc[0]
    print(f"   Peak Load Time: {max_load_idx.strftime('%Y-%m-%d %H:%M')} ({load.max().iloc[0]:.2f} MW)")
    print(f"   Min Load Time: {min_load_idx.strftime('%Y-%m-%d %H:%M')} ({load.min().iloc[0]:.2f} MW)")
    
    return {
        'avg_load': load.mean().iloc[0],
        'peak_load': load.max().iloc[0],
        'min_load': load.min().iloc[0],
        'load_factor': (load.mean().iloc[0] / load.max().iloc[0] * 100)
    }

def analyze_flows(flows):
    """Analyze cross-border flows data."""
    print("\n📊 CROSS-BORDER FLOWS ANALYSIS")
    print("-" * 40)
    
    print(f"🌍 Flow Statistics:")
    print(f"   Average Flow: {flows.mean().iloc[0]:.2f} MW")
    print(f"   Max Export: {flows.max().iloc[0]:.2f} MW")
    print(f"   Max Import: {flows.min().iloc[0]:.2f} MW")
    
    # Determine net flow direction
    net_flow = flows.mean().iloc[0]
    if net_flow > 0:
        print(f"   Net Flow: {net_flow:.2f} MW (Exporting to Germany-Luxembourg)")
    else:
        print(f"   Net Flow: {net_flow:.2f} MW (Importing from Germany-Luxembourg)")
    
    return {
        'avg_flow': flows.mean().iloc[0],
        'max_export': flows.max().iloc[0],
        'max_import': flows.min().iloc[0],
        'net_flow': net_flow
    }

def analyze_generation(gen):
    """Analyze generation data."""
    print("\n📊 GENERATION ANALYSIS")
    print("-" * 40)
    
    # Get actual generation data
    gen_actual = gen[[c for c in gen.columns if "Actual Aggregated" in str(c)]].copy()
    if not gen_actual.empty:
        gen_actual.columns = [c[0] for c in gen_actual.columns]
        
        print(f"🔋 Generation Mix:")
        total_generation = gen_actual.sum().sum()
        generation_mix = {}
        
        for fuel_type in gen_actual.columns:
            fuel_total = gen_actual[fuel_type].sum()
            percentage = (fuel_total / total_generation) * 100
            generation_mix[fuel_type] = {'total': fuel_total, 'percentage': percentage}
            print(f"   {fuel_type}: {fuel_total:.2f} MWh ({percentage:.1f}%)")
        
        print(f"   Total Generation: {total_generation:.2f} MWh")
        
        return {
            'total_generation': total_generation,
            'generation_mix': generation_mix
        }
    else:
        print("   No generation data available")
        return None

def correlation_analysis(prices, load):
    """Perform correlation analysis between prices and load."""
    print("\n📊 CORRELATION ANALYSIS")
    print("-" * 40)
    
    # Align data by time index
    prices_clean = prices.dropna()
    load_clean = load.dropna()
    
    if not prices_clean.empty and not load_clean.empty:
        # Find common time index
        common_times = prices_clean.index.intersection(load_clean.index)
        if len(common_times) > 1:
            prices_aligned = prices_clean.loc[common_times]
            load_aligned = load_clean.loc[common_times]
            
            correlation = prices_aligned.corrwith(load_aligned).iloc[0]
            print(f"   Price-Load Correlation: {correlation:.3f}")
            
            if correlation > 0.5:
                print("   📈 Strong positive correlation: Higher load = Higher prices")
            elif correlation < -0.5:
                print("   📉 Strong negative correlation: Higher load = Lower prices")
            else:
                print("   📊 Weak correlation: Load and prices are not strongly related")
            
            return correlation
    else:
        print("   Insufficient data for correlation analysis")
        return None

def trading_insights(price_stats):
    """Generate trading insights based on price analysis."""
    print("\n📊 TRADING INSIGHTS")
    print("-" * 40)
    
    # Price volatility analysis
    price_volatility = price_stats['volatility']
    if price_volatility > 20:
        print("   ⚠️  High price volatility detected - High risk/reward potential")
        risk_level = "High"
    elif price_volatility > 10:
        print("   📊 Moderate price volatility - Standard trading conditions")
        risk_level = "Moderate"
    else:
        print("   📈 Low price volatility - Stable market conditions")
        risk_level = "Low"
    
    # Peak/off-peak spread
    price_spread = price_stats['price_range']
    if price_spread > 50:
        print("   💰 Large price spread - Good arbitrage opportunities")
        arbitrage_potential = "High"
    elif price_spread > 20:
        print("   📊 Moderate price spread - Some trading opportunities")
        arbitrage_potential = "Moderate"
    else:
        print("   📈 Small price spread - Limited arbitrage potential")
        arbitrage_potential = "Low"
    
    return {
        'risk_level': risk_level,
        'arbitrage_potential': arbitrage_potential,
        'volatility': price_volatility,
        'price_spread': price_spread
    }

def generate_summary_report(price_stats, load_stats, flow_stats, trading_insights, prices):
    """Generate a comprehensive summary report."""
    print("\n📊 SUMMARY REPORT")
    print("-" * 40)
    print(f"   Analysis Period: {prices.index[0].strftime('%Y-%m-%d %H:%M')} to {prices.index[-1].strftime('%Y-%m-%d %H:%M')}")
    print(f"   Data Points: {len(prices)} price points")
    print(f"   Market Status: {trading_insights['risk_level']} Volatility")
    print(f"   Trading Recommendation: {trading_insights['arbitrage_potential']} Risk/Reward")
    print(f"   Average Price: {price_stats['avg_price']:.2f} EUR/MWh")
    print(f"   Price Volatility: {price_stats['volatility']:.2f} EUR/MWh")
    print(f"   Peak Load: {load_stats['peak_load']:.2f} MW")
    print(f"   Net Flow: {flow_stats['net_flow']:.2f} MW")

def main_analysis():
    """Main analysis function that orchestrates all analytics."""
    print("=" * 60)
    print("ENERGY DATA ANALYTICS")
    print("=" * 60)
    
    # Load data
    prices, load, gen, flows = load_energy_data()
    
    if prices is None:
        print("❌ Cannot proceed with analysis - data loading failed")
        return
    
    try:
        # Perform all analyses
        price_stats = analyze_prices(prices)
        load_stats = analyze_load(load)
        flow_stats = analyze_flows(flows)
        gen_stats = analyze_generation(gen)
        correlation = correlation_analysis(prices, load)
        trading_insights_data = trading_insights(price_stats)
        
        # Generate summary
        generate_summary_report(price_stats, load_stats, flow_stats, trading_insights_data, prices)
        
        print("\n✅ Data analytics completed successfully!")
        
        return {
            'price_stats': price_stats,
            'load_stats': load_stats,
            'flow_stats': flow_stats,
            'gen_stats': gen_stats,
            'correlation': correlation,
            'trading_insights': trading_insights_data
        }
        
    except Exception as e:
        print(f"❌ Error in data analytics: {e}")
        return None

if __name__ == "__main__":
    # Run analysis when script is executed directly
    main_analysis()


