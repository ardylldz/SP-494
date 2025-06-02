import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont
import os # OS modülü eklendi

# ========== CONFIGURATION ==========
# customtkinter varsayılan ayarları
ctk.set_appearance_mode("dark") # Başlangıçta koyu mod
ctk.set_default_color_theme("blue") # Varsayılan tema (widget'ların genel mavi tonu)

# Constants
SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096
TIMEOUT_THRESHOLD = 3 # seconds

# --- Image Paths ---
# Statik yer tutucu resim (drone durduğunda veya GIF yüklenemediğinde)
DRONE_IMAGE_PATH = "drone_feed_placeholder.png"
# Drone uçuşu için animasyonlu GIF
# Kendi yolunuza göre güncellemeyi unutmayın!
DRONE_GIF_PATH = "/home/arda/Masaüstü/Drone.gif"

# --- Kart ve Besleme Boyutları ---
CARD_WIDTH_SMALL = 300 # Daha küçük kart genişliği
CARD_HEIGHT_SMALL = 380 # Daha küçük kart yüksekliği (içeriğe göre ayarlandı)
FEED_WIDTH_SMALL = CARD_WIDTH_SMALL - 40 # örn. 260
FEED_HEIGHT_SMALL = 150 # Daha küçük besleme yüksekliği

# Renk Temaları
# Koyu Tema Renkleri
COLORS_DARK = {
    "primary": "#1E1E2E",       # Ana navigasyon kenar çubuğu
    "secondary": "#2A2A3A",     # QGC paneli, nav butonları için hover
    "tertiary": "#272A3A",      # QGC paneli için biraz farklı bir ton (gerekirse)
    "accent": "#4E9FEC",        # Vurgu rengi
    "success": "#2ECC71",
    "success_hover": "#27AE60",
    "danger": "#E74C3C",
    "danger_hover": "#C0392B",
    "warning": "#F39C12",
    "dark": "#121212",          # Ana içerik alanı arka planı
    "card_bg": "#2C3E50",       # Kart arka planı
    "text_primary": "#FFFFFF",  # Birincil metin rengi
    "text_secondary": "#B8B8B8", # İkincil metin rengi
    "gray": "#7F8C8D",          # Gri tonu
    "disconnected": "#5B5B5B"   # Bağlantı kesildiğinde kullanılacak renk
}

# Açık Tema Renkleri
COLORS_LIGHT = {
    "primary": "#E0E0E0",       # Açık tema için ana arka plan
    "secondary": "#F0F0F0",     # Açık tema için ikincil arka plan
    "tertiary": "#E8E8E8",
    "accent": "#1ABC9C",        # Farklı bir vurgu rengi
    "success": "#28B463",
    "success_hover": "#239B56",
    "danger": "#CB4335",
    "danger_hover": "#B03A2E",
    "warning": "#F5B041",
    "dark": "#FFFFFF",          # Ana içerik alanı arka planı
    "card_bg": "#ECF0F1",       # Açık kart arka planı
    "text_primary": "#333333",   # Koyu metin
    "text_secondary": "#666666", # Daha açık koyu metin
    "gray": "#AAAAAA",
    "disconnected": "#888888"
}

# Başlangıçta kullanılacak renk temasını ayarla
COLORS = COLORS_DARK # Bu, uygulamanın başlangıçta kullanacağı renk sözlüğüdür

# Dummy yer tutucu resim oluşturma (dosya yoksa)
try:
    with Image.open(DRONE_IMAGE_PATH) as img:
        img.load()
except FileNotFoundError:
    print(f"INFO: {DRONE_IMAGE_PATH} konumunda sahte yer tutucu resim oluşturuluyor")
    try:
        img_pl = Image.new('RGB', (FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL), color = (18, 18, 18))
        draw = ImageDraw.Draw(img_pl)
        text = "Görüntü Yok"
        try:
            # Arial fontunu bulmaya çalış, yoksa varsayılanı kullan
            font_path = "arial.ttf"
            if not os.path.exists(font_path): # Eğer aynı dizinde yoksa
                # Sistem font dizinlerinde arama yap (Linux için örnek)
                # Bu kısım işletim sistemine göre farklılık gösterebilir.
                if os.name == 'posix': # Linux/macOS
                    possible_paths = [
                        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/Library/Fonts/Arial.ttf", # macOS
                    ]
                    for path in possible_paths:
                        if os.path.exists(path):
                            font_path = path
                            break
            font = ImageFont.truetype(font_path, 20)
        except IOError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), text, font=font)
        textwidth = bbox[2] - bbox[0]
        textheight = bbox[3] - bbox[1]
        x = (img_pl.width - textwidth) / 2
        y = (img_pl.height - textheight) / 2
        draw.text((x, y), text, fill=(248, 248, 242), font=font)
        img_pl.save(DRONE_IMAGE_PATH)
    except Exception as e:
        print(f"HATA: Sahte yer tutucu resim oluşturulamadı: {e}")

# Fontlar
FONTS = {
    "title": ("Roboto", 24, "bold"),
    "subtitle": ("Roboto", 16, "bold"),
    "body": ("Roboto", 14),
    "small": ("Roboto", 12),
    "button": ("Roboto", 14, "bold"),
    "button_small": ("Roboto", 12, "bold") # Daha küçük kart butonları için
}

# Commands - MODIFIED TO PREVENT NEW TERMINAL WINDOWS
COMMANDS = {
    # QGC command: Removed gnome-terminal. QGroundControl.AppImage typically runs as a GUI.
    # If QGC itself opens a terminal, that's external to this script.
    "qgc": "cd ~/PX4-Autopilot || exit 1; ./QGroundControl.AppImage",
    
    # Drone 1 command: Removed gnome-terminal, running tmux commands directly.
    "drone1": """
        cd ~/PX4-Autopilot || exit 1;
        tmux kill-session -t drone1_session 2>/dev/null;
        tmux new-session -d -s drone1_session "PX4_SYS_AUTOSTART=4002 PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 1";
        tmux kill-session -t drone1_py 2>/dev/null;
        tmux new-session -d -s drone1_py "python3 ~/Masaüstü/ucak1.py"
    """,
    # Drone 2 command: Removed gnome-terminal, running tmux commands directly.
    "drone2": """
        cd ~/PX4-Autopilot || exit 1;
        sleep 5;
        tmux kill-session -t drone2_session 2>/dev/null;
        tmux new-session -d -s drone2_session "PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE=\\"0,10,0,0,0,0\\" PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 2";
        tmux kill-session -t drone2_py 2>/dev/null;
        tmux new-session -d -s drone2_py "python3 ~/Masaüstü/ucak2.py"
    """
}
