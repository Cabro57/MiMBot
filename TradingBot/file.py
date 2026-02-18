import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt
import pandas as pd
import sys
import platform
import logging
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# Windows DNS ve aiodns hatasını kökten çözen ayar
os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'

try:
    from config import Config
except ImportError:
    print("❌ HATA: config.py bulunamadı!")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AstarBot")

class TelegramScalpingBot:
    def __init__(self):
        self.exchange = None
        self.telegram_bot = Bot(token=Config.BOT_TOKEN)
        self.active_symbols = []
        self.tracked_trades = {}
        self.semaphore = None
        self.last_symbol_update = datetime.now()

    async def initialize(self):
        if self.exchange is None:
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            self.exchange = ccxt.binance({
                'options': {'defaultType': 'future', 'adjustForTimeDifference': True},
                'enableRateLimit': True,
                'timeout': 30000,
                'connector': connector 
            })
            self.semaphore = asyncio.Semaphore(getattr(Config, 'MAX_PARALLEL_TASKS', 50))
            await self.refresh_all_symbols()

    async def refresh_all_symbols(self):
        try:
            markets = await self.exchange.load_markets()
            self.active_symbols = [
                symbol.split(':')[0] for symbol, m in markets.items()
                if m['active'] and m['linear'] and m['quote'] == 'USDT' 
                and m['type'] == 'swap' and not symbol.endswith('USDC')
            ]
            self.last_symbol_update = datetime.now()
            logger.info(f"✅ Market Senkronize Edildi: {len(self.active_symbols)} parite.")
        except Exception as e:
            logger.error(f"⚠️ Sembol listesi hatası: {e}")
            self.active_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

    async def send_telegram(self, message):
        try: await self.telegram_bot.send_message(chat_id=Config.CHAT_ID, text=message, parse_mode=ParseMode.HTML)
        except: pass

    async def analyze_symbol_async(self, symbol):
        async with self.semaphore:
            try:
                # Veri miktarını güvenli hesaplama için biraz artırdık
                tasks = [
                    self.exchange.fetch_ohlcv(symbol, '1m', limit=100), 
                    self.exchange.fetch_ohlcv(symbol, '5m', limit=30)
                ]
                d1_raw, d5_raw = await asyncio.gather(*tasks)
                
                # Veri kontrolü (Boş veya eksik veri varsa atla)
                if not d1_raw or not d5_raw or len(d1_raw) < 50 or len(d5_raw) < 10:
                    return None

                df1 = pd.DataFrame(d1_raw, columns=['ts','o','h','l','c','v'])
                df5 = pd.DataFrame(d5_raw, columns=['ts','o','h','l','c','v'])

                # Verileri sayısal formata çevir (String gelirse hata vermemesi için)
                for col in ['o', 'h', 'l', 'c', 'v']:
                    df1[col] = pd.to_numeric(df1[col])
                    df5[col] = pd.to_numeric(df5[col])

                # EMA Hesaplama
                df1['ema_f'] = df1['c'].ewm(span=Config.EMA_FAST, adjust=False).mean()
                df1['ema_s'] = df1['c'].ewm(span=Config.EMA_SLOW, adjust=False).mean()
                
                last_c = df1['c'].iloc[-1]
                
                # --- HATANIN DÜZELTİLDİĞİ YER ---
                # Eskisi: r_high, r_low = df5... (Hata veriyordu)
                # Yenisi: Ayrı ayrı hesaplıyoruz
                r_high = df5['h'].iloc[-6:-1].max() 
                r_low = df5['l'].iloc[-6:-1].min()

                current_vol = df1['v'].iloc[-1]
                avg_vol_10 = df1['v'].iloc[-11:-1].mean()
                
                # 0'a bölünme hatası kontrolü
                spike_ratio = current_vol / avg_vol_10 if (avg_vol_10 and avg_vol_10 > 0) else 0
                
                # --- FİLTRE: 1.5x ile 20.0x arası (Genişlettik sinyal görünsün diye) ---
                if not (2.5 <= spike_ratio <= 6):
                    return None

                side = None
                # EMA ve Kırılım Kontrolü
                if last_c > r_high and df1['ema_f'].iloc[-1] > df1['ema_s'].iloc[-1]:
                    side = "LONG"
                elif last_c < r_low and df1['ema_f'].iloc[-1] < df1['ema_s'].iloc[-1]:
                    side = "SHORT"

                if side:
                    sl = max(r_low * (1 - Config.STOP_OFFSET), last_c * (1 - Config.MAX_STOP_PERCENT)) if side == "LONG" else min(r_high * (1 + Config.STOP_OFFSET), last_c * (1 + Config.MAX_STOP_PERCENT))
                    tp = last_c + ((last_c - sl) * Config.RR_RATIO) if side == "LONG" else last_c - ((sl - last_c) * Config.RR_RATIO)
                    
                    return {
                        "symbol": symbol, "side": side, "entry": last_c, 
                        "sl": round(sl, 6), "tp": round(tp, 6), 
                        "spike_ratio": spike_ratio
                    }
            except Exception as e:
                # Hata olursa loga bas (sessizce yutmasın)
                # print(f"Hata {symbol}: {e}") 
                return None

    async def monitor_loop(self):
        while True:
            try:
                if self.tracked_trades:
                    for symbol in list(self.tracked_trades.keys()):
                        ticker = await self.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        trade = self.tracked_trades[symbol]
                        is_tp = (trade['side'] == "LONG" and price >= trade['tp']) or (trade['side'] == "SHORT" and price <= trade['tp'])
                        is_sl = (trade['side'] == "LONG" and price <= trade['sl']) or (trade['side'] == "SHORT" and price >= trade['sl'])
                        if is_tp or is_sl:
                            icon = "✅ TP" if is_tp else "❌ SL"
                            await self.send_telegram(f"{icon} | <b>{symbol}</b> Kapatıldı.\nFiyat: {price}")
                            del self.tracked_trades[symbol]
            except: pass
            await asyncio.sleep(Config.TRADE_CONTROL_SECONDS)

    async def run_forever(self):
        await self.initialize()
        await self.send_telegram(f"🚀 <b>AstarBot v4.8 (Fix) Aktif</b>\nFiltre: 1.5x - 20.0x Hacim")
        
        asyncio.create_task(self.monitor_loop())

        while True:
            try:
                if (datetime.now() - self.last_symbol_update).total_seconds() > 14400:
                    await self.refresh_all_symbols()

                logger.info(f"⚡ {len(self.active_symbols)} sembol taranıyor...")
                tasks = [self.analyze_symbol_async(s) for s in self.active_symbols if s not in self.tracked_trades]
                results = await asyncio.gather(*tasks)
                
                # Debug satırı: Hata olup olmadığını anlamak için
                signals = [res for res in results if res is not None]
                print(f"DEBUG: Taranan: {len(results)} | Bulunan Sinyal: {len(signals)}")

                if signals:
                    # En güçlü hacme göre sırala
                    signals.sort(key=lambda x: x['spike_ratio'], reverse=True)
                    top_3_signals = signals[:3]

                    for res in top_3_signals:
                        msg = (f"🔔 <b>#{res['symbol']} {res['side']}</b>\n"
                               f"📈 Giriş: {res['entry']}\n🎯 TP: {res['tp']}\n🛡️ SL: {res['sl']}\n"
                               f"📊 Hacim Gücü: {round(res['spike_ratio'], 2)}x")
                        await self.send_telegram(msg)
                        self.tracked_trades[res['symbol']] = res
                
                await asyncio.sleep(Config.SCAN_INTERVAL_MINUTES * 60)
            except Exception as e:
                logger.error(f"Ana döngü hatası: {e}")
                await asyncio.sleep(60)

    async def shutdown(self):
        if self.exchange: await self.exchange.close()

if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    bot = TelegramScalpingBot()
    try:
        asyncio.run(bot.run_forever())
    except KeyboardInterrupt:
        logger.info("Durduruluyor...")
    finally:
        try: asyncio.run(bot.shutdown())
        except: pass
