import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database_manager import db_manager
from analysis_engine import AnalysisEngine

class StrategyEngine:
   def __init__(self):
       self.analysis_engine = AnalysisEngine()   

   async def detect_breakout_signal(self, analysis_result, token_address):
       """New breakout detection using pre-analyzed data"""
       if not analysis_result:
           return None
           
       # Extract metadata
       metadata = analysis_result['metadata']
       symbol = metadata['symbol']
       pool_id = metadata['pool_id']
       
       print(f"🔄 [L1-START] Analysing {symbol} using pre-computed data")
           
       # Extract data from analysis result
       current_price = analysis_result['raw_data']['current_price']
       supply_zones = analysis_result['technical_levels']['zones']['supply']
       demand_zones = analysis_result['technical_levels']['zones']['demand']
       fibonacci_data = analysis_result['technical_levels']['fibonacci']
       
       # Check for breakout signals using confluence scoring
       signal = self._check_confluence_signals(
           current_price, supply_zones, demand_zones, fibonacci_data,
           token_address, pool_id, symbol
       )
       
       if signal:
           # Add analysis_result to signal for chart creation
           signal['analysis_result'] = analysis_result
           print(f"🚀✅ [L1-SUCCESS] Signal found for {symbol}!")
           return signal
           
       print(f"🔵 [L1-INFO] No signal found for {symbol}")
       return None

   def _check_confluence_signals(self, current_price, supply_zones, demand_zones,
                                fibonacci_data, token_address, pool_id, symbol):
        """
        Checks for multiple signal types: Proximity, Real-time Breakout, S/R Flip, and Support Test.
        """
        from datetime import datetime

        ZONE_SCORE_MIN = 1.0
        PROXIMITY_THRESHOLD = 0.03  # 3% distance for alerts

        # --- Strategy 1, 2, 3: Analyzing Resistance Levels ---
        for zone in supply_zones:
            if zone['score'] < ZONE_SCORE_MIN:
                continue
            
            zone_price = zone['avg_price']
            final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)

            # Strategy 1: Proximity to Resistance (Price is BELOW the zone)
            if current_price < zone_price:
                proximity = (zone_price - current_price) / current_price
                if proximity < PROXIMITY_THRESHOLD:
                    return self._create_signal_dict('resistance_proximity', locals(), final_score)

            # Strategy 2 & 3: Price is ABOVE the zone
            else:
                proximity_above = (current_price - zone_price) / zone_price

                # Strategy 2: Real-time Breakout (Price just broke and is very close)
                if proximity_above < 0.05: # Less than 5% away from the broken level
                    return self._create_signal_dict('resistance_breakout_realtime', locals(), final_score)

                # Strategy 3: S/R Flip Re-test (Price broke, moved away, and came back)
                elif proximity_above < PROXIMITY_THRESHOLD:
                    return self._create_signal_dict('sr_flip_retest', locals(), final_score)

        # --- Strategy 4: Analyzing Major Support Levels ---
        for zone in demand_zones:
            if zone['score'] < ZONE_SCORE_MIN:
                continue

            zone_price = zone['avg_price']
            proximity = abs(current_price - zone_price) / zone_price

            if proximity < PROXIMITY_THRESHOLD:
                final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)
                return self._create_signal_dict('support_test', locals(), final_score)

        return None

   def _create_signal_dict(self, signal_type, local_vars, final_score):
        """Helper function to create a consistent signal dictionary."""
        from datetime import datetime
        zone = local_vars['zone']
        
        signal = {
            'signal_type': signal_type,
            'token_address': local_vars['token_address'],
            'pool_id': local_vars['pool_id'],
            'symbol': local_vars['symbol'],
            'current_price': local_vars['current_price'],
            'zone_score': zone['score'],
            'final_score': final_score,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add the specific level price for all signal types
        if 'resistance' in signal_type or 'breakout' in signal_type:
            signal['level_broken'] = zone['avg_price']
        elif 'support' in signal_type or 'retest' in signal_type:
            signal['support_level'] = zone['avg_price']
            
        return signal

   def _calculate_confluence_score(self, zone, zone_price, fibonacci_data):
        """Calculate confluence score between a zone and fibonacci levels."""
        zone_base_score = zone['score']
        fibonacci_bonus = 0.0
        
        if fibonacci_data and fibonacci_data.get('levels'):
            key_fib_levels = [0.382, 0.5, 0.618]
            for fib_level in key_fib_levels:
                if fib_level in fibonacci_data['levels']:
                    fib_price = fibonacci_data['levels'][fib_level]
                    if abs(zone_price - fib_price) / zone_price < 0.005: # 0.5% proximity
                        fibonacci_bonus = 2.0
                        break
        
        # Trend bonus can be added here later
        trend_bonus = 0.5
        
        return zone_base_score + fibonacci_bonus + trend_bonus

   async def save_alert(self, signal):
        """Save alert to the database, including the specific level price."""
        level_price = signal.get('level_broken', signal.get('support_level', 0))
        current_price = signal['current_price']
        
        # Convert numpy types to Python native types
        if hasattr(level_price, 'item'):
            level_price = level_price.item()
        if hasattr(current_price, 'item'):
            current_price = current_price.item()
            
        level_price = float(level_price) if level_price is not None else 0.0
        current_price = float(current_price)
        
        params = (
            signal['token_address'], signal['signal_type'], signal['timestamp'],
            current_price, level_price
        )
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f'''INSERT INTO alert_history (token_address, alert_type, timestamp, price_at_alert, level_price)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})'''
        try:
            db_manager.execute(query, params)
            print(f"💾 Alert for {signal['symbol']} at level {level_price:.6f} saved.")
        except Exception as e:
            print(f"Error in save_alert: {e}")


   async def has_recent_alert(self, signal, cooldown_hours=4):
        """Checks for recent alerts for the *same specific level*."""
        from datetime import datetime, timedelta
        
        level_price = signal.get('level_broken', signal.get('support_level'))
        if level_price is None: return False

        # Convert numpy types to Python native types
        if hasattr(level_price, 'item'):
            level_price = level_price.item()
        level_price = float(level_price)

        cooldown_time = (datetime.now() - timedelta(hours=cooldown_hours)).isoformat()
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f"""SELECT timestamp FROM alert_history 
                    WHERE token_address = {placeholder} AND level_price = {placeholder} AND timestamp > {placeholder}
                    LIMIT 1"""
        params = (signal['token_address'], level_price, cooldown_time)

        try:
            if db_manager.fetchone(query, params):
                print(f"🔵 [COOLDOWN] Event-based cooldown for {signal['symbol']} at level {level_price:.6f}.")
                return True
            return False
        except Exception as e:
            print(f"❌ Error in has_recent_alert: {e}")
            return False
