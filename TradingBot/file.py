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
        # Asenkron borsa ve Rate Limit koruması
        self.exchange = ccxt.binance({
            'options': {'defaultType': 'future'},
            'enableRateLimit': True  
        })
        self.bot_token = Config.BOT_TOKEN
        self.chat_id = Config.CHAT_ID
        self.telegram_bot = Bot(token=self.bot_token)
        
        self.active_symbols = []
        self.tracked_trades = {}
        # Rate Limit Koruması: Eşzamanlı maksimum 15 istek
        self.semaphore = asyncio.Semaphore(15) 
        print("🚀 ASTARBOT v3.0: Ultra-Asenkron & Trend Filtreli Sistem Aktif!")

    async def send_telegram(self, message):
        try: await self.telegram_bot.send_message(chat_id=self.chat_id, text=message, parse_mode=ParseMode.HTML)
        except Exception as e: print(f"Telegram Hatası: {e}")

    async def get_all_futures_symbols(self):
        try:
            markets = await self.exchange.fetch_markets()
            symbols = [m['symbol'] for m in markets if m['active'] and m['quote'] == 'USDT' and m.get('type') == 'swap']
            print(f"🌍 {len(symbols)} parite Binance'ten güncellendi.")
            return symbols
        except Exception as e:
            print(f"❌ Parite çekme hatası: {e}")
            return ['BTC/USDT', 'ETH/USDT']

    async def fetch_ohlcv_parallel(self, symbol):
        """Performans: 1m ve 5m verilerini aynı anda çeker."""
        tasks = [
            self.exchange.fetch_ohlcv(symbol, '1m', limit=210),
            self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
        ]
        return await asyncio.gather(*tasks)

    async def analyze_symbol_async(self, symbol):
        """Asenkron Analiz: Her pariteyi paralel ve filtrelerle tarar."""
        async with self.semaphore: # Rate Limit Koruması
            try:
                # Verileri paralel çek
                d1_raw, d5_raw = await self.fetch_ohlcv_parallel(symbol)
                if not d1_raw or not d5_raw: return None
                
                df1 = pd.DataFrame(d1_raw, columns=['ts','o','h','l','c','v'])
                df5 = pd.DataFrame(d5_raw, columns=['ts','o','h','l','c','v'])
                
                # --- STRATEJİK FİLTRELER ---
                # 1. Trend Filtresi (EMA 200)
                df1['ema200'] = df1['c'].ewm(span=200, adjust=False).mean()
                last_ema = df1['ema200'].iloc[-1]

                # 2. Kanal Kırılımı
                r_high, r_low = df5['h'].max(), df5['l'].min()
                entry = df1['c'].iloc[-1]
                
                side = None
                if entry > r_high and entry > last_ema: side = "LONG"
                elif entry < r_low and entry < last_ema: side = "SHORT"
                
                if side:
                    # 3. Hacim Filtresi
                    avg_vol = df1['v'].iloc[-6:-1].mean()
                    last_vol = df1['v'].iloc[-1]
                    if last_vol <= avg_vol: return None

                    # 4. MSS (Market Structure Shift) Onayı
                    if side == "LONG":
                        recent_high = df5['h'].iloc[-10:].max()
                        if entry <= recent_high: return None
                        sl = r_low * (1 - Config.STOP_OFFSET)
                        if sl < entry * (1 - Config.MAX_STOP_PERCENT): sl = entry * (1 - Config.MAX_STOP_PERCENT)
                        tp = entry + ((entry - sl) * Config.RR_RATIO)
                    else: # SHORT
                        recent_low = df5['l'].iloc[-10:].min()
                        if entry >= recent_low: return None
                        sl = r_high * (1 + Config.STOP_OFFSET)
                        if sl > entry * (1 + Config.MAX_STOP_PERCENT): sl = entry * (1 + Config.MAX_STOP_PERCENT)
                        tp = entry - ((sl - entry) * Config.RR_RATIO)

                    return {
                        "symbol": symbol, "side": side, "entry": entry,
                        "sl": round(sl, 6), "tp": round(tp, 6), "time": datetime.now()
                    }
            except: return None
        return None

    async def check_tracked_trades(self):
        """Açık işlemlerin TP/SL kontrolünü asenkron yapar."""
        if not self.tracked_trades: return
        
        # Takipteki işlemler için ticker verilerini toplu çekmek daha hızlıdır
        symbols = list(self.tracked_trades.keys())
        tasks = [self.exchange.fetch_ticker(s) for s in symbols]
        tickers = await asyncio.gather(*tasks, return_exceptions=True)

        for i, ticker in enumerate(tickers):
            if isinstance(ticker, Exception): continue
            symbol = symbols[i]
            trade = self.tracked_trades[symbol]
            price = ticker['last']
            
            # Zaman Stopu Kontrolü: 4 saatten uzun süren işlemlerde stopu girişe çek
            elapsed = (datetime.now() - trade['time']).total_seconds() / 3600
            if elapsed > 4 and trade['sl'] != trade['entry']:
                self.tracked_trades[symbol]['sl'] = trade['entry']
                print(f"🛡️ {symbol} için 4 saat doldu, stop girişe çekildi.")

            # TP/SL Kontrolü
            if (trade['side'] == "LONG" and price >= trade['tp']) or (trade['side'] == "SHORT" and price <= trade['tp']):
                await self.send_telegram(f"✅ <b>{symbol} TP OLDU!</b> 💰")
                del self.tracked_trades[symbol]
            elif (trade['side'] == "LONG" and price <= trade['sl']) or (trade['side'] == "SHORT" and price >= trade['sl']):
                await self.send_telegram(f"❌ <b>{symbol} SL OLDU.</b> 📉")
                del self.tracked_trades[symbol]

    async def run_forever(self):
        self.active_symbols = await self.get_all_futures_symbols()
        await self.send_telegram("🚀 <b>ASTARBOT v3.0 AKTİF</b>\nAsenkron Tarama + EMA200 + MSS + Zaman Stopu Aktif.")
        
        # TP/SL Kontrol Döngüsü
        async def monitor_loop():
            while True:
                await self.check_tracked_trades()
                await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)
        
        asyncio.create_task(monitor_loop())

        while True:
            # Zaman Senkronizasyonu (Tam mum kapanışı)
            now = datetime.now()
            wait_min = Config.SCAN_INTERVAL_MINUTES - (now.minute % Config.SCAN_INTERVAL_MINUTES)
            wait_sec = (wait_min * 60) - now.second
            if wait_sec > 5 and wait_sec < (Config.SCAN_INTERVAL_MINUTES * 60 - 5):
                print(f"😴 Mum kapanışı bekleniyor: {wait_sec} saniye...")
                await asyncio.sleep(wait_sec)

            print(f"\n⚡ ASENKRON TARAMA BAŞLADI: {datetime.now().strftime('%H:%M:%S')}")
            start_t = datetime.now()
            
            # Analiz Görevlerini Toplu Başlat (gather)
            tasks = [self.analyze_symbol_async(s) for s in self.active_symbols if s not in self.tracked_trades]
            results = await asyncio.gather(*tasks)
            
            found = 0
            for res in results:
                if res:
                    found += 1
                    msg = (f"🟢 <b>YENİ SİNYAL: {res['symbol']}</b>\nYön: {res['side']}\n"
                           f"Giriş: {res['entry']}\n🔥 TP: {res['tp']}\n🛡️ SL: {res['sl']}\n"
                           f"Trend: 🚀 | Hacim: ✅ | MSS: ✅")
                    await self.send_telegram(msg)
                    self.tracked_trades[res['symbol']] = res
            
            end_t = datetime.now()
            print(f"✅ Tarama {(end_t - start_t).total_seconds():.2f}sn sürdü. {found} sinyal bulundu.")
            await asyncio.sleep(10) # Kısa mola ve döngü başı

if __name__ == "__main__":
    bot = TelegramScalpingBot()
    try:
        asyncio.run(bot.run_forever())
    except KeyboardInterrupt:
        print("Bot durduruldu.")
