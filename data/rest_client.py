"""
trading_bot.data.rest_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Binance Futures REST API istemcisi.
Geçmiş mum verilerini stratejinin talep ettiği zaman dilimlerinde çeker.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import aiohttp
import numpy as np

from core.logger import get_logger

logger = get_logger(__name__)


async def fetch_historical_klines(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str = "1m",
    limit: int = 1000,
) -> np.ndarray:
    """
    Binance Futures /fapi/v1/klines üzerinden belirtilen zaman diliminde
    geçmiş verisi çeker.
    """
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit,
    }

    try:
        await asyncio.sleep(0.05)  # Rate limit koruması
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                logger.error("rest_fetch_error", symbol=symbol, interval=interval, status=resp.status)
                return np.empty((0, 6))

            data = await resp.json()
            klines = [
                [float(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
                for k in data
            ]
            return np.array(klines, dtype=np.float64) if klines else np.empty((0, 6))

    except Exception as e:
        logger.error("rest_exception", symbol=symbol, interval=interval, error=str(e))
        return np.empty((0, 6))


async def preload_history(
    symbols: list[str],
    store: 'MemoryStore',
    timeframes: list[str],
    limit: int = 250,
    max_concurrent: int = 20,
) -> None:
    """
    Tüm semboller için istenen zaman dilimlerinde geçmişi çeker ve MemoryStore'u doldurur.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("preload_started", symbol_count=len(symbols), timeframes=timeframes, limit=limit)

    semaphore = asyncio.Semaphore(max_concurrent)

    async with aiohttp.ClientSession() as session:
        async def _process_symbol(symbol: str):
            async with semaphore:
                for tf in timeframes:
                    klines = await fetch_historical_klines(session, symbol, interval=tf, limit=limit)
                    if klines.size == 0:
                        continue
                    for candle in klines:
                        await store.update_candle(symbol, tf, candle.tolist(), is_closed=True)

        tasks = [_process_symbol(s) for s in symbols]
        await asyncio.gather(*tasks)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("preload_complete", elapsed_sec=round(elapsed, 2))
