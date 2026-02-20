"""
trading_bot.data.rest_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Binance Futures REST API istemcisi.
Geçmiş mum verilerini çekmek ve 5m verisine resample etmek için kullanılır.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

import aiohttp
import numpy as np

from core.logger import get_logger

logger = get_logger(__name__)

# MemoryStore sütun indeksleri
TS, OPEN, HIGH, LOW, CLOSE, VOLUME = 0, 1, 2, 3, 4, 5


async def fetch_historical_1m_klines(
    session: aiohttp.ClientSession, symbol: str, limit: int = 1000
) -> np.ndarray:
    """
    Binance Futures /fapi/v1/klines üzerinden 1m geçmiş verisi çeker.
    """
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": "1m",
        "limit": limit
    }
    
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status != 200:
                logger.error("rest_fetch_error", symbol=symbol, status=resp.status)
                return np.empty((0, 6))
            
            data = await resp.json()
            # Binance format: [ts, o, h, l, c, v, ...] -> ilk 6 sütun lazım
            klines = []
            for k in data:
                klines.append([
                    float(k[0]), # Open time
                    float(k[1]), # Open
                    float(k[2]), # High
                    float(k[3]), # Low
                    float(k[4]), # Close
                    float(k[5])  # Volume
                ])
            return np.array(klines, dtype=np.float64)
            
    except Exception as e:
        logger.error("rest_exception", symbol=symbol, error=str(e))
        return np.empty((0, 6))


def resample_1m_to_5m(klines_1m: np.ndarray) -> np.ndarray:
    """
    1 dakikalık mumları 5 dakikalık bloklara dönüştürür.
    Binance standartlarına göre (start_ts % 300000 == 0) hizalar.
    """
    if klines_1m.size == 0:
        return np.empty((0, 6))

    # 5 dakika = 300,000 ms
    MS_5M = 5 * 60 * 1000
    
    # 1. Her mumu 5m başlangıç zamanına yuvarla
    # timestamps: klines_1m[:, TS]
    resampled_data = []
    
    # Gruplama için bir sözlük kullan (ordered dict gibi davranır Python 3.7+)
    groups = {}
    
    for row in klines_1m:
        ts = row[TS]
        start_ts = ts - (ts % MS_5M)
        
        if start_ts not in groups:
            groups[start_ts] = {
                "open": row[OPEN],
                "high": row[HIGH],
                "low": row[LOW],
                "close": row[CLOSE],
                "volume": row[VOLUME],
                "ts": start_ts
            }
        else:
            g = groups[start_ts]
            g["high"] = max(g["high"], row[HIGH])
            g["low"] = min(g["low"], row[LOW])
            g["close"] = row[CLOSE] # Son gelen kapanış
            g["volume"] += row[VOLUME]

    # Sözlükten diziye çevir
    for ts in sorted(groups.keys()):
        g = groups[ts]
        resampled_data.append([
            g["ts"], g["open"], g["high"], g["low"], g["close"], g["volume"]
        ])
        
    return np.array(resampled_data, dtype=np.float64)


async def preload_history(
    symbols: list[str], 
    store: 'MemoryStore', 
    limit: int = 1000,
    max_concurrent: int = 20
) -> None:
    """
    Tüm semboller için geçmişi çeker ve MemoryStore'u doldurur.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("preload_started", symbol_count=len(symbols), limit=limit)
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession() as session:
        async def _process_symbol(symbol: str):
            async with semaphore:
                # 1. 1m klines çek
                k1m = await fetch_historical_1m_klines(session, symbol, limit)
                if k1m.size == 0:
                    return
                
                # 2. 5m resample et
                k5m = resample_1m_to_5m(k1m)
                
                # 3. Store'a yaz (1m ve 5m)
                # Not: update_candle awaitable'dır.
                for candle in k1m:
                    await store.update_candle(symbol, "1m", candle.tolist(), is_closed=True)
                
                for candle in k5m:
                    await store.update_candle(symbol, "5m", candle.tolist(), is_closed=True)
                    
        tasks = [_process_symbol(s) for s in symbols]
        await asyncio.gather(*tasks)
        
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("preload_complete", elapsed_sec=round(elapsed, 2))
