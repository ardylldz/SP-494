#!/usr/bin/env python3

import customtkinter as ctk
import subprocess
import time
import multiprocessing.shared_memory as shm
import json
from PIL import Image, ImageTk # ImageTk is included
from config import (
    SHM_NAME, SHM_SIZE, TIMEOUT_THRESHOLD,
    DRONE_IMAGE_PATH, DRONE_GIF_PATH,
    CARD_WIDTH_SMALL, CARD_HEIGHT_SMALL, FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL,
    COLORS, COLORS_DARK, COLORS_LIGHT, FONTS, COMMANDS # COLORS_DARK ve COLORS_LIGHT eklendi
)

class DroneControlCenter:
    def __init__(self):
        self.app = ctk.CTk()
        self.app.title("SwarMind PX4 Drone Control Center")
        self.app.geometry("1280x800")
        self.app.minsize(1024, 768)

        self.current_theme = "dark" # Başlangıç teması
        self.colors = COLORS_DARK # Başlangıçta koyu tema renklerini kullan

        # Configure grid weights for responsive layout
        self.app.grid_columnconfigure(0, weight=0) # Nav sidebar fixed width
        # self.app.grid_columnconfigure(1, weight=0) # QGC tools panel REMOVED
        self.app.grid_columnconfigure(1, weight=1) # Main content area expands (was column 2)
        self.app.grid_rowconfigure(0, weight=1) # Main row expands

        # State variables
        self.last_telemetry_update_time = {1: 0.0, 2: 0.0}
        self.drone_process_commanded_active = {1: False, 2: False}
        self.is_drone_connected_via_telemetry = {1: False, 2: False}

        # UI element references for dashboard drone cards
        self.dash_drone1_card_ref = None
        self.dash_drone2_card_ref = None
        self.drone1_dashboard_status_light = None
        self.drone1_dashboard_status_label = None
        self.drone2_dashboard_status_light = None
        self.drone2_dashboard_status_label = None
        self.drone_image_labels = {1: None, 2: None} # For image/GIF display

        # GIF Animation properties
        self.drone_gif_ctk_frames = {1: [], 2: []} # Store CTkImage objects
        self.drone_gif_durations = {1: [], 2: []}
        self.drone_gif_current_frame_index = {1: 0, 2: 0}
        self.drone_gif_animation_job_id = {1: None, 2: None}
        self.gif_loaded_successfully = {1: False, 2: False}

        # UI element references for telemetry view
        self.drone1_telemetry_connection_label = None
        self.drone2_telemetry_connection_label = None
        self.drone1_card_ref = None # Telemetry view card
        self.drone2_card_ref = None # Telemetry view card
        self.drone1_data = {} # Labels for drone 1 telemetry values
        self.drone2_data = {} # Labels for drone 2 telemetry values

        self.static_placeholder_ctkimage = None # Initialize as None
        
        self.setup_ui()
        self.update_telemetry()

    def _load_static_placeholder_images(self, target_width, target_height):
        """Pre-loads the static placeholder CTkImage with dynamic sizing."""
        try:
            pil_image = Image.open(DRONE_IMAGE_PATH)
            pil_image_resized = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            self.static_placeholder_ctkimage = ImageTk.PhotoImage(pil_image_resized)
            print(f"INFO: Static placeholder image loaded and resized to {target_width}x{target_height}.")
        except Exception as e:
            print(f"ERROR: Could not load static placeholder image '{DRONE_IMAGE_PATH}': {e}")
            self.static_placeholder_ctkimage = None

    def setup_ui(self):
        # ===== NAVIGATION SIDEBAR (Far Left) =====
        self.nav_sidebar = ctk.CTkFrame(self.app, width=220, corner_radius=0, fg_color=self.colors["primary"])
        self.nav_sidebar.grid(row=0, column=0, sticky="nswe")
        self.nav_sidebar.grid_propagate(False) # Prevent frame from shrinking to content

        self.logo_frame = ctk.CTkFrame(self.nav_sidebar, fg_color="transparent")
        self.logo_frame.pack(pady=(25, 25), padx=20, fill="x")
        ctk.CTkLabel(self.logo_frame, text="SwarMind", font=FONTS["title"], text_color=self.colors["accent"]
                     ).pack(side="left", padx=0)
        ctk.CTkLabel(self.logo_frame, text="Control", font=("Roboto", 24, "normal"), text_color=self.colors["text_primary"]
                     ).pack(side="left", padx=5)

        self.create_nav_buttons(self.nav_sidebar)
        self.create_system_controls(self.nav_sidebar)

        # ===== QGC/TOOLS SIDE PANEL REMOVED =====
        # self.qgc_tools_panel = ctk.CTkFrame(self.app, width=180, corner_radius=0, fg_color=self.colors["secondary"])
        # self.qgc_tools_panel.grid(row=0, column=1, sticky="nswe", padx=(1,0))
        # self.qgc_tools_panel.grid_propagate(False) 
        # self._create_qgc_tools_panel_content(self.qgc_tools_panel) # Method will be removed

        # ===== MAIN CONTENT AREA (Right) =====
        self.main_content_area = ctk.CTkFrame(self.app, corner_radius=0, fg_color=self.colors["dark"])
        self.main_content_area.grid(row=0, column=1, sticky="nswe") # Column changed from 2 to 1
        self.main_content_area.grid_propagate(False)

        self.dashboard_frame = self.create_dashboard(self.main_content_area)
        self.telemetry_frame = self.create_telemetry_display(self.main_content_area)

        self.show_dashboard()
        self._load_static_placeholder_images(FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL)

    def create_nav_buttons(self, parent_sidebar):
        nav_buttons_frame = ctk.CTkFrame(parent_sidebar, fg_color="transparent")
        nav_buttons_frame.pack(fill="x", pady=(20,0))
        nav_buttons = [
            {"text": "Dashboard", "command": self.show_dashboard},
            {"text": "Telemetry", "command": self.show_telemetry},
            {"text": "Settings", "command": lambda: print("Settings clicked")}
        ]
        self.nav_button_refs = [] 
        for btn_info in nav_buttons:
            btn = ctk.CTkButton(
                nav_buttons_frame,
                text=btn_info['text'],
                command=btn_info["command"],
                height=40,
                font=FONTS["button"],
                fg_color="transparent",
                hover_color=self.colors["secondary"],
                text_color=self.colors["text_primary"],
                corner_radius=8,
                anchor="w"
            )
            btn.pack(fill="x", padx=15, pady=6)
            self.nav_button_refs.append(btn)

    def create_system_controls(self, parent_sidebar):
        ctk.CTkFrame(parent_sidebar, height=1, fg_color=self.colors["secondary"]).pack(fill="x", padx=10, pady=(25,0))
        self.system_controls_title_label = ctk.CTkLabel( # Storing ref for color update
            parent_sidebar, text="System Controls", font=FONTS["subtitle"], text_color=self.colors["text_secondary"]
        )
        self.system_controls_title_label.pack(pady=(15, 10), padx=15, anchor="w")
        
        controls_frame = ctk.CTkFrame(parent_sidebar, fg_color="transparent")
        controls_frame.pack(fill="x", pady=(0,10))
        
        self.control_buttons_refs = [] 
        controls_data = [ # Changed variable name for clarity
            {"text": "Start All", "command": self.start_all, "color_key": "success", "hover_key": "success_hover"},
            {"text": "Stop All", "command": self.stop_all, "color_key": "danger", "hover_key": "danger_hover"},
            {"text": "Emergency Stop", "command": self.emergency_stop, "color_key": "danger", "hover_key": "danger_hover"}
        ]
        for ctrl_data in controls_data: # Iterate using new variable name
            btn = ctk.CTkButton(
                controls_frame, text=ctrl_data["text"], command=ctrl_data["command"], height=38, font=FONTS["button_small"],
                fg_color=self.colors[ctrl_data["color_key"]], hover_color=self.colors[ctrl_data["hover_key"]], corner_radius=8
            )
            btn.pack(fill="x", padx=15, pady=5)
            self.control_buttons_refs.append(btn)
        
        # Tema değiştirme düğmesi eklendi
        self.theme_button = ctk.CTkButton(
            parent_sidebar, 
            text="Change Theme", 
            command=self.toggle_theme, 
            height=38, 
            font=FONTS["button_small"],
            fg_color=self.colors["secondary"], 
            hover_color=self.colors["tertiary"],
            text_color=self.colors["accent"], # MODIFIED: Colored text
            corner_radius=8
        )
        self.theme_button.pack(fill="x", padx=15, pady=(10, 5))

        # Launch QGC Button (Moved here)
        self.launch_qgc_button = ctk.CTkButton(
            parent_sidebar,
            text="Launch QGC",
            command=self.start_qgc,
            height=38,
            font=FONTS["button_small"], # Match style of other buttons in this section
            fg_color=self.colors["secondary"], # Match theme button's fg_color for visual consistency
            hover_color=self.colors["tertiary"], # Match theme button's hover
            text_color=self.colors["accent"], # MODIFIED: Colored text like theme button
            corner_radius=8
        )
        self.launch_qgc_button.pack(fill="x", padx=15, pady=5) # Placed after theme button

        self.exit_button = ctk.CTkButton(
            parent_sidebar, text="Exit Application", command=self.app.quit, height=38, font=FONTS["button_small"],
            fg_color=self.colors["dark"], hover_color=self.colors["danger_hover"], border_width=1, border_color=self.colors["secondary"],
            corner_radius=8
        )
        self.exit_button.pack(side="bottom", fill="x", padx=15, pady=(10,15))

    # def _create_qgc_tools_panel_content IS REMOVED

    def _create_dashboard_status_widgets(self, parent, initial_text):
        light = ctk.CTkLabel(parent, text="●", font=("Arial", 22), text_color=self.colors["gray"])
        light.pack(side="left", padx=(0, 8))
        label = ctk.CTkLabel(parent, text=initial_text, font=FONTS["small"], text_color=self.colors["text_secondary"])
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
        self.dashboard_header_label = ctk.CTkLabel(header_content_frame, text="Drone Control Panel", font=FONTS["title"],
                                                   text_color=self.colors["text_primary"])
        self.dashboard_header_label.pack()

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=15, pady=10)
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_rowconfigure(0, weight=1) 

        self.create_drone_card(cards_frame, "DRONE 1", drone_id=1, column_idx=0)
        self.create_drone_card(cards_frame, "DRONE 2", drone_id=2, column_idx=1)
        return frame

    def create_drone_card(self, parent, title_text, drone_id, column_idx):
        card = ctk.CTkFrame(
            parent, fg_color=self.colors["card_bg"], corner_radius=12,
            border_width=2, border_color=self.colors["gray"],
        )
        card.grid(row=0, column=column_idx, padx=12, pady=12, sticky="nsew")
        card.grid_propagate(False)

        # Store title label references directly for easier color update
        title_label_attr = f"drone{drone_id}_card_title_label"
        title_label = ctk.CTkLabel(card, text=title_text, font=FONTS["subtitle"], text_color=self.colors["accent"])
        title_label.pack(pady=(12, 8))
        setattr(self, title_label_attr, title_label)

        if drone_id == 1: self.dash_drone1_card_ref = card
        else: self.dash_drone2_card_ref = card

        feed_frame = ctk.CTkFrame(card, fg_color=self.colors["dark"], corner_radius=8)
        feed_frame.pack(pady=(5, 10), padx=10, fill="both", expand=True)
        feed_frame.pack_propagate(False) 

        image_label = ctk.CTkLabel(feed_frame, text="")
        image_label.pack(expand=True, fill="both")
        self.drone_image_labels[drone_id] = image_label

        if self.static_placeholder_ctkimage:
            image_label.configure(image=self.static_placeholder_ctkimage, text="")
        else:
            image_label.configure(text="Placeholder N/A", font=FONTS["small"], text_color=self.colors["warning"])

        def resize_image_on_frame_resize(event):
            if event.width > 0 and event.height > 0:
                if not self.drone_process_commanded_active[drone_id] or not self.gif_loaded_successfully[drone_id]:
                    self._load_static_placeholder_images(event.width, event.height)
                    if self.static_placeholder_ctkimage:
                        image_label.configure(image=self.static_placeholder_ctkimage, text="")
                elif self.drone_process_commanded_active[drone_id] and self.gif_loaded_successfully[drone_id]:
                    if self.drone_gif_ctk_frames[drone_id] and (
                        event.width != self.drone_gif_ctk_frames[drone_id][0].width() or
                        event.height != self.drone_gif_ctk_frames[drone_id][0].height()
                    ):
                        print(f"INFO: Resizing GIF for Drone {drone_id} to {event.width}x{event.height}")
                        self._load_gif_frames(drone_id, DRONE_GIF_PATH)
                        if self.drone_gif_animation_job_id[drone_id]:
                            self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                            self.drone_gif_animation_job_id[drone_id] = None
                        self.drone_gif_current_frame_index[drone_id] = 0
                        self._animate_gif(drone_id)
        feed_frame.bind("<Configure>", resize_image_on_frame_resize)

        status_display_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_display_frame.pack(pady=(8, 8))
        if drone_id == 1:
            self.drone1_dashboard_status_light, self.drone1_dashboard_status_label = \
                self._create_dashboard_status_widgets(status_display_frame, "INACTIVE")
        else:
            self.drone2_dashboard_status_light, self.drone2_dashboard_status_label = \
                self._create_dashboard_status_widgets(status_display_frame, "INACTIVE")

        buttons_control_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_control_frame.pack(pady=(8, 12), padx=15, fill="x")
        start_cmd = self.start_drone1 if drone_id == 1 else self.start_drone2
        stop_cmd = self.stop_drone1 if drone_id == 1 else self.stop_drone2
        
        self.drone_start_buttons = getattr(self, 'drone_start_buttons', {})
        self.drone_stop_buttons = getattr(self, 'drone_stop_buttons', {})

        start_btn = self.create_control_button(buttons_control_frame, f"Start Drone {drone_id}", start_cmd,
                                               self.colors["success"], self.colors["success_hover"])
        self.drone_start_buttons[drone_id] = start_btn

        stop_btn = self.create_control_button(buttons_control_frame, f"Stop Drone {drone_id}", stop_cmd,
                                             self.colors["danger"], self.colors["danger_hover"])
        self.drone_stop_buttons[drone_id] = stop_btn
        return card

    def _load_gif_frames(self, drone_id, gif_path):
        image_label_widget = self.drone_image_labels.get(drone_id)
        if not image_label_widget:
            print(f"ERROR: No image label widget found for Drone {drone_id} for GIF loading.")
            self.gif_loaded_successfully[drone_id] = False
            return

        current_width = image_label_widget.winfo_width()
        current_height = image_label_widget.winfo_height()
        if current_width == 0 or current_height == 0:
            print(f"WARNING: Image label for Drone {drone_id} has zero dimensions. Using default for GIF.")
            current_width, current_height = FEED_WIDTH_SMALL, FEED_HEIGHT_SMALL

        try:
            pil_gif = Image.open(gif_path)
            self.drone_gif_ctk_frames[drone_id] = []
            self.drone_gif_durations[drone_id] = []
            for i in range(pil_gif.n_frames):
                pil_gif.seek(i)
                pil_frame_copy = pil_gif.copy().convert("RGBA")
                pil_frame_resized = pil_frame_copy.resize((current_width, current_height), Image.Resampling.LANCZOS)
                self.drone_gif_ctk_frames[drone_id].append(ImageTk.PhotoImage(pil_frame_resized))
                self.drone_gif_durations[drone_id].append(pil_gif.info.get('duration', 100))
            self.gif_loaded_successfully[drone_id] = True
            print(f"INFO: GIF loaded for Drone {drone_id} ({pil_gif.n_frames} frames) resized to {current_width}x{current_height}.")
        except Exception as e:
            print(f"ERROR: Could not load GIF for Drone {drone_id}: {e}")
            self.gif_loaded_successfully[drone_id] = False

    def _animate_gif(self, drone_id):
        if not self.drone_process_commanded_active[drone_id] or not self.gif_loaded_successfully[drone_id] or not self.drone_gif_ctk_frames[drone_id]:
            if self.drone_gif_animation_job_id[drone_id]:
                self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                self.drone_gif_animation_job_id[drone_id] = None
            image_label_widget = self.drone_image_labels.get(drone_id)
            if image_label_widget and self.static_placeholder_ctkimage:
                image_label_widget.configure(image=self.static_placeholder_ctkimage, text="")
            return

        idx = self.drone_gif_current_frame_index[drone_id]
        self.drone_image_labels[drone_id].configure(image=self.drone_gif_ctk_frames[drone_id][idx], text="")
        self.drone_gif_current_frame_index[drone_id] = (idx + 1) % len(self.drone_gif_ctk_frames[drone_id])
        duration = self.drone_gif_durations[drone_id][idx] if self.drone_gif_durations[drone_id] and idx < len(self.drone_gif_durations[drone_id]) else 100
        self.drone_gif_animation_job_id[drone_id] = self.app.after(duration, lambda: self._animate_gif(drone_id))

    def _populate_telemetry_card_content(self, card_widget, title_text, drone_id):
        title_frame = ctk.CTkFrame(card_widget, fg_color="transparent")
        title_frame.pack(pady=(15, 10), fill="x", padx=20)
        
        # Store references for easier color updates
        title_label_attr = f"drone{drone_id}_telemetry_title_label"
        conn_label_attr = f"drone{drone_id}_telemetry_connection_label"

        title_label = ctk.CTkLabel(title_frame, text=title_text, font=FONTS["subtitle"], text_color=self.colors["accent"])
        title_label.pack(side="left")
        setattr(self, title_label_attr, title_label)
        
        conn_label = ctk.CTkLabel(title_frame, text="Status: UNKNOWN", font=FONTS["small"], text_color=self.colors["gray"])
        conn_label.pack(side="right", padx=(0, 5))
        setattr(self, conn_label_attr, conn_label)
        
        data_rows_frame = ctk.CTkFrame(card_widget, fg_color="transparent")
        data_rows_frame.pack(fill="both", expand=True, pady=(5, 15), padx=20)
        telemetry_fields = {
            "latitude": "Latitude", "longitude": "Longitude", "altitude": "Altitude",
            "speed": "Speed", "battery": "Battery", "mode": "Flight Mode",
            "pitch": "Pitch Angle", "roll": "Roll Angle", "yaw": "Yaw Angle"
        }
        current_data_dict = {}
        for key, display_name in telemetry_fields.items():
            current_data_dict[key] = self.create_telemetry_row(data_rows_frame, display_name, "-")
        if drone_id == 1: self.drone1_data = current_data_dict
        else: self.drone2_data = current_data_dict

    def create_telemetry_display(self, parent_frame):
        frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(25, 15))
        self.telemetry_header_label = ctk.CTkLabel(header, text="Live Drone Telemetry", font=FONTS["title"], text_color=self.colors["text_primary"])
        self.telemetry_header_label.pack(side="left")
        
        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=15, pady=10)
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)

        self.drone1_card_ref = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color=self.colors["card_bg"],
                                            border_color=self.colors["gray"], border_width=2)
        self.drone1_card_ref.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.drone1_card_ref.grid_propagate(False)
        self._populate_telemetry_card_content(self.drone1_card_ref, "Drone 1 Telemetry", drone_id=1)

        self.drone2_card_ref = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color=self.colors["card_bg"],
                                            border_color=self.colors["gray"], border_width=2)
        self.drone2_card_ref.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.drone2_card_ref.grid_propagate(False)
        self._populate_telemetry_card_content(self.drone2_card_ref, "Drone 2 Telemetry", drone_id=2)
        return frame

    def create_telemetry_row(self, parent, label, value):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row_frame.pack(fill="x", padx=5, pady=3)
        ctk.CTkLabel(row_frame, text=f"{label}:", font=FONTS["body"], text_color=self.colors["text_secondary"],
                     width=130, anchor="w").pack(side="left", padx=(0,8))
        value_label = ctk.CTkLabel(row_frame, text=value, font=FONTS["body"], text_color=self.colors["text_primary"], anchor="w")
        value_label.pack(side="left", expand=True, fill="x")
        return value_label

    def show_dashboard(self):
        self.telemetry_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)

    def show_telemetry(self):
        self.dashboard_frame.pack_forget()
        self.telemetry_frame.pack(fill="both", expand=True)

    def toggle_theme(self):
        if self.current_theme == "dark":
            ctk.set_appearance_mode("light")
            self.current_theme = "light"
            self.colors = COLORS_LIGHT
            print("Tema: AÇIK")
        else:
            ctk.set_appearance_mode("dark")
            self.current_theme = "dark"
            self.colors = COLORS_DARK
            print("Tema: KOYU")
        self.update_ui_colors()

    def update_ui_colors(self):
        self.nav_sidebar.configure(fg_color=self.colors["primary"])
        # self.qgc_tools_panel.configure(fg_color=self.colors["secondary"]) # REMOVED
        self.main_content_area.configure(fg_color=self.colors["dark"])

        for widget in self.logo_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel):
                widget.configure(text_color=self.colors["accent"] if "SwarMind" in widget.cget("text") else self.colors["text_primary"])

        for btn in self.nav_button_refs:
            btn.configure(hover_color=self.colors["secondary"], text_color=self.colors["text_primary"])
        
        if hasattr(self, 'system_controls_title_label'): # Check if label exists
            self.system_controls_title_label.configure(text_color=self.colors["text_secondary"])

        for i, btn in enumerate(self.control_buttons_refs):
            # Assuming specific order for Start All, Stop All, Emergency Stop
            if i == 0: # Start All
                btn.configure(fg_color=self.colors["success"], hover_color=self.colors["success_hover"])
            elif i == 1 or i == 2: # Stop All, Emergency Stop
                btn.configure(fg_color=self.colors["danger"], hover_color=self.colors["danger_hover"])
        
        self.theme_button.configure(fg_color=self.colors["secondary"], hover_color=self.colors["tertiary"], text_color=self.colors["accent"])
        
        # Update Launch QGC button colors
        if hasattr(self, 'launch_qgc_button'): # Check if it has been created
            self.launch_qgc_button.configure(
                fg_color=self.colors["secondary"], 
                hover_color=self.colors["tertiary"], 
                text_color=self.colors["accent"]
            )

        self.exit_button.configure(fg_color=self.colors["dark"], hover_color=self.colors["danger_hover"], border_color=self.colors["secondary"])

        # self.qgc_label.configure(text_color=self.colors["text_primary"]) # REMOVED
        # self.qgc_button.configure(fg_color=self.colors["accent"], hover_color="#3A7BBF") # REMOVED (now self.launch_qgc_button)

        self.dashboard_header_label.configure(text_color=self.colors["text_primary"])
        
        for i in [1, 2]:
            dash_card = getattr(self, f"dash_drone{i}_card_ref", None)
            dash_title = getattr(self, f"drone{i}_card_title_label", None)
            if dash_card: dash_card.configure(fg_color=self.colors["card_bg"], border_color=self.colors.get("gray", "#6c757d"))
            if dash_title: dash_title.configure(text_color=self.colors["accent"])

            # Update feed frame background and placeholder text color
            if self.drone_image_labels[i]:
                feed_frame = self.drone_image_labels[i].master # Get parent CTkFrame
                if isinstance(feed_frame, ctk.CTkFrame): # Ensure it's the feed_frame
                    feed_frame.configure(fg_color=self.colors["dark"])
                # Check if placeholder text needs color update
                if self.drone_image_labels[i].cget("image") == "" and "Placeholder N/A" in self.drone_image_labels[i].cget("text"):
                    self.drone_image_labels[i].configure(text_color=self.colors["warning"])

            start_btn = self.drone_start_buttons.get(i)
            stop_btn = self.drone_stop_buttons.get(i)
            if start_btn: start_btn.configure(fg_color=self.colors["success"], hover_color=self.colors["success_hover"])
            if stop_btn: stop_btn.configure(fg_color=self.colors["danger"], hover_color=self.colors["danger_hover"])

        self.telemetry_header_label.configure(text_color=self.colors["text_primary"])
        for i in [1, 2]:
            tel_card = getattr(self, f"drone{i}_card_ref", None) # Telemetry view card
            tel_title = getattr(self, f"drone{i}_telemetry_title_label", None)
            tel_conn = getattr(self, f"drone{i}_telemetry_connection_label", None)
            if tel_card:
                tel_card.configure(fg_color=self.colors["card_bg"], border_color=self.colors.get("gray", "#6c757d"))
                self._update_telemetry_row_colors(tel_card)
            if tel_title: tel_title.configure(text_color=self.colors["accent"])
            # Connection label color is updated in _update_telemetry_card_visuals
        
        self._update_telemetry_card_visuals(1, self.drone1_data if self.is_drone_connected_via_telemetry[1] else {}) 
        self._update_telemetry_card_visuals(2, self.drone2_data if self.is_drone_connected_via_telemetry[2] else {})

    def _update_telemetry_row_colors(self, card_widget):
        for child_frame in card_widget.winfo_children():
            if isinstance(child_frame, ctk.CTkFrame) and child_frame.cget("fg_color") == "transparent": 
                for row_frame in child_frame.winfo_children():
                    if isinstance(row_frame, ctk.CTkFrame) and row_frame.cget("fg_color") == "transparent":
                        labels_in_row = row_frame.winfo_children()
                        if len(labels_in_row) >= 1 and isinstance(labels_in_row[0], ctk.CTkLabel) and labels_in_row[0].cget("text").endswith(":"):
                            labels_in_row[0].configure(text_color=self.colors["text_secondary"])
                        if len(labels_in_row) >= 2 and isinstance(labels_in_row[1], ctk.CTkLabel):
                             # Value color is primarily handled by update_telemetry_data_labels/clear
                            if labels_in_row[1].cget("text") == "-" or labels_in_row[1].cget("text").startswith("-"):
                                labels_in_row[1].configure(text_color=self.colors["text_primary"])


    def handle_drone_process_command(self, drone_id, start_process):
        self.drone_process_commanded_active[drone_id] = start_process
        if not start_process: self.is_drone_connected_via_telemetry[drone_id] = False
        self.last_telemetry_update_time[drone_id] = 0.0 

        if start_process:
            print(f"Attempting to start Drone {drone_id} processes...")
            command_key = f"drone{drone_id}" # Simplified command key
            subprocess.Popen(COMMANDS[command_key], shell=True, text=True)

            current_width = self.drone_image_labels[drone_id].winfo_width()
            current_height = self.drone_image_labels[drone_id].winfo_height()
            if not self.gif_loaded_successfully[drone_id] or (
                current_width > 0 and current_height > 0 and (
                (self.drone_gif_ctk_frames[drone_id] and \
                (current_width != self.drone_gif_ctk_frames[drone_id][0].width() or \
                 current_height != self.drone_gif_ctk_frames[drone_id][0].height())) or \
                 not self.drone_gif_ctk_frames[drone_id] 
                )
            ):
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
                        image_label_widget.configure(text="Image N/A", image=None)
        else: 
            print(f"Attempting to stop Drone {drone_id} processes...")
            subprocess.call(f"tmux kill-session -t drone{drone_id}_session 2>/dev/null", shell=True)
            subprocess.call(f"tmux kill-session -t drone{drone_id}_py 2>/dev/null", shell=True)

            if self.drone_gif_animation_job_id[drone_id]:
                self.app.after_cancel(self.drone_gif_animation_job_id[drone_id])
                self.drone_gif_animation_job_id[drone_id] = None
            
            image_label_widget = self.drone_image_labels.get(drone_id)
            if image_label_widget:
                if self.static_placeholder_ctkimage:
                    image_label_widget.configure(image=self.static_placeholder_ctkimage, text="")
                else:
                    image_label_widget.configure(text="Image Stopped", image=None)
        self._update_telemetry_card_visuals(drone_id, {}) 

    def start_drone1(self): self.handle_drone_process_command(1, True)
    def stop_drone1(self): self.handle_drone_process_command(1, False)
    def start_drone2(self): self.handle_drone_process_command(2, True)
    def stop_drone2(self): self.handle_drone_process_command(2, False)

    def start_qgc(self):
        print("Launching QGroundControl...")
        subprocess.Popen(COMMANDS["qgc"], shell=True, text=True)

    def start_all(self):
        print("Starting all systems...")
        self.start_drone1()
        self.app.after(2000, self.start_drone2) 
        self.app.after(7000, self.start_qgc) 

    def stop_all(self):
        print("Stopping all drone systems...")
        self.stop_drone1()
        self.stop_drone2()

    def emergency_stop(self):
        print("EMERGENCY STOP ACTIVE!")
        self.stop_all()

    def read_shared_memory(self):
        try:
            telemetry_shm = shm.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
            raw_bytes = bytearray(telemetry_shm.buf)
            try: null_index = raw_bytes.index(0) 
            except ValueError: null_index = len(raw_bytes) # Read all if no null byte
            decoded_str = raw_bytes[:null_index].decode('utf-8', errors='ignore').rstrip('\x00')
            telemetry_shm.close()
            return json.loads(decoded_str) if decoded_str.strip() else {}
        except FileNotFoundError: return None
        except json.JSONDecodeError: return None
        except Exception: return None

    # Telemetry data display keys are corrected in this version
    def update_telemetry_data_labels(self, card_data_labels, telemetry):
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        if card_data_labels:
            lat_text = f"{telemetry.get('latitude', 0.0):.6f}" if isinstance(telemetry.get('latitude'), (float, int)) else "-"
            lon_text = f"{telemetry.get('longitude', 0.0):.6f}" if isinstance(telemetry.get('longitude'), (float, int)) else "-"
            alt_raw = telemetry.get('absolute_altitude', telemetry.get('altitude', "-")) 
            alt_text = f"{alt_raw:.2f} m" if isinstance(alt_raw, (float, int)) else f"{alt_raw} m"

            card_data_labels.get("latitude").configure(text=lat_text, text_color=self.colors["text_primary"])
            card_data_labels.get("longitude").configure(text=lon_text, text_color=self.colors["text_primary"])
            card_data_labels.get("altitude").configure(text=alt_text, text_color=self.colors["text_primary"])
            
            speed_val = telemetry.get('speed', '-') 
            speed_text = f"{speed_val:.2f} m/s" if isinstance(speed_val, (float, int)) else f"{speed_val} m/s"
            card_data_labels.get("speed").configure(text=speed_text, text_color=self.colors["text_primary"])
            
            battery_val = telemetry.get('battery_percent', None) 
            battery_text = "-%"
            if isinstance(battery_val, (float, int)) and battery_val is not None: battery_text = f"{battery_val:.0f}%"
            elif battery_val is not None and str(battery_val).replace('.', '', 1).isdigit(): battery_text = f"{float(battery_val):.0f}%"
            elif battery_val is not None: battery_text = str(battery_val)
            card_data_labels.get("battery").configure(text=battery_text, text_color=self.colors["text_primary"])

            card_data_labels.get("mode").configure(text=f"{telemetry.get('flight_mode', '-')}", text_color=self.colors["text_primary"])
            
            pitch_val = telemetry.get('pitch', '-') 
            pitch_text = f"{pitch_val:.2f}°" if isinstance(pitch_val, (float, int)) else f"{pitch_val}°"
            card_data_labels.get("pitch").configure(text=pitch_text, text_color=self.colors["text_primary"])

            roll_val = telemetry.get('roll', '-') 
            roll_text = f"{roll_val:.2f}°" if isinstance(roll_val, (float, int)) else f"{roll_val}°"
            card_data_labels.get("roll").configure(text=roll_text, text_color=self.colors["text_primary"])

            yaw_val = telemetry.get('yaw', '-') 
            yaw_text = f"{yaw_val:.2f}°" if isinstance(yaw_val, (float, int)) else f"{yaw_val}°"
            card_data_labels.get("yaw").configure(text=yaw_text, text_color=self.colors["text_primary"])

    def _clear_telemetry_data_labels(self, card_data_labels):
        if card_data_labels:
            default_texts = {
                "latitude": "-", "longitude": "-", "altitude": "- m", "speed": "- m/s",
                "battery": "-%", "mode": "-", "pitch": "-°", "roll": "-°", "yaw": "-°"
            }
            for key, label_widget in card_data_labels.items():
                if label_widget and isinstance(label_widget, ctk.CTkLabel):
                    label_widget.configure(text=default_texts.get(key, "-"), text_color=self.colors["text_primary"])

    def _update_telemetry_card_visuals(self, drone_id, current_telemetry_data):
        dash_light_ref, dash_label_ref = (self.drone1_dashboard_status_light, self.drone1_dashboard_status_label) if drone_id == 1 else \
                                 (self.drone2_dashboard_status_light, self.drone2_dashboard_status_label)
        
        tel_view_card_widget = getattr(self, f"drone{drone_id}_card_ref", None)
        tel_conn_label_widget = getattr(self, f"drone{drone_id}_telemetry_connection_label", None)
        dashboard_card_widget = getattr(self, f"dash_drone{drone_id}_card_ref", None)
        current_data_labels_dict = getattr(self, f"drone{drone_id}_data", {})

        status_text, light_color_key, text_color_key, border_color_key = "INACTIVE", "gray", "text_secondary", "gray"

        if self.drone_process_commanded_active[drone_id]:
            if self.is_drone_connected_via_telemetry[drone_id]:
                status_text, light_color_key, text_color_key, border_color_key = "ACTIVE", "success", "success", "success"
            else: 
                status_text, light_color_key, text_color_key, border_color_key = "AWAITING DATA", "warning", "warning", "warning"
        else: 
            status_text, light_color_key, text_color_key, border_color_key = "DISCONNECTED", "disconnected", "text_secondary", "gray"
            
        if dash_light_ref: dash_light_ref.configure(text_color=self.colors.get(light_color_key, self.colors["gray"]))
        if dash_label_ref: dash_label_ref.configure(text=status_text.upper(), text_color=self.colors.get(text_color_key, self.colors["text_secondary"]))
        if dashboard_card_widget: dashboard_card_widget.configure(border_color=self.colors.get(border_color_key, self.colors["gray"]))
        if tel_view_card_widget: tel_view_card_widget.configure(border_color=self.colors.get(border_color_key, self.colors["gray"]))
        
        if tel_conn_label_widget:
            conn_disp_text = "Status: DISCONNECTED"
            conn_disp_color = self.colors["text_secondary"]
            if self.drone_process_commanded_active[drone_id]:
                conn_disp_text = "Status: CONNECTED" if self.is_drone_connected_via_telemetry[drone_id] else "Status: NO TELEMETRY"
                conn_disp_color = self.colors["success"] if self.is_drone_connected_via_telemetry[drone_id] else self.colors["warning"]
            tel_conn_label_widget.configure(text=conn_disp_text, text_color=conn_disp_color)

        if self.drone_process_commanded_active[drone_id] and self.is_drone_connected_via_telemetry[drone_id]:
            self.update_telemetry_data_labels(current_data_labels_dict, current_telemetry_data)
        else:
            self._clear_telemetry_data_labels(current_data_labels_dict)

    def update_telemetry(self):
        shared_data = self.read_shared_memory()
        now = time.time()
        data_received_this_cycle = {1: False, 2: False}

        if shared_data:
            for drone_id_str, telemetry_content in shared_data.items():
                try:
                    drone_id = int(drone_id_str)
                    if drone_id in [1, 2]:
                        if self.drone_process_commanded_active[drone_id]: # Only process if active
                            self.is_drone_connected_via_telemetry[drone_id] = True 
                            self.last_telemetry_update_time[drone_id] = now
                            # Pass the actual telemetry content for this drone
                            self._update_telemetry_card_visuals(drone_id, telemetry_content) 
                        data_received_this_cycle[drone_id] = True # Mark data was present in SHM
                except ValueError:
                    print(f"Invalid drone_id format in shared memory: {drone_id_str}")

        for did in [1, 2]:
            if self.drone_process_commanded_active[did]:
                # If active, but no data received for it in this cycle from SHM
                if not data_received_this_cycle[did] and self.is_drone_connected_via_telemetry[did]: 
                    # And if it was previously connected and timeout exceeded
                    if (now - self.last_telemetry_update_time[did] > TIMEOUT_THRESHOLD):
                        print(f"Drone {did} telemetry timed out.")
                        self.is_drone_connected_via_telemetry[did] = False
                        self._update_telemetry_card_visuals(did, {}) # Update visuals to show timeout
                # If active but not connected (e.g. awaiting first data, or already timed out)
                elif not self.is_drone_connected_via_telemetry[did]:
                     self._update_telemetry_card_visuals(did, {}) # Ensure visuals reflect "AWAITING" or "NO TELEMETRY"
            else: # If drone is not commanded to be active
                if self.is_drone_connected_via_telemetry[did]: # If it was somehow marked connected, correct it
                    self.is_drone_connected_via_telemetry[did] = False
                self._update_telemetry_card_visuals(did, {}) # Update visuals to "DISCONNECTED"
            
        self.app.after(500, self.update_telemetry)

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    try:
        existing_shm = shm.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
        existing_shm.close()
        print(f"INFO: Shared memory '{SHM_NAME}' found.")
    except FileNotFoundError:
        print(f"INFO: Shared memory '{SHM_NAME}' not found. Ensure the telemetry script (writer) is running and has created it.")
    
    app_instance = DroneControlCenter()
    app_instance.run()
