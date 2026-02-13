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
        print("✅ ASTARBOT: Filtreli Sistem Aktif (Hacim + MSS + %2 Max Stop)")

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
            # Verileri çek (MSS için biraz daha fazla mum çekiyoruz)
            d5 = self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
            d1 = self.exchange.fetch_ohlcv(symbol, '1m', limit=10)
            if not d5 or not d1: return None
            
            df5 = pd.DataFrame(d5, columns=['ts','o','h','l','c','v'])
            df1 = pd.DataFrame(d1, columns=['ts','o','h','l','c','v'])
            
            # Kanal Seviyeleri
            r_high, r_low = df5['h'].max(), df5['l'].min()
            entry = df1['c'].iloc[-1]
            
            # 1. TEMEL KIRILIM KONTROLÜ
            side = None
            if entry > r_high: side = "LONG"
            elif entry < r_low: side = "SHORT"
            
            if side:
                # 2. HACİM FİLTRESİ (Son mum hacmi ortalamanın üstünde mi?)
                avg_vol = df1['v'].iloc[-6:-1].mean()
                last_vol = df1['v'].iloc[-1]
                if last_vol <= avg_vol: return None

                # 3. MSS (Market Structure Shift) KONTROLÜ
                if side == "LONG":
                    # Kanal içindeki son 10 mumun en yüksek tepesini de geçmeli
                    recent_swing_high = df5['h'].iloc[-10:].max()
                    if entry <= recent_swing_high: return None
                    
                    # Stop ve TP Hesabı
                    sl = r_low * (1 - Config.STOP_OFFSET)
                    if sl < entry * (1 - Config.MAX_STOP_PERCENT): sl = entry * (1 - Config.MAX_STOP_PERCENT)
                    tp = entry + ((entry - sl) * Config.RR_RATIO)
                    
                else: # SHORT
                    # Kanal içindeki son 10 mumun en düşük dibini de kırmalı
                    recent_swing_low = df5['l'].iloc[-10:].min()
                    if entry >= recent_swing_low: return None
                    
                    # Stop ve TP Hesabı
                    sl = r_high * (1 + Config.STOP_OFFSET)
                    if sl > entry * (1 + Config.MAX_STOP_PERCENT): sl = entry * (1 + Config.MAX_STOP_PERCENT)
                    tp = entry - ((sl - entry) * Config.RR_RATIO)

                return {
                    "side": side, 
                    "entry": entry, 
                    "sl": round(sl, 6), 
                    "tp": round(tp, 6),
                    "mss": "✅",
                    "vol": "✅"
                }
        except: pass
        return None

    async def trade_monitor_loop(self):
        while True:
            await self.check_tracked_trades()
            await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)

    async def run_forever(self):
        self.active_symbols = self.get_all_futures_symbols()
        await self.send_telegram(f"🚀 <b>ASTARBOT: MSS+HACİM AKTİF</b>\n{len(self.active_symbols)} parite | RR: {Config.RR_RATIO}")
        
        asyncio.create_task(self.trade_monitor_loop())
        
        while True:
            print(f"\n⚡ YENİ TARAMA DÖNGÜSÜ: {datetime.now().strftime('%H:%M:%S')}")
            found = 0
            for i, symbol in enumerate(self.active_symbols, 1):
                print(f"🧐 [{i}/{len(self.active_symbols)}] {symbol} inceleniyor...", end="\r")
                if symbol in self.tracked_trades: continue
                
                signal = self.analyze_symbol(symbol)
                if signal:
                    found += 1
                    print(f"\n✅ MSS ONAYLI SİNYAL: {symbol} ({signal['side']})")
                    msg = (f"🟢 <b>YENİ SİNYAL: {symbol}</b>\n"
                           f"Yön: {signal['side']}\n"
                           f"Giriş: {signal['entry']}\n"
                           f"🔥 TP: {signal['tp']}\n"
                           f"🛡️ SL: {signal['sl']}\n"
                           f"Hacim: {signal['vol']} | MSS: {signal['mss']}")
                    await self.send_telegram(msg)
                    self.tracked_trades[symbol] = signal
                await asyncio.sleep(0.12)

            print(f"\n✅ Tarama bitti. {found} sinyal bulundu. 10 dk mola...")
            await asyncio.sleep(Config.SCAN_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    bot = TelegramScalpingBot()
    asyncio.run(bot.run_forever())
