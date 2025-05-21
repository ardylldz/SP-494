import customtkinter as ctk
import subprocess
import time
import multiprocessing.shared_memory as shm
import json
from PIL import Image, ImageDraw, ImageTk # ImageTk eklendi

# ========== YAPILANDIRMA ==========
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Sabitler
SHM_NAME = "telemetry_shared"
SHM_SIZE = 4096
TIMEOUT_THRESHOLD = 3 # saniye

# --- Resim Yolları ---
# Statik yer tutucu resim (drone durduğunda veya GIF yüklenemediğinde)
DRONE_IMAGE_PATH = "drone_feed_placeholder.png"
# Drone uçuşu için animasyonlu GIF
DRONE_GIF_PATH = "/home/arda/Masaüstü/Drone.gif" # Kullanıcının belirttiği yol

# --- Kart ve Besleme Boyutları ---
CARD_WIDTH_SMALL = 300 # Daha küçük kart genişliği
CARD_HEIGHT_SMALL = 380 # Daha küçük kart yüksekliği (içeriğe göre ayarlandı)
FEED_WIDTH_SMALL = CARD_WIDTH_SMALL - 40 # örn. 260
FEED_HEIGHT_SMALL = 150 # Daha küçük besleme yüksekliği

# Renk Teması
COLORS = {
    "primary": "#1E1E2E",       # Ana navigasyon kenar çubuğu
    "secondary": "#2A2A3A",     # QGC paneli, nav butonları için hover
    "tertiary": "#272A3A",      # QGC paneli için biraz farklı bir ton (gerekirse)
    "accent": "#4E9FEC",
    "success": "#2ECC71",
    "success_hover": "#27AE60",
    "danger": "#E74C3C",
    "danger_hover": "#C0392B",
    "warning": "#F39C12",
    "dark": "#121212",          # Ana içerik alanı arka planı
    "card_bg": "#2C3E50",
    "text_primary": "#FFFFFF",
    "text_secondary": "#B8B8B8",
    "gray": "#7F8C8D",
    "disconnected": "#5B5B5B" # Bağlantı kesildiğinde kullanılacak renk
}

# Test için, DRONE_IMAGE_PATH bulunamazsa sahte bir yer tutucu oluştur:
try:
    with Image.open(DRONE_IMAGE_PATH) as img:
        img.load() # Dosyanın okunabilir olduğundan emin ol
except FileNotFoundError:
    print(f"BİLGİ: {DRONE_IMAGE_PATH} konumunda sahte yer tutucu resim oluşturuluyor")
    try:
        # COLORS["dark"] (#121212) ile eşleşmesi için (18, 18, 18)
        img_pl = Image.new('RGB', (FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL), color = (18, 18, 18))
        draw = ImageDraw.Draw(img_pl)
        text = "Görüntü Yok"
        # Basit metin ortalama
        bbox = draw.textbbox((0,0), text, font=ImageFont.truetype("arial.ttf", 20)) # Font ekledik
        textwidth = bbox[2] - bbox[0]
        textheight = bbox[3] - bbox[1]
        x = (img_pl.width - textwidth) / 2
        y = (img_pl.height - textheight) / 2
        draw.text((x, y), text, fill=(248, 248, 242), font=ImageFont.truetype("arial.ttf", 20)) # Font ekledik
        img_pl.save(DRONE_IMAGE_PATH)
    except Exception as e:
        print(f"HATA: Sahte yer tutucu resim oluşturulamadı: {e}")
# ------------------------------------------------------------


# Fontlar
FONTS = {
    "title": ("Roboto", 24, "bold"),
    "subtitle": ("Roboto", 16, "bold"),
    "body": ("Roboto", 14),
    "small": ("Roboto", 12),
    "button": ("Roboto", 14, "bold"),
    "button_small": ("Roboto", 12, "bold") # Daha küçük kart butonları için
}

class DroneControlCenter:
    def __init__(self):
        self.app = ctk.CTk()
        self.app.title("SwarMind PX4 Drone Kontrol Merkezi")
        self.app.geometry("1280x800")
        self.app.minsize(1024, 768)

        # Durum değişkenleri
        self.last_telemetry_update_time = {1: 0.0, 2: 0.0}
        self.drone_process_commanded_active = {1: False, 2: False}
        self.is_drone_connected_via_telemetry = {1: False, 2: False}

        # Dashboard drone kartları için UI eleman referansları
        self.dash_drone1_card_ref = None
        self.dash_drone2_card_ref = None
        self.drone1_dashboard_status_light = None
        self.drone1_dashboard_status_label = None
        self.drone2_dashboard_status_light = None
        self.drone2_dashboard_status_label = None
        self.drone_image_labels = {1: None, 2: None} # Resim/GIF gösterimi için

        # GIF Animasyon özellikleri
        self.drone_gif_ctk_frames = {1: [], 2: []} # CTkImage nesnelerini sakla
        self.drone_gif_durations = {1: [], 2: []}
        self.drone_gif_current_frame_index = {1: 0, 2: 0}
        self.drone_gif_animation_job_id = {1: None, 2: None}
        self.gif_loaded_successfully = {1: False, 2: False}

        # Telemetry görünümü için UI eleman referansları
        self.drone1_telemetry_connection_label = None
        self.drone2_telemetry_connection_label = None
        self.drone1_card_ref = None # Telemetry view card
        self.drone2_card_ref = None # Telemetry view card
        self.drone1_data = {}
        self.drone2_data = {}

        self.commands = {
            "qgc": """
                gnome-terminal --title='QGroundControl' -- bash -c '
                cd ~/PX4-Autopilot || exit 1;
                ./QGroundControl.AppImage;
                exec bash'
            """,
            "drone1": """
                gnome-terminal --title='Drone1 & Aircraft1' -- bash -c '
                cd ~/PX4-Autopilot || exit 1;
                tmux kill-session -t drone1_session 2>/dev/null;
                tmux new-session -d -s drone1_session "PX4_SYS_AUTOSTART=4002 PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 1";
                tmux kill-session -t drone1_py 2>/dev/null;
                tmux new-session -d -s drone1_py "python3 ~/Masaüstü/ucak1.py";
                exec bash'
            """,
            "drone2": """
                gnome-terminal --title='Drone2 & Aircraft2' -- bash -c '
                cd ~/PX4-Autopilot || exit 1;
                sleep 5;
                tmux kill-session -t drone2_session 2>/dev/null;
                tmux new-session -d -s drone2_session "PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE=\\"0,10,0,0,0,0\\" PX4_SIM_MODEL=gz_x500 ./build/px4_sitl_default/bin/px4 -i 2";
                tmux kill-session -t drone2_py 2>/dev/null;
                tmux new-session -d -s drone2_py "python3 ~/Masaüstü/ucak2.py";
                exec bash'
            """
        }
        self._load_static_placeholder_images()
        self.setup_ui()
        self.update_telemetry()

    def _load_static_placeholder_images(self):
        """Statik yer tutucu CTkImage'ı önceden yükler."""
        self.static_placeholder_ctkimage = None
        try:
            pil_image = Image.open(DRONE_IMAGE_PATH)
            pil_image_resized = pil_image.resize((FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL), Image.Resampling.LANCZOS)
            # CTkImage yerine ImageTk.PhotoImage kullanın, çünkü CTkImage animasyon etiketlerinde sorun yaratabilir
            self.static_placeholder_ctkimage = ImageTk.PhotoImage(pil_image_resized)
        except Exception as e:
            print(f"HATA: Statik yer tutucu resim yüklenemedi '{DRONE_IMAGE_PATH}': {e}")


    def setup_ui(self):
        # ===== NAVİGASYON KENAR ÇUBUĞU (En Sol) =====
        self.nav_sidebar = ctk.CTkFrame(self.app, width=220, corner_radius=0, fg_color=COLORS["primary"])
        self.nav_sidebar.pack(side="left", fill="y")

        self.logo_frame = ctk.CTkFrame(self.nav_sidebar, fg_color="transparent")
        self.logo_frame.pack(pady=(25, 25), padx=20, fill="x")
        ctk.CTkLabel(self.logo_frame, text="SwarMind", font=FONTS["title"], text_color=COLORS["accent"]
                     ).pack(side="left", padx=0)
        ctk.CTkLabel(self.logo_frame, text="Kontrol", font=("Roboto", 24, "normal"), text_color=COLORS["text_primary"]
                     ).pack(side="left", padx=5)

        self.create_nav_buttons(self.nav_sidebar)
        self.create_system_controls(self.nav_sidebar)

        # ===== QGC/ARAÇLAR YAN PANELİ (Orta Sol) =====
        self.qgc_tools_panel = ctk.CTkFrame(self.app, width=180, corner_radius=0, fg_color=COLORS["secondary"])
        self.qgc_tools_panel.pack(side="left", fill="y", padx=(1,0))
        self._create_qgc_tools_panel_content(self.qgc_tools_panel)


        # ===== ANA İÇERİK ALANI (Sağ) =====
        self.main_content_area = ctk.CTkFrame(self.app, corner_radius=0, fg_color=COLORS["dark"])
        self.main_content_area.pack(side="left", fill="both", expand=True)

        self.dashboard_frame = self.create_dashboard(self.main_content_area)
        self.telemetry_frame = self.create_telemetry_display(self.main_content_area)

        self.show_dashboard()


    def create_nav_buttons(self, parent_sidebar):
        nav_buttons_frame = ctk.CTkFrame(parent_sidebar, fg_color="transparent")
        nav_buttons_frame.pack(fill="x", pady=(20,0))
        nav_buttons = [
            {"text": "Dashboard", "command": self.show_dashboard},
            {"text": "Telemetri", "command": self.show_telemetry},
            {"text": "Ayarlar", "command": lambda: print("Ayarlar tıklandı")}
        ]
        for btn_info in nav_buttons:
            ctk.CTkButton(
                nav_buttons_frame,
                text=btn_info['text'],
                command=btn_info["command"],
                height=40,
                font=FONTS["button"],
                fg_color="transparent",
                hover_color=COLORS["secondary"],
                text_color=COLORS["text_primary"],
                corner_radius=8,
                anchor="w"
            ).pack(fill="x", padx=15, pady=6)


    def create_system_controls(self, parent_sidebar):
        ctk.CTkFrame(parent_sidebar, height=1, fg_color=COLORS["secondary"]).pack(fill="x", padx=10, pady=(25,0))
        ctk.CTkLabel(
            parent_sidebar, text="Sistem Kontrolleri", font=FONTS["subtitle"], text_color=COLORS["text_secondary"]
        ).pack(pady=(15, 10), padx=15, anchor="w")
        controls_frame = ctk.CTkFrame(parent_sidebar, fg_color="transparent")
        controls_frame.pack(fill="x", pady=(0,10))
        controls = [
            {"text": "Tümünü Başlat", "command": self.start_all, "color": COLORS["success"], "hover": COLORS["success_hover"]},
            {"text": "Tümünü Durdur", "command": self.stop_all, "color": COLORS["danger"], "hover": COLORS["danger_hover"]},
            {"text": "Acil Durdurma", "command": self.emergency_stop, "color": COLORS["danger"], "hover": COLORS["danger_hover"]}
        ]
        for ctrl in controls:
            ctk.CTkButton(
                controls_frame, text=ctrl["text"], command=ctrl["command"], height=38, font=FONTS["button_small"],
                fg_color=ctrl["color"], hover_color=ctrl["hover"], corner_radius=8
            ).pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(
            parent_sidebar, text="Uygulamadan Çık", command=self.app.quit, height=38, font=FONTS["button_small"],
            fg_color=COLORS["dark"], hover_color=COLORS["danger_hover"], border_width=1, border_color=COLORS["secondary"],
            corner_radius=8
        ).pack(side="bottom", fill="x", padx=15, pady=(10,15))

    def _create_qgc_tools_panel_content(self, parent_panel):
        ctk.CTkLabel(parent_panel, text="Araçlar", font=FONTS["subtitle"],
                     text_color=COLORS["text_primary"]).pack(pady=(25,10), padx=10)
        ctk.CTkButton(parent_panel, text="QGC Başlat",
                      command=self.start_qgc,
                      fg_color=COLORS["accent"],
                      hover_color="#3A7BBF",
                      font=FONTS["button"],
                      height=40
                      ).pack(fill="x", padx=15, pady=10)


    def _create_dashboard_status_widgets(self, parent, initial_text):
        light = ctk.CTkLabel(parent, text="●", font=("Arial", 22), text_color=COLORS["gray"])
        light.pack(side="left", padx=(0, 8))
        label = ctk.CTkLabel(parent, text=initial_text, font=FONTS["small"], text_color=COLORS["text_secondary"])
        label.pack(side="left")
        return light, label

    def create_control_button(self, parent, text, command, color, hover_color, height=35, font_choice=FONTS["button_small"]):
        btn = ctk.CTkButton(
            parent, text=text, command=command, height=height,
            font=font_choice, fg_color=color, hover_color=hover_color, corner_radius=6
        )
        btn.pack(fill="x", padx=10, pady=4)
        return btn

    def create_dashboard(self, parent_frame):
        frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

        header_content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_content_frame.pack(fill="x", padx=25, pady=(25, 15))
        ctk.CTkLabel(header_content_frame, text="Drone Kontrol Paneli", font=FONTS["title"],
                     text_color=COLORS["text_primary"]).pack()

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=15, pady=10)
        cards_frame.grid_columnconfigure((0, 1), weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)

        self.create_drone_card(cards_frame, "DRONE 1", drone_id=1, column_idx=0)
        self.create_drone_card(cards_frame, "DRONE 2", drone_id=2, column_idx=1)
        return frame

    def create_drone_card(self, parent, title_text, drone_id, column_idx):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["card_bg"], corner_radius=12,
            border_width=2, border_color=COLORS["gray"],
            width=CARD_WIDTH_SMALL, height=CARD_HEIGHT_SMALL
        )
        card.grid(row=0, column=column_idx, padx=12, pady=12, sticky="nsew")
        card.grid_propagate(False)

        if drone_id == 1: self.dash_drone1_card_ref = card
        else: self.dash_drone2_card_ref = card

        ctk.CTkLabel(card, text=title_text, font=FONTS["subtitle"], text_color=COLORS["accent"]
                     ).pack(pady=(12, 8))

        feed_frame = ctk.CTkFrame(
            card, width=FEED_WIDTH_SMALL, height=FEED_HEIGHT_SMALL,
            fg_color=COLORS["dark"], corner_radius=8
        )
        feed_frame.pack(pady=(5, 10), padx=10)
        feed_frame.pack_propagate(False)

        image_label = ctk.CTkLabel(feed_frame, text="")
        image_label.pack(expand=True, fill="both")
        self.drone_image_labels[drone_id] = image_label

        if self.static_placeholder_ctkimage:
            # CTkImage.configure ile ImageTk.PhotoImage direkt olarak atanır
            image_label.configure(image=self.static_placeholder_ctkimage, text="")
        else:
            image_label.configure(text="Yer Tutucu Yok", font=FONTS["small"], text_color=COLORS["warning"])


        status_display_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_display_frame.pack(pady=(8, 8))
        if drone_id == 1:
            self.drone1_dashboard_status_light, self.drone1_dashboard_status_label = \
                self._create_dashboard_status_widgets(status_display_frame, "PASİF")
        else:
            self.drone2_dashboard_status_light, self.drone2_dashboard_status_label = \
                self._create_dashboard_status_widgets(status_display_frame, "PASİF")

        buttons_control_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_control_frame.pack(pady=(8, 12), padx=15, fill="x")
        start_cmd = self.start_drone1 if drone_id == 1 else self.start_drone2
        stop_cmd = self.stop_drone1 if drone_id == 1 else self.stop_drone2
        self.create_control_button(buttons_control_frame, f"Drone {drone_id} Başlat", start_cmd,
                                   COLORS["success"], COLORS["success_hover"])
        self.create_control_button(buttons_control_frame, f"Drone {drone_id} Durdur", stop_cmd,
                                   COLORS["danger"], COLORS["danger_hover"])
        return card

    def _load_gif_frames(self, drone_id, gif_path):
        try:
            pil_gif = Image.open(gif_path)
            self.drone_gif_ctk_frames[drone_id] = []
            self.drone_gif_durations[drone_id] = []
            for i in range(pil_gif.n_frames):
                pil_gif.seek(i)
                pil_frame_copy = pil_gif.copy().convert("RGBA")
                pil_frame_resized = pil_frame_copy.resize((FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL), Image.Resampling.LANCZOS)
                # CTkImage yerine ImageTk.PhotoImage kullanın
                self.drone_gif_ctk_frames[drone_id].append(ImageTk.PhotoImage(pil_frame_resized))
                self.drone_gif_durations[drone_id].append(pil_gif.info.get('duration', 100))
            self.gif_loaded_successfully[drone_id] = True
            print(f"BİLGİ: Drone {drone_id} için GIF başarıyla yüklendi ({pil_gif.n_frames} kare).")
        except FileNotFoundError:
            print(f"HATA: Drone {drone_id} için GIF dosyası bulunamadı: {gif_path}")
            self.gif_loaded_successfully[drone_id] = False
        except Exception as e:
            print(f"HATA: Drone {drone_id} için GIF yüklenemedi: {e}")
            self.gif_loaded_successfully[drone_id] = False


    def _animate_gif(self, drone_id):
        if not self.drone_process_commanded_active[drone_id] or not self.gif_loaded_successfully[drone_id]:
            if self.drone_gif_animation_job_id[drone_id]:
                self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                self.drone_gif_animation_job_id[drone_id] = None
            # Durduğunda statik yer tutucuyu göster
            image_label_widget = self.drone_image_labels.get(drone_id)
            if image_label_widget and self.static_placeholder_ctkimage:
                image_label_widget.configure(image=self.static_placeholder_ctkimage, text="")
            return

        current_frames = self.drone_gif_ctk_frames[drone_id]
        if not current_frames: # GIF yüklenememişse animasyonu durdur
            return

        idx = self.drone_gif_current_frame_index[drone_id]
        
        image_label_widget = self.drone_image_labels.get(drone_id)
        if image_label_widget:
            if idx < len(current_frames):
                image_label_widget.configure(image=current_frames[idx], text="")
            else: # Döngüye başa dön
                self.drone_gif_current_frame_index[drone_id] = 0
                if current_frames:
                    image_label_widget.configure(image=current_frames[0], text="")

        self.drone_gif_current_frame_index[drone_id] = (idx + 1) % len(current_frames)
            
        duration = self.drone_gif_durations[drone_id][self.drone_gif_current_frame_index[drone_id]] if self.drone_gif_durations[drone_id] else 100
        self.drone_gif_animation_job_id[drone_id] = self.app.after(duration, lambda: self._animate_gif(drone_id))


    def _populate_telemetry_card_content(self, card_widget, title_text, drone_id):
        title_frame = ctk.CTkFrame(card_widget, fg_color="transparent")
        title_frame.pack(pady=(15, 10), fill="x", padx=20)
        ctk.CTkLabel(title_frame, text=title_text, font=FONTS["subtitle"], text_color=COLORS["accent"]).pack(side="left")
        status_label = ctk.CTkLabel(title_frame, text="Durum: BİLİNMİYOR", font=FONTS["small"], text_color=COLORS["gray"])
        status_label.pack(side="right", padx=(0, 5))
        
        data_rows_frame = ctk.CTkFrame(card_widget, fg_color="transparent")
        data_rows_frame.pack(fill="both", expand=True, pady=(5, 15), padx=20)
        telemetry_fields = {
            "latitude": "Enlem", "longitude": "Boylam", "altitude": "Yükseklik",
            "speed": "Hız", "battery": "Batarya", "mode": "Uçuş Modu",
            "pitch": "Pitch Açısı", "roll": "Roll Açısı", "yaw": "Yaw Açısı"
        }
        current_data_dict = {}
        for key, display_name in telemetry_fields.items():
            current_data_dict[key] = self.create_telemetry_row(data_rows_frame, display_name, "-")
        if drone_id == 1:
            self.drone1_telemetry_connection_label = status_label
            self.drone1_data = current_data_dict
        else:
            self.drone2_telemetry_connection_label = status_label
            self.drone2_data = current_data_dict


    def create_telemetry_display(self, parent_frame):
        frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(25, 15))
        ctk.CTkLabel(header, text="Canlı Drone Telemetrisi", font=FONTS["title"], text_color=COLORS["text_primary"]).pack(side="left")
        
        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=15, pady=10)
        cards_frame.grid_columnconfigure((0,1), weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)

        self.drone1_card_ref = ctk.CTkFrame(
            cards_frame, width=400, height=420, corner_radius=12, fg_color=COLORS["card_bg"],
            border_color=COLORS["gray"], border_width=2
        )
        self.drone1_card_ref.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.drone1_card_ref.grid_propagate(False)
        self._populate_telemetry_card_content(self.drone1_card_ref, "Drone 1 Telemetri", drone_id=1)

        self.drone2_card_ref = ctk.CTkFrame(
            cards_frame, width=400, height=420, corner_radius=12, fg_color=COLORS["card_bg"],
            border_color=COLORS["gray"], border_width=2
        )
        self.drone2_card_ref.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.drone2_card_ref.grid_propagate(False)
        self._populate_telemetry_card_content(self.drone2_card_ref, "Drone 2 Telemetri", drone_id=2)
        return frame

    def create_telemetry_row(self, parent, label, value):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row_frame.pack(fill="x", padx=5, pady=3)
        ctk.CTkLabel(
            row_frame, text=f"{label}:", font=FONTS["body"], text_color=COLORS["text_secondary"],
            width=130, anchor="w"
        ).pack(side="left", padx=(0,8))
        value_label = ctk.CTkLabel(row_frame, text=value, font=FONTS["body"], text_color=COLORS["text_primary"], anchor="w")
        value_label.pack(side="left", expand=True, fill="x")
        return value_label

    def show_dashboard(self):
        self.telemetry_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)

    def show_telemetry(self):
        self.dashboard_frame.pack_forget()
        self.telemetry_frame.pack(fill="both", expand=True)

    def handle_drone_process_command(self, drone_id, start_process):
        self.drone_process_commanded_active[drone_id] = start_process
        
        if not start_process:
            # Durdurulursa bağlantı durumunu sıfırla
            self.is_drone_connected_via_telemetry[drone_id] = False
        
        self.last_telemetry_update_time[drone_id] = 0.0 # Yeni bir timeout döngüsü başlatmak için sıfırla

        if start_process:
            print(f"Drone {drone_id} işlemleri başlatılmaya çalışılıyor...")
            command_key = "drone1" if drone_id == 1 else "drone2"
            subprocess.Popen(self.commands[command_key], shell=True, text=True)

            if not self.drone_gif_ctk_frames[drone_id] or not self.gif_loaded_successfully[drone_id]:
                self._load_gif_frames(drone_id, DRONE_GIF_PATH)
            
            if self.gif_loaded_successfully[drone_id]:
                self.drone_gif_current_frame_index[drone_id] = 0
                if self.drone_gif_animation_job_id[drone_id]:
                    self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                self._animate_gif(drone_id)
            else:
                image_label_widget = self.drone_image_labels.get(drone_id)
                if image_label_widget:
                    if self.static_placeholder_ctkimage:
                        image_label_widget.configure(image=self.static_placeholder_ctkimage, text="")
                    else:
                        image_label_widget.configure(text="Görüntü Y/A", image=None)


        else: # İşlemi durdur
            print(f"Drone {drone_id} işlemleri durdurulmaya çalışılıyor...")
            # Tmux oturumlarını ve ilgili Python scriptlerini durdurma komutları
            if drone_id == 1:
                subprocess.call("tmux kill-session -t drone1_session 2>/dev/null", shell=True)
                subprocess.call("tmux kill-session -t drone1_py 2>/dev/null", shell=True)
            else:
                subprocess.call("tmux kill-session -t drone2_session 2>/dev/null", shell=True)
                subprocess.call("tmux kill-session -t drone2_py 2>/dev/null", shell=True)

            if self.drone_gif_animation_job_id[drone_id]:
                self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                self.drone_gif_animation_job_id[drone_id] = None
            
            # Animasyon durunca statik yer tutucuyu göster
            image_label_widget = self.drone_image_labels.get(drone_id)
            if image_label_widget:
                if self.static_placeholder_ctkimage:
                    image_label_widget.configure(image=self.static_placeholder_ctkimage, text="")
                else:
                    image_label_widget.configure(text="Görüntü Durdu", image=None)

        self._update_telemetry_card_visuals(drone_id)


    def start_drone1(self): self.handle_drone_process_command(1, True)
    def stop_drone1(self): self.handle_drone_process_command(1, False)
    def start_drone2(self): self.handle_drone_process_command(2, True)
    def stop_drone2(self): self.handle_drone_process_command(2, False)

    def start_qgc(self):
        print("QGroundControl başlatılıyor...")
        subprocess.Popen(self.commands["qgc"], shell=True, text=True)

    def start_all(self):
        print("Tüm sistemler başlatılıyor...")
        self.start_drone1()
        self.app.after(2000, self.start_drone2) # Drone 2'yi biraz gecikmeli başlat
        self.app.after(7000, self.start_qgc) # QGC'yi daha da gecikmeli başlat

    def stop_all(self):
        print("Tüm drone sistemleri durduruluyor...")
        self.stop_drone1()
        self.stop_drone2()
        # QGC'yi de durdurmak isterseniz bu satırı etkinleştirin:
        # subprocess.call("pkill QGroundControl", shell=True)

    def emergency_stop(self):
        print("ACİL DURDURMA AKTİF!")
        self.stop_all()
        # Ek acil durum işlemleri buraya eklenebilir

    def read_shared_memory(self):
        try:
            # Paylaşımlı belleğe bağlan
            telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
            raw_bytes = bytes(telemetry_shm.buf[:])
            
            # Null karakteri bul ve ondan öncesini al
            try:
                null_index = raw_bytes.index(b'\x00')
                decoded_str = raw_bytes[:null_index].decode('utf-8', errors='ignore')
            except ValueError: # Null karakter yoksa tüm belleği kullan
                decoded_str = raw_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
            
            telemetry_shm.close()
            # JSON'ı parse et. Eğer boş bir stringse None dön.
            return json.loads(decoded_str) if decoded_str.strip() else {}
        except FileNotFoundError:
            # print(f"Paylaşımlı bellek '{SHM_NAME}' bulunamadı. Telemetry script'lerinin çalıştığından emin olun.")
            return None
        except json.JSONDecodeError as e:
            # print(f"Paylaşımlı bellek JSON decode hatası: {e} - Raw: '{decoded_str}'")
            return None
        except Exception as e:
            # print(f"Paylaşımlı bellek okunurken beklenmeyen hata: {e}")
            return None


    def update_telemetry_data_labels(self, card_data_labels, telemetry):
        if telemetry and card_data_labels:
            # Telemetri verilerini güncelle
            lat_text = f"{telemetry.get('latitude', 0.0):.6f}" if isinstance(telemetry.get('latitude'), (float, int)) else "-"
            lon_text = f"{telemetry.get('longitude', 0.0):.6f}" if isinstance(telemetry.get('longitude'), (float, int)) else "-"
            alt_raw = telemetry.get('absolute_altitude', telemetry.get('altitude', "-")) # absolute_altitude_m yerine absolute_altitude
            alt_text = f"{alt_raw:.2f} m" if isinstance(alt_raw, (float, int)) else f"{alt_raw} m"

            card_data_labels.get("latitude", ctk.CTkLabel(None)).configure(text=lat_text)
            card_data_labels.get("longitude", ctk.CTkLabel(None)).configure(text=lon_text)
            card_data_labels.get("altitude", ctk.CTkLabel(None)).configure(text=alt_text)
            
            speed_val = telemetry.get('speed', '-') # ground_speed_m_s yerine speed
            speed_text = f"{speed_val:.2f} m/s" if isinstance(speed_val, (float, int)) else f"{speed_val} m/s"
            card_data_labels.get("speed", ctk.CTkLabel(None)).configure(text=speed_text)
            
            battery_val = telemetry.get('battery_percent', None) # battery_remaining yerine battery_percent
            battery_text = "-%"
            if isinstance(battery_val, (float, int)) and battery_val is not None:
                battery_text = f"{battery_val:.0f}%" # Zaten 0-100 arası geliyor
            elif battery_val is not None and str(battery_val).replace('.', '', 1).isdigit():
                battery_text = f"{float(battery_val):.0f}%"
            elif battery_val is not None:
                battery_text = str(battery_val)

            card_data_labels.get("battery", ctk.CTkLabel(None)).configure(text=battery_text)

            card_data_labels.get("mode", ctk.CTkLabel(None)).configure(text=f"{telemetry.get('flight_mode', '-')}")
            
            pitch_val = telemetry.get('pitch', '-') # pitch_deg yerine pitch
            pitch_text = f"{pitch_val:.2f}°" if isinstance(pitch_val, (float, int)) else f"{pitch_val}°"
            card_data_labels.get("pitch", ctk.CTkLabel(None)).configure(text=pitch_text)

            roll_val = telemetry.get('roll', '-') # roll_deg yerine roll
            roll_text = f"{roll_val:.2f}°" if isinstance(roll_val, (float, int)) else f"{roll_val}°"
            card_data_labels.get("roll", ctk.CTkLabel(None)).configure(text=roll_text)

            yaw_val = telemetry.get('yaw', '-') # yaw_deg yerine yaw
            yaw_text = f"{yaw_val:.2f}°" if isinstance(yaw_val, (float, int)) else f"{yaw_val}°"
            card_data_labels.get("yaw", ctk.CTkLabel(None)).configure(text=yaw_text)


    def _clear_telemetry_data_labels(self, card_data_labels):
        if card_data_labels:
            default_texts = {
                "latitude": "-", "longitude": "-", "altitude": "- m", "speed": "- m/s",
                "battery": "-%", "mode": "-", "pitch": "-°", "roll": "-°", "yaw": "-°"
            }
            for key, label_widget in card_data_labels.items():
                if label_widget and isinstance(label_widget, ctk.CTkLabel):
                    label_widget.configure(text=default_texts.get(key, "-"))


    def _update_telemetry_card_visuals(self, drone_id):
        dash_light, dash_label = (self.drone1_dashboard_status_light, self.drone1_dashboard_status_label) if drone_id == 1 else \
                                 (self.drone2_dashboard_status_light, self.drone2_dashboard_status_label)
        
        telemetry_view_card_widget = self.drone1_card_ref if drone_id == 1 else self.drone2_card_ref
        telemetry_conn_label = self.drone1_telemetry_connection_label if drone_id == 1 else self.drone2_telemetry_connection_label
        
        dashboard_card_widget = self.dash_drone1_card_ref if drone_id == 1 else self.dash_drone2_card_ref
        current_data_labels = self.drone1_data if drone_id == 1 else self.drone2_data

        # Dashboard kartı için varsayılanlar (PASİF durumu)
        dash_status_text = "PASİF"
        dash_light_color = COLORS["gray"]
        dash_text_color = COLORS["text_secondary"]
        border_color = COLORS["gray"] # Başlangıçta gri sınır

        if self.drone_process_commanded_active[drone_id]:
            if self.is_drone_connected_via_telemetry[drone_id]:
                dash_status_text = "AKTİF"
                dash_light_color = COLORS["success"]
                dash_text_color = COLORS["success"]
                border_color = COLORS["success"]
            else: # Veri bekleniyor veya zaman aşımına uğradı
                dash_status_text = "BAĞLANTI BEKLENİYOR" # Daha açıklayıcı
                dash_light_color = COLORS["warning"]
                dash_text_color = COLORS["warning"]
                border_color = COLORS["warning"]
        else: # Süreç aktif değilse bağlantı kesik
            dash_status_text = "BAĞLANTI KESİK"
            dash_light_color = COLORS["disconnected"]
            dash_text_color = COLORS["text_secondary"]
            border_color = COLORS["gray"]
            
        if dash_light: dash_light.configure(text_color=dash_light_color)
        if dash_label: dash_label.configure(text=dash_status_text, text_color=dash_text_color)
        if dashboard_card_widget: dashboard_card_widget.configure(border_color=border_color)
        
        # Telemetri görünümü kartı için
        if telemetry_view_card_widget: telemetry_view_card_widget.configure(border_color=border_color)
        
        if telemetry_conn_label:
            conn_text = "Durum: BAĞLANTI KESİK" # Process aktif değilse
            conn_color = COLORS["text_secondary"]
            if self.drone_process_commanded_active[drone_id]:
                conn_text = "Durum: BAĞLI" if self.is_drone_connected_via_telemetry[drone_id] else "Durum: TELEMETRİ YOK"
                conn_color = COLORS["success"] if self.is_drone_connected_via_telemetry[drone_id] else COLORS["warning"]
            telemetry_conn_label.configure(text=conn_text, text_color=conn_color)

        # Eğer süreç aktif değilse veya bağlı değilse telemetri verilerini temizle
        if not self.drone_process_commanded_active[drone_id] or \
           (self.drone_process_commanded_active[drone_id] and not self.is_drone_connected_via_telemetry[drone_id]):
            self._clear_telemetry_data_labels(current_data_labels)


    def update_telemetry(self):
        shared_data = self.read_shared_memory()
        now = time.time()
        
        # Bu döngüde hangi drone'lardan veri geldiğini takip et
        drone_data_received_this_cycle = {1: False, 2: False}

        if shared_data:
            # Paylaşımlı bellekteki her drone'un verisini işle
            for drone_id_str, telemetry_content in shared_data.items():
                try:
                    drone_id = int(drone_id_str)
                    if drone_id in [1, 2]:
                        target_data_dict = self.drone1_data if drone_id == 1 else self.drone2_data
                        self.update_telemetry_data_labels(target_data_dict, telemetry_content)
                        self.last_telemetry_update_time[drone_id] = now
                        if self.drone_process_commanded_active[drone_id]:
                            self.is_drone_connected_via_telemetry[drone_id] = True
                        drone_data_received_this_cycle[drone_id] = True
                except ValueError:
                    print(f"Paylaşımlı bellekte geçersiz drone_id formatı: {drone_id_str}")

        # Her drone için bağlantı durumunu kontrol et
        for did in [1, 2]:
            if self.drone_process_commanded_active[did]:
                if not drone_data_received_this_cycle[did]: # Bu döngüde veri gelmediyse
                    if self.last_telemetry_update_time[did] > 0 and \
                       (now - self.last_telemetry_update_time[did] > TIMEOUT_THRESHOLD):
                        if self.is_drone_connected_via_telemetry[did]: # Daha önce bağlıydıysa zaman aşımı uyarısı
                            print(f"Drone {did} telemetrisi zaman aşımına uğradı.")
                        self.is_drone_connected_via_telemetry[did] = False
                    elif self.last_telemetry_update_time[did] == 0.0: # İlk defa başlatılıp henüz hiç veri gelmediyse
                        self.is_drone_connected_via_telemetry[did] = False # Bağlı değil olarak işaretle
            else: # Süreç aktif değilse, bağlantı da kesik
                self.is_drone_connected_via_telemetry[did] = False

            self._update_telemetry_card_visuals(did)
            
        self.app.after(1000, self.update_telemetry)

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    from PIL import ImageFont # Font için Pillow'dan ImageFont'ı ekledik
    try:
        # Mevcut paylaşımlı bellek segmentini bulmaya çalış
        # Eğer bulunamazsa, telemetry script'lerinin henüz başlatılmadığı anlamına gelir.
        existing_shm = shm.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
        existing_shm.close()
        print(f"BİLGİ: Paylaşımlı bellek '{SHM_NAME}' bulundu.")
    except FileNotFoundError:
        print(f"BİLGİ: Paylaşımlı bellek '{SHM_NAME}' bulunamadı. Telemetry script'inin (yazıcı) çalıştığından ve oluşturduğundan emin olun.")
    
    app_instance = DroneControlCenter()
    app_instance.run()
