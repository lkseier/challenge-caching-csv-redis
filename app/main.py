import pandas as pd
import time
import logging
import hashlib
from typing import Dict, Any, Optional
import os
from datetime import datetime
from cache import RedisCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FlightDataAnalyzer:
    def __init__(self, csv_path: str, cache_ttl: int = 60):
        """Initialize analyzer with CSV path and cache TTL"""
        self.csv_path = csv_path
        self.cache_ttl = cache_ttl
        self.cache = RedisCache()
        self.df = None
        
    def load_data(self) -> None:
        """Load CSV data into memory"""
        logger.info(f"Loading data from {self.csv_path}")
        start_time = time.time()
        
        try:
            # Load only essential columns to save memory
            columns_to_load = [
                'FL_DATE', 'OP_CARRIER', 'ORIGIN', 'DEST', 
                'DEP_DELAY', 'ARR_DELAY', 'CANCELLED'
            ]
            
            self.df = pd.read_csv(self.csv_path, usecols=columns_to_load)
            
            # Clean data
            self.df = self.df[self.df['CANCELLED'] == 0]  # Remove cancelled flights
            self.df['DEP_DELAY'] = pd.to_numeric(self.df['DEP_DELAY'], errors='coerce')
            self.df['ARR_DELAY'] = pd.to_numeric(self.df['ARR_DELAY'], errors='coerce')
            self.df = self.df.dropna(subset=['DEP_DELAY', 'ARR_DELAY'])
            
            load_time = time.time() - start_time
            logger.info(f"Data loaded successfully: {len(self.df):,} rows in {load_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def _generate_cache_key(self, query_type: str, **params) -> str:
        """Generate unique cache key for query"""
        key_data = f"{query_type}_{str(sorted(params.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_avg_delay_by_airline(self, delay_type: str = 'ARR_DELAY') -> Dict[str, float]:
        """Calculate average delay per airline with caching"""
        cache_key = self._generate_cache_key('avg_delay_airline', delay_type=delay_type)
        
        # Try to get from cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.info("✅ Returned result from REDIS CACHE")
            return cached_result
        
        # Calculate from CSV
        logger.info("🔄 Computing from CSV (cache miss)")
        start_time = time.time()
        
        if self.df is None:
            self.load_data()
        
        result = self.df.groupby('OP_CARRIER')[delay_type].mean().round(2).to_dict()
        
        computation_time = time.time() - start_time
        logger.info(f"📊 Computed {len(result)} airline delays in {computation_time:.3f}s")
        
        # Cache the result
        self.cache.set(cache_key, result, self.cache_ttl)
        logger.info("💾 Result cached for future requests")
        
        return result
    
    def get_flights_by_airport(self, airport_type: str = 'ORIGIN') -> Dict[str, int]:
        """Calculate flight counts per airport with caching"""
        cache_key = self._generate_cache_key('flights_airport', airport_type=airport_type)
        
        # Try cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.info("✅ Returned result from REDIS CACHE")
            return cached_result
        
        # Calculate from CSV
        logger.info("🔄 Computing from CSV (cache miss)")
        start_time = time.time()
        
        if self.df is None:
            self.load_data()
        
        result = self.df[airport_type].value_counts().to_dict()
        
        computation_time = time.time() - start_time
        logger.info(f"📊 Computed {len(result)} airport counts in {computation_time:.3f}s")
        
        # Cache the result
        self.cache.set(cache_key, result, self.cache_ttl)
        logger.info("💾 Result cached for future requests")
        
        return result
    
    def get_monthly_delays(self, delay_type: str = 'ARR_DELAY') -> Dict[str, float]:
        """Calculate average delay per month with caching"""
        cache_key = self._generate_cache_key('monthly_delays', delay_type=delay_type)
        
        # Try cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.info("✅ Returned result from REDIS CACHE")
            return cached_result
        
        # Calculate from CSV
        logger.info("🔄 Computing from CSV (cache miss)")
        start_time = time.time()
        
        if self.df is None:
            self.load_data()
        
        # Extract month from FL_DATE
        self.df['FL_DATE'] = pd.to_datetime(self.df['FL_DATE'])
        self.df['MONTH'] = self.df['FL_DATE'].dt.strftime('%Y-%m')
        
        result = self.df.groupby('MONTH')[delay_type].mean().round(2).to_dict()
        
        computation_time = time.time() - start_time
        logger.info(f"📊 Computed {len(result)} monthly delays in {computation_time:.3f}s")
        
        # Cache the result
        self.cache.set(cache_key, result, self.cache_ttl)
        logger.info("💾 Result cached for future requests")
        
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> bool:
        """Clear all cached data"""
        return self.cache.clear_all()

def demo_performance():
    """Demonstrate caching performance improvement"""
    
    # Configuration
    CSV_PATH = os.getenv('CSV_PATH', 'flights.csv')
    CACHE_TTL = int(os.getenv('CACHE_TTL', 60))
    
    print("=" * 60)
    print("🚀 AIRLINE DATA CACHING DEMO")
    print("=" * 60)
    
    analyzer = FlightDataAnalyzer(CSV_PATH, CACHE_TTL)
    
    # Test different queries multiple times to show caching effect
    queries = [
        ("Average Arrival Delay by Airline", lambda: analyzer.get_avg_delay_by_airline('ARR_DELAY')),
        ("Flight Counts by Origin Airport", lambda: analyzer.get_flights_by_airport('ORIGIN')),
        ("Monthly Average Delays", lambda: analyzer.get_monthly_delays('ARR_DELAY')),
    ]
    
    for query_name, query_func in queries:
        print(f"\n📋 Testing: {query_name}")
        print("-" * 40)
        
        # First run (should be slow - cache miss)
        print("🔍 First run (cache miss expected):")
        start_time = time.time()
        result = query_func()
        first_run_time = time.time() - start_time
        print(f"⏱️  First run took: {first_run_time:.3f}s")
        print(f"📈 Got {len(result)} results")
        
        # Second run (should be fast - cache hit)
        print("\n🔍 Second run (cache hit expected):")
        start_time = time.time()
        result = query_func()
        second_run_time = time.time() - start_time
        print(f"⏱️  Second run took: {second_run_time:.3f}s")
        
        # Calculate speedup
        if second_run_time > 0:
            speedup = first_run_time / second_run_time
            print(f"🚀 Speedup: {speedup:.1f}x faster!")
        
        time.sleep(1)  # Brief pause between tests
    
    # Show cache statistics
    print(f"\n📊 Cache Statistics:")
    stats = analyzer.get_cache_stats()
    for key, value in stats.items():
        print(f"  • {key}: {value}")
    
    hit_ratio = analyzer.cache.get_cache_hit_ratio()
    print(f"  • Cache Hit Ratio: {hit_ratio:.1f}%")

if __name__ == "__main__":
    demo_performance()