import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from config import Config

class TelegramScalpingBot:
    def __init__(self):
        # Nesneleri burada sadece tanımlıyoruz, döngü içinde oluşturacağız
        self.exchange = None
        self.telegram_bot = Bot(token=Config.BOT_TOKEN)
        self.active_symbols = []
        self.tracked_trades = {}
        self.semaphore = None

    async def initialize(self):
        """Asenkron nesneleri aktif döngü içinde oluşturur (HATA ÇÖZÜMÜ)"""
        if self.exchange is None:
            self.exchange = ccxt.binance({
                'options': {'defaultType': 'future'},
                'enableRateLimit': True  
            })
            self.semaphore = asyncio.Semaphore(15)
            self.active_symbols = await self.get_all_futures_symbols()

    async def send_telegram(self, message):
        try: await self.telegram_bot.send_message(chat_id=Config.CHAT_ID, text=message, parse_mode=ParseMode.HTML)
        except: pass

    async def get_all_futures_symbols(self):
        try:
            markets = await self.exchange.fetch_markets()
            return [m['symbol'] for m in markets if m['active'] and m['quote'] == 'USDT' and m.get('type') == 'swap']
        except: return ['BTC/USDT', 'ETH/USDT']

    async def fetch_ohlcv_parallel(self, symbol):
        tasks = [self.exchange.fetch_ohlcv(symbol, '1m', limit=210), self.exchange.fetch_ohlcv(symbol, '5m', limit=50)]
        return await asyncio.gather(*tasks)

    async def analyze_symbol_async(self, symbol):
        async with self.semaphore:
            try:
                d1_raw, d5_raw = await self.fetch_ohlcv_parallel(symbol)
                df1 = pd.DataFrame(d1_raw, columns=['ts','o','h','l','c','v'])
                df5 = pd.DataFrame(d5_raw, columns=['ts','o','h','l','c','v'])
                
                df1['ema200'] = df1['c'].ewm(span=200, adjust=False).mean()
                last_ema = df1['ema200'].iloc[-1]
                r_high, r_low = df5['h'].max(), df5['l'].min()
                entry = df1['c'].iloc[-1]
                
                side = None
                if entry > r_high and entry > last_ema: side = "LONG"
                elif entry < r_low and entry < last_ema: side = "SHORT"
                
                if side:
                    avg_vol = df1['v'].iloc[-6:-1].mean()
                    if df1['v'].iloc[-1] <= avg_vol: return None

                    if side == "LONG":
                        if entry <= df5['h'].iloc[-10:].max(): return None
                        sl = max(r_low * (1 - Config.STOP_OFFSET), entry * (1 - Config.MAX_STOP_PERCENT))
                        tp = entry + ((entry - sl) * Config.RR_RATIO)
                    else:
                        if entry >= df5['l'].iloc[-10:].min(): return None
                        sl = min(r_high * (1 + Config.STOP_OFFSET), entry * (1 + Config.MAX_STOP_PERCENT))
                        tp = entry - ((sl - entry) * Config.RR_RATIO)

                    return {"symbol": symbol, "side": side, "entry": entry, "sl": round(sl, 6), "tp": round(tp, 6), "time": datetime.now()}
            except: return None

    async def check_tracked_trades(self):
        if not self.tracked_trades: return
        symbols = list(self.tracked_trades.keys())
        tasks = [self.exchange.fetch_ticker(s) for s in symbols]
        tickers = await asyncio.gather(*tasks, return_exceptions=True)

        for i, ticker in enumerate(tickers):
            if isinstance(ticker, Exception): continue
            symbol, trade, price = symbols[i], self.tracked_trades[symbols[i]], ticker['last']
            elapsed = (datetime.now() - trade['time']).total_seconds() / 3600
            
            if elapsed >= Config.TIME_STOP_HOURS:
                if (trade['side'] == "LONG" and price > trade['entry']) or (trade['side'] == "SHORT" and price < trade['entry']):
                    await self.send_telegram(f"⏰ <b>{symbol} Zaman Aşımı:</b> Kârda kapatıldı. 💰")
                    del self.tracked_trades[symbol]; continue

            if (trade['side'] == "LONG" and price >= trade['tp']) or (trade['side'] == "SHORT" and price <= trade['tp']):
                await self.send_telegram(f"✅ <b>{symbol} TP!</b>"); del self.tracked_trades[symbol]
            elif (trade['side'] == "LONG" and price <= trade['sl']) or (trade['side'] == "SHORT" and price >= trade['sl']):
                await self.send_telegram(f"❌ <b>{symbol} SL!</b>"); del self.tracked_trades[symbol]

    async def run_forever(self):
        # 1. Döngü içindeki nesneleri oluştur
        await self.initialize()
        await self.send_telegram("🚀 <b>ASTARBOT v3.2 AKTİF (Docker Fix)</b>")
        
        asyncio.create_task(self.monitor_loop())

        while True:
            now = datetime.now()
            wait_sec = ((Config.SCAN_INTERVAL_MINUTES - (now.minute % Config.SCAN_INTERVAL_MINUTES)) * 60) - now.second
            if 5 < wait_sec < (Config.SCAN_INTERVAL_MINUTES * 60 - 5):
                print(f"😴 Bekleme: {wait_sec}sn"); await asyncio.sleep(wait_sec)

            print(f"⚡ TARAMA: {datetime.now().strftime('%H:%M:%S')}")
            tasks = [self.analyze_symbol_async(s) for s in self.active_symbols if s not in self.tracked_trades]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    msg = (f"🟢 <b>YENİ SİNYAL: {res['symbol']}</b>\nYön: {res['side']}\nGiriş: {res['entry']}\n"
                           f"🔥 TP: {res['tp']}\n🛡️ SL: {res['sl']}")
                    await self.send_telegram(msg)
                    self.tracked_trades[res['symbol']] = res
            await asyncio.sleep(20)

    async def monitor_loop(self):
        while True:
            await self.check_tracked_trades()
            await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)

    async def shutdown(self):
        """Bağlantıları güvenli kapatır (Hata mesajını önler)"""
        if self.exchange:
            await self.exchange.close()
            print("🛑 Borsa bağlantısı kapatıldı.")

if __name__ == "__main__":
    bot = TelegramScalpingBot()
    try:
        asyncio.run(bot.run_forever())
    except KeyboardInterrupt:
        asyncio.run(bot.shutdown())
