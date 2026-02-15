import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from config import Config

class TelegramScalpingBot:
    def __init__(self):
        self.exchange = ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True})
        self.bot_token = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
        self.chat_id = '-1002547240908'
        self.telegram_bot = Bot(token=self.bot_token)
        
        self.active_symbols = []
        self.tracked_trades = {}
        print("✅ ASTARBOT v2: Trend (EMA 200) + Senkronize Tarama Aktif")

    async def send_telegram(self, message):
        try: await self.telegram_bot.send_message(chat_id=self.chat_id, text=message, parse_mode=ParseMode.HTML)
        except: pass

    def get_all_futures_symbols(self):
        try:
            markets = self.exchange.fetch_markets()
            symbols = [m['symbol'] for m in markets if m['active'] and m['quote'] == 'USDT' and m.get('type') == 'swap']
            print(f"🌍 Toplam {len(symbols)} parite bulundu.")
            return symbols
        except Exception as e:
            print(f"❌ Parite çekme hatası: {e}")
            return ['BTC/USDT', 'ETH/USDT']

    async def check_tracked_trades(self):
        now = datetime.now().strftime('%H:%M:%S')
        trade_count = len(self.tracked_trades)
        print(f"🕒 [{now}] TP/SL Kontrolü yapılıyor... (Aktif İşlem: {trade_count})")
        
        if trade_count == 0: return

        for symbol in list(self.tracked_trades.keys()):
            trade = self.tracked_trades[symbol]
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                price = ticker['last']
                if trade['side'] == "LONG":
                    if price >= trade['tp']:
                        await self.send_telegram(f"✅ <b>{symbol} TP OLDU!</b> 💰")
                        del self.tracked_trades[symbol]
                    elif price <= trade['sl']:
                        await self.send_telegram(f"❌ <b>{symbol} SL OLDU.</b> 📉")
                        del self.tracked_trades[symbol]
                elif trade['side'] == "SHORT":
                    if price <= trade['tp']:
                        await self.send_telegram(f"✅ <b>{symbol} TP OLDU!</b> 💰")
                        del self.tracked_trades[symbol]
                    elif price >= trade['sl']:
                        await self.send_telegram(f"❌ <b>{symbol} SL OLDU.</b> 📉")
                        del self.tracked_trades[symbol]
            except: continue

    def analyze_symbol(self, symbol):
        try:
            # EMA 200 için limitleri artırdık
            d5 = self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
            d1 = self.exchange.fetch_ohlcv(symbol, '1m', limit=210) 
            if not d5 or not d1: return None
            
            df5 = pd.DataFrame(d5, columns=['ts','o','h','l','c','v'])
            df1 = pd.DataFrame(d1, columns=['ts','o','h','l','c','v'])
            
            # --- YENİ: TREND FİLTRESİ (EMA 200) ---
            df1['ema200'] = df1['c'].ewm(span=200, adjust=False).mean()
            last_ema = df1['ema200'].iloc[-1]

            # Kanal Seviyeleri
            r_high, r_low = df5['h'].max(), df5['l'].min()
            entry = df1['c'].iloc[-1]
            
            # 1. TEMEL KIRILIM + EMA TREND UYUMU
            side = None
            if entry > r_high and entry > last_ema: side = "LONG"
            elif entry < r_low and entry < last_ema: side = "SHORT"
            
            if side:
                # 2. HACİM FİLTRESİ
                avg_vol = df1['v'].iloc[-6:-1].mean()
                last_vol = df1['v'].iloc[-1]
                if last_vol <= avg_vol: return None

                # 3. MSS (Market Structure Shift) KONTROLÜ
                if side == "LONG":
                    recent_swing_high = df5['h'].iloc[-10:].max()
                    if entry <= recent_swing_high: return None
                    
                    sl = r_low * (1 - Config.STOP_OFFSET)
                    if sl < entry * (1 - Config.MAX_STOP_PERCENT): sl = entry * (1 - Config.MAX_STOP_PERCENT)
                    tp = entry + ((entry - sl) * Config.RR_RATIO)
                    
                else: # SHORT
                    recent_swing_low = df5['l'].iloc[-10:].min()
                    if entry >= recent_swing_low: return None
                    
                    sl = r_high * (1 + Config.STOP_OFFSET)
                    if sl > entry * (1 + Config.MAX_STOP_PERCENT): sl = entry * (1 + Config.MAX_STOP_PERCENT)
                    tp = entry - ((sl - entry) * Config.RR_RATIO)

                return {
                    "side": side, 
                    "entry": entry, 
                    "sl": round(sl, 6), 
                    "tp": round(tp, 6),
                    "mss": "✅",
                    "vol": "✅",
                    "trend": "🚀"
                }
        except: pass
        return None

    async def trade_monitor_loop(self):
        while True:
            await self.check_tracked_trades()
            await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)

    async def run_forever(self):
        self.active_symbols = self.get_all_futures_symbols()
        await self.send_telegram(f"🚀 <b>ASTARBOT v2: AKTİF</b>\nEMA Trend + Senkronize Tarama Sistemi Devrede.")
        
        asyncio.create_task(self.trade_monitor_loop())
        
        while True:
            # --- YENİ: ZAMAN SENKRONİZASYONU ---
            now = datetime.now()
            # Bir sonraki 15 dakikanın katına kadar bekle (00, 15, 30, 45)
            wait_minutes = Config.SCAN_INTERVAL_MINUTES - (now.minute % Config.SCAN_INTERVAL_MINUTES)
            wait_seconds = (wait_minutes * 60) - now.second
            
            # Eğer tam dakikada değilsek bekle, tam dakikadaysak (0-10sn pay) taramaya geç
            if wait_seconds > 10 and wait_seconds < (Config.SCAN_INTERVAL_MINUTES * 60 - 10):
                print(f"😴 Mum kapanışı için {wait_seconds} saniye bekleniyor...")
                await asyncio.sleep(wait_seconds)

            print(f"\n⚡ STRATEJİK TARAMA BAŞLADI: {datetime.now().strftime('%H:%M:%S')}")
            found = 0
            for i, symbol in enumerate(self.active_symbols, 1):
                print(f"🧐 [{i}/{len(self.active_symbols)}] {symbol} inceleniyor...", end="\r")
                if symbol in self.tracked_trades: continue
                
                signal = self.analyze_symbol(symbol)
                if signal:
                    found += 1
                    print(f"\n✅ ONAYLI SİNYAL: {symbol} ({signal['side']})")
                    msg = (f"🟢 <b>YENİ SİNYAL: {symbol}</b>\n"
                           f"Yön: {signal['side']}\n"
                           f"Giriş: {signal['entry']}\n"
                           f"🔥 TP: {signal['tp']}\n"
                           f"🛡️ SL: {signal['sl']}\n"
                           f"Hacim: {signal['vol']} | MSS: {signal['mss']} | Trend: {signal['trend']}")
                    await self.send_telegram(msg)
                    self.tracked_trades[symbol] = signal
                await asyncio.sleep(0.12)

            print(f"\n✅ Tarama bitti. {found} sinyal bulundu. Beklemeye geçiliyor...")
            # Tarama bittikten sonra döngü başa döner ve wait_seconds tekrar hesaplanır.
            await asyncio.sleep(10) 

if __name__ == "__main__":
    bot = TelegramScalpingBot()
    asyncio.run(bot.run_forever())
