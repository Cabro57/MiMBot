# config.py

class Config:
    # --- Telegram Bilgileri ---
    # Botun sinyal ve bildirim göndereceği adresler
    BOT_TOKEN = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
    CHAT_ID = '-1002547240908'

    # --- Otomatik Parite Ayarları ---
    # Boş bırakıldığında bot tüm Binance Futures USDT paritelerini (250+) tarar.
    SYMBOLS = [] 

    # --- Zamanlama Ayarları ---
    # Bot her 15 dakikanın katında (00, 15, 30, 45) otomatik senkronize olur.
    SCAN_INTERVAL_MINUTES = 15 
    
    # Açık işlemleri (TP/SL) kontrol etme sıklığı (Saniye).
    TRADE_CONTROL_SECONDS = 30 
    
    # --- Risk ve Strateji Ayarları ---
    RR_RATIO = 1.4             # 1:1.4 Risk/Ödül oranı (Hedef = Stop x 1.4)
    MAX_STOP_PERCENT = 0.02    # %2 Maksimum Stop Loss sınırı (Kasa koruması için zorunlu)
    STOP_OFFSET = 0.0005       # Teknik stop seviyesine eklenen küçük esneme payı
    
    # --- v3.1 Akıllı Zaman Stopu Ayarları ---
    # İşlem bu saatten uzun sürerse ve kârda ise otomatik kapatılır.
    TIME_STOP_HOURS = 4        
    
    # --- Teknik Filtre Ayarları ---
    # Trend yönünü belirleyen ana hareketli ortalama periyodu.
    EMA_TREND_PERIOD = 200     
    BREAKOUT_TIMEFRAME = '1m'  # Kırılım onayı için kullanılan alt zaman dilimi
    
    # --- Log Ayarları ---
    ENABLE_CONSOLE_LOG = True  # Terminal ekranında detaylı bilgi akışını gösterir
