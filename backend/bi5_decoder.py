"""
Dukascopy .bi5 File Decoder
Decodes binary tick data from Dukascopy format
"""

import struct
import lzma
from typing import List, Dict
from datetime import datetime, timezone


class BI5Decoder:
    """Decoder for Dukascopy .bi5 binary tick files"""
    
    @staticmethod
    def decode_bi5(compressed_data: bytes) -> List[Dict]:
        """
        Decode .bi5 file to tick data
        
        Format: Each tick is 20 bytes:
        - timestamp (4 bytes, big-endian int) - milliseconds from hour start
        - ask price (4 bytes, big-endian int) - price * 100000
        - bid price (4 bytes, big-endian int) - price * 100000
        - ask volume (4 bytes, big-endian float)
        - bid volume (4 bytes, big-endian float)
        """
        try:
            # Decompress LZMA data
            decompressed = lzma.decompress(compressed_data)
            
            ticks = []
            tick_size = 20  # Each tick is 20 bytes
            num_ticks = len(decompressed) // tick_size
            
            for i in range(num_ticks):
                offset = i * tick_size
                tick_bytes = decompressed[offset:offset + tick_size]
                
                # Unpack tick data (big-endian)
                timestamp_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(
                    '>IIIff', tick_bytes
                )
                
                # Convert prices from integer representation
                ask_price = ask_int / 100000.0
                bid_price = bid_int / 100000.0
                
                tick = {
                    'timestamp_ms': timestamp_ms,
                    'ask': ask_price,
                    'bid': bid_price,
                    'ask_volume': ask_vol,
                    'bid_volume': bid_vol,
                    'mid': (ask_price + bid_price) / 2.0
                }
                
                ticks.append(tick)
            
            return ticks
            
        except Exception as e:
            raise ValueError(f"Failed to decode .bi5 file: {str(e)}")
    
    @staticmethod
    def validate_ticks(ticks: List[Dict]) -> bool:
        """Validate decoded tick data"""
        if not ticks:
            return False
        
        for tick in ticks:
            # Check prices are positive
            if tick['ask'] <= 0 or tick['bid'] <= 0:
                return False
            
            # Check ask >= bid (normal market condition)
            if tick['ask'] < tick['bid']:
                return False
        
        return True
