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
        print("✅ ASTARBOT: Sistemler aktif. 30sn Takip / 10dk Tarama döngüsü başladı.")

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
        """Bu fonksiyon her 30 saniyede bir çalışır ve CMD'de görünür."""
        now = datetime.now().strftime('%H:%M:%S')
        trade_count = len(self.tracked_trades)
        
        # Her zaman yazdır ki botun çalıştığı anlaşılsın
        print(f"🕒 [{now}] TP/SL Kontrolü yapılıyor... (Aktif İşlem: {trade_count})")
        
        if trade_count == 0: return

        for symbol in list(self.tracked_trades.keys()):
            trade = self.tracked_trades[symbol]
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                price = ticker['last']
                if trade['side'] == "LONG":
                    if price >= trade['tp']:
                        await self.send_telegram(f"✅ <b>{symbol} KÂR AL (TP) HEDEFE ULAŞTI!</b> 💰")
                        print(f"\n💰 {symbol} TP oldu!")
                        del self.tracked_trades[symbol]
                    elif price <= trade['sl']:
                        await self.send_telegram(f"❌ <b>{symbol} STOP (SL) OLDU.</b> 📉")
                        print(f"\n📉 {symbol} SL oldu!")
                        del self.tracked_trades[symbol]
                elif trade['side'] == "SHORT":
                    if price <= trade['tp']:
                        await self.send_telegram(f"✅ <b>{symbol} KÂR AL (TP) HEDEFE ULAŞTI!</b> 💰")
                        print(f"\n💰 {symbol} TP oldu!")
                        del self.tracked_trades[symbol]
                    elif price >= trade['sl']:
                        await self.send_telegram(f"❌ <b>{symbol} STOP (SL) OLDU.</b> 📉")
                        print(f"\n📉 {symbol} SL oldu!")
                        del self.tracked_trades[symbol]
            except: continue

    def analyze_symbol(self, symbol):
        try:
            d5 = self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
            d1 = self.exchange.fetch_ohlcv(symbol, '1m', limit=5)
            if not d5 or not d1: return None
            
            df5 = pd.DataFrame(d5, columns=['ts','o','h','l','c','v'])
            df1 = pd.DataFrame(d1, columns=['ts','o','h','l','c','v'])
            
            h, l = df5['h'].max(), df5['l'].min()
            entry = df1['c'].iloc[-1]
            
            if entry > h: # LONG
                sl = l * (1 - Config.STOP_OFFSET)
                if sl < entry * (1 - Config.MAX_STOP_PERCENT): sl = entry * (1 - Config.MAX_STOP_PERCENT)
                tp = entry + ((entry - sl) * Config.RR_RATIO)
                return {"side": "LONG", "entry": entry, "sl": round(sl, 6), "tp": round(tp, 6)}
            elif entry < l: # SHORT
                sl = h * (1 + Config.STOP_OFFSET)
                if sl > entry * (1 + Config.MAX_STOP_PERCENT): sl = entry * (1 + Config.MAX_STOP_PERCENT)
                tp = entry - ((sl - entry) * Config.RR_RATIO)
                return {"side": "SHORT", "entry": entry, "sl": round(sl, 6), "tp": round(tp, 6)}
        except: pass
        return None

    async def trade_monitor_loop(self):
        """Arka planda TP/SL kontrolü yapar"""
        while True:
            await self.check_tracked_trades()
            await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)

    async def run_forever(self):
        self.active_symbols = self.get_all_futures_symbols()
        await self.send_telegram(f"🚀 <b>ASTARBOT BAŞLADI</b>\n{len(self.active_symbols)} parite taranıyor.\nTakip: 30sn | Tarama: 10dk")
        
        # Takip döngüsünü başlat
        asyncio.create_task(self.trade_monitor_loop())
        
        while True:
            print(f"\n⚡ YENİ TARAMA DÖNGÜSÜ (10 Dakikada bir yapılır): {datetime.now().strftime('%H:%M:%S')}")
            found = 0
            for i, symbol in enumerate(self.active_symbols, 1):
                print(f"🧐 [{i}/{len(self.active_symbols)}] {symbol} inceleniyor...", end="\r")
                if symbol in self.tracked_trades: continue
                
                signal = self.analyze_symbol(symbol)
                if signal:
                    found += 1
                    print(f"\n✅ SİNYAL: {symbol} ({signal['side']})")
                    msg = (f"🟢 <b>YENİ SİNYAL: {symbol}</b>\nYön: {signal['side']}\nGiriş: {signal['entry']}\n"
                           f"🔥 TP: {signal['tp']}\n🛡️ SL: {signal['sl']}\nRR: 1:{Config.RR_RATIO}")
                    await self.send_telegram(msg)
                    self.tracked_trades[symbol] = signal
                await asyncio.sleep(0.12)

            print(f"\n✅ Tarama bitti. {found} sinyal bulundu.")
            print(f"😴 {Config.SCAN_INTERVAL_MINUTES} dakika mola...")
            await asyncio.sleep(Config.SCAN_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    bot = TelegramScalpingBot()
    asyncio.run(bot.run_forever())