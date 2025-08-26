import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import os
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps # Import Pillow libraries
import uuid # For unique IDs
import random # For random Aktenzeichen
import string # For random Aktenzeichen
import re # For regex in placeholder extraction

# Class for image cropping dialog
class ImageCropper(tk.Toplevel):
    def __init__(self, parent, pil_image):
        super().__init__(parent)
        self.parent = parent
        self.title("Bild zuschneiden")
        self.geometry("600x600")
        self.transient(parent) # Make dialog appear on top of parent
        self.grab_set() # Disable interaction with parent window

        self.original_pil_image = pil_image
        self.cropped_image = None # This will store the final cropped PIL Image

        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.rect_id = None

        self.canvas = tk.Canvas(self, bg="gray", cursor="cross") # Canvas background
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize) # Bind resize event

        self.tk_image = None # To hold the PhotoImage for the canvas
        self.display_pil_image = None # To hold the PIL image scaled for display

        self.canvas.after(100, self._load_initial_image) # Load image after canvas is ready

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Zuschneiden", command=self.perform_crop).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=self.cancel_crop).pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self.cancel_crop) # Handle window close button

    def _on_canvas_resize(self, event):
        """Reloads and rescales the image when the canvas is resized."""
        self._load_initial_image()

    def _load_initial_image(self):
        """Loads and displays the original image on the canvas, scaled to fit."""
        if self.canvas.winfo_width() <= 1 or self.canvas.winfo_height() <= 1:
            self.after(100, self._load_initial_image) # Try again if canvas not ready
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        img_width, img_height = self.original_pil_image.size
        
        # Calculate ratio to fit image within canvas while maintaining aspect ratio
        ratio = min(canvas_width / img_width, canvas_height / img_height)
        display_width = int(img_width * ratio)
        display_height = int(img_height * ratio)

        self.display_pil_image = self.original_pil_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.display_pil_image)
        
        self.canvas.delete("all") # Clear previous image and rectangle
        self.canvas.create_image(canvas_width/2, canvas_height/2, image=self.tk_image, anchor="center")
        self.rect_id = None # Reset rectangle ID
        self.current_rect = None # Reset current selection

    def on_button_press(self, event):
        """Starts drawing the crop rectangle."""
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        """Updates the crop rectangle as the mouse is dragged."""
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        """Finalizes the crop rectangle selection."""
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        self.current_rect = (min(self.start_x, end_x), min(self.start_y, end_y),
                             max(self.start_x, end_x), max(self.start_y, end_y))

    def perform_crop(self):
        """Crops the image based on the selected rectangle and resizes it to 150x150."""
        if not self.current_rect:
            messagebox.showwarning("Zuschneiden", "Bitte wählen Sie einen Bereich zum Zuschneiden aus.", parent=self)
            return

        # Get the bounding box of the displayed image on the canvas
        img_canvas_x0, img_canvas_y0 = self.canvas.coords(self.canvas.find_all()[0]) # Center of image
        display_img_width, display_img_height = self.display_pil_image.size
        
        # Calculate top-left corner of the displayed image relative to canvas (0,0)
        display_img_x0 = img_canvas_x0 - display_img_width / 2
        display_img_y0 = img_canvas_y0 - display_img_height / 2

        # Crop rectangle coordinates relative to the displayed image's top-left corner
        crop_x1_display = self.current_rect[0] - display_img_x0
        crop_y1_display = self.current_rect[1] - display_img_y0
        crop_x2_display = self.current_rect[2] - display_img_y0
        crop_y2_display = self.current_rect[3] - display_img_y0

        # Ensure crop coordinates are within the displayed image bounds
        crop_x1_display = max(0, crop_x1_display)
        crop_y1_display = max(0, crop_y1_display)
        crop_x2_display = min(display_img_width, crop_x2_display)
        crop_y2_display = min(display_img_height, crop_y2_display)

        # Scale crop coordinates back to original image size
        img_width_orig, img_height_orig = self.original_pil_image.size
        scale_x = img_width_orig / display_img_width
        scale_y = img_height_orig / display_img_height

        final_crop_box = (int(crop_x1_display * scale_x), int(crop_y1_display * scale_y),
                          int(crop_x2_display * scale_x), int(crop_y2_display * scale_y))
        
        # Ensure crop box is valid (x1 < x2, y1 < y2)
        if final_crop_box[0] >= final_crop_box[2] or final_crop_box[1] >= final_crop_box[3]:
            messagebox.showwarning("Zuschneiden", "Ungültiger Auswahlbereich. Bitte wählen Sie einen gültigen Bereich.", parent=self)
            return

        self.cropped_image = self.original_pil_image.crop(final_crop_box)
        
        # Resize cropped image to 150x150
        target_size = (150, 150)
        self.cropped_image = self.cropped_image.resize(target_size, Image.Resampling.LANCZOS)

        self.destroy() # Close the dialog

    def cancel_crop(self):
        """Cancels the cropping operation."""
        self.cropped_image = None
        self.destroy() # Close the dialog


class PoliceRPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Polizei RP App")
        self.root.geometry("1200x850") # Larger initial window size for more tabs
        self.root.minsize(900, 700) # Set minimum window size

        # --- Design: Root window background ---
        self.root.configure(bg='#e0e0e0') # Light grey background for the root window

        # Define file paths for different data types
        self.notes_file = "notizen.json"
        self.reports_file = "anzeigen.json" # Main reports that link to perpetrators
        self.perpetrator_files_dir = "taeterakten" # Directory for perpetrator data and images
        self.perpetrator_files_json = os.path.join(self.perpetrator_files_dir, "taeterakten.json")
        self.perpetrator_images_dir = os.path.join(self.perpetrator_files_dir, "bilder")
        self.report_presets_file = "anzeigen_presets.json"
        self.predefined_crimes_file = "predefined_crimes.json" # New file for predefined crimes

        # Ensure directories exist
        os.makedirs(self.perpetrator_files_dir, exist_ok=True)
        os.makedirs(self.perpetrator_images_dir, exist_ok=True)

        # Load data for all sections
        self.notes = self.load_data(self.notes_file)
        self.reports = self.load_data(self.reports_file)
        self.perpetrator_files = self.load_data(self.perpetrator_files_json)
        self.report_presets = self.load_data(self.report_presets_file)

        # Load or initialize predefined crimes
        self.predefined_crimes = self.load_data(self.predefined_crimes_file)
        if not self.predefined_crimes:
            self.predefined_crimes = [
                {"name": "Diebstahl", "paragraph": "§ 242 StGB", "detention_units": 5, "fine": 100},
                {"name": "Raub", "paragraph": "§ 249 StGB", "detention_units": 10, "fine": 500},
                {"name": "Körperverletzung", "paragraph": "§ 223 StGB", "detention_units": 7, "fine": 200},
                {"name": "Sachbeschädigung", "paragraph": "§ 303 StGB", "detention_units": 3, "fine": 50},
                {"name": "Einbruch", "paragraph": "§ 244 StGB", "detention_units": 8, "fine": 300},
                {"name": "Betrug", "paragraph": "§ 263 StGB", "detention_units": 6, "fine": 250},
                {"name": "Drogenhandel", "paragraph": "BtMG", "detention_units": 15, "fine": 1000},
                {"name": "Widerstand gegen die Staatsgewalt", "paragraph": "§ 113 StGB", "detention_units": 4, "fine": 150},
                {"name": "Fahren ohne Fahrerlaubnis", "paragraph": "§ 21 StVG", "detention_units": 2, "fine": 80},
                {"name": "Verkehrsunfallflucht", "paragraph": "§ 142 StGB", "detention_units": 5, "fine": 120},
                {"name": "Brandstiftung", "paragraph": "§ 306 StGB", "detention_units": 12, "fine": 700},
                {"name": "Mord", "paragraph": "§ 211 StGB", "detention_units": 999, "fine": 5000}, # Example large values
                {"name": "Totschlag", "paragraph": "§ 212 StGB", "detention_units": 999, "fine": 3000},
                {"name": "Nötigung", "paragraph": "§ 240 StGB", "detention_units": 4, "fine": 100},
                {"name": "Beleidigung", "paragraph": "§ 185 StGB", "detention_units": 1, "fine": 30},
                {"name": "Hausfriedensbruch", "paragraph": "§ 123 StGB", "detention_units": 2, "fine": 40}
            ]
            self.save_data(self.predefined_crimes, self.predefined_crimes_file)

        # Add new report presets as requested
        # Only initialize if no presets exist (to avoid overwriting user-added ones)
        if not self.report_presets: 
            self.report_presets = [
                {"name": "Standard Anzeige", "template_string": "[Herr/Frau] [name] hat am [Datum] um [uhrzeit] folgende Straftaten begangen [Straftat1,2,3,4,5, etc], laut [Gesetz] wurden [Hafteinheiten] Hafteinheiten und eine Strafe von [Strafbetrag] verhängt. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"},
                {"name": "Ordnungswidrigkeit", "template_string": "Am [Datum] um [uhrzeit] wurde [Herr/Frau] [name] wegen einer Ordnungswidrigkeit ([OWI-Art]) gemäß [OWI-Gesetz] mit einem Verwarnungsgeld von [Verwarnungsgeld] € belegt. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"},
                {"name": "Fahndung", "template_string": "FAHNDUNG nach [name], geboren am [Geburtsdatum] in [Geburtsort]. Beschreibung: [Beschreibung]. Letzter bekannter Aufenthaltsort: [Ort]. Grund: [Grund der Fahndung]. Bei Sichtung bitte [Maßnahme] ergreifen. Aktenzeichen: [Aktenzeichen]. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"},
                {"name": "Festnahme", "template_string": "Festnahme von [Herr/Frau] [name] am [Datum] um [uhrzeit] in [Ort]. Grund der Festnahme: [Grund]. Die Person wurde zur [Ort der Verbringung] verbracht. Aktenzeichen: [Aktenzeichen]. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"},
                {"name": "Verkehrsunfall/Unfallbericht", "template_string": "Verkehrsunfall am [Datum] um [uhrzeit] in [Ort]. Beteiligte Fahrzeuge: [Fahrzeug 1], [Fahrzeug 2]. Beteiligte Personen: [Personen]. Sachschaden: [Sachschaden]. Personenschaden: [Personenschaden]. Ursache: [Unfallursache]. Aktenzeichen: [Aktenzeichen]. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"},
                {"name": "Zeugenvernehmung", "template_string": "Zeugenvernehmung von [Herr/Frau] [Zeugenname] am [Datum] um [uhrzeit] in [Ort]. Zum Sachverhalt: [Sachverhalt]. Aussage: [Aussage des Zeugen]. Aktenzeichen: [Aktenzeichen]. Unterschrift [Officer Name]: Unterschrift [Unterschrift Officer Name (Cursiv)]"}
            ]
            self.save_data(self.report_presets, self.report_presets_file)


        self.current_perpetrator_image_path = None # To store path of current perpetrator image for display/editing
        self.perpetrator_photo_image = None # To store Tkinter PhotoImage for display

        self.create_widgets()

    def load_data(self, filename):
        """Lädt Daten aus einer JSON-Datei."""
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Data migration for reports
                    if filename == self.reports_file:
                        for record in data:
                            # Migrate old 'address' to 'birthplace' in perpetrator files if it exists
                            if 'address' in record and 'birthplace' not in record:
                                record['birthplace'] = record['address']
                                del record['address'] # Remove old field
                            
                            # Migrate crimes_committed from list of strings to list of dicts
                            if 'crimes_committed' in record and all(isinstance(c, str) for c in record['crimes_committed']):
                                record['crimes_committed'] = [{"name": c, "paragraph": "", "detention_units": 0, "fine": 0} for c in record['crimes_committed']]
                    
                    # Data migration for perpetrator_files (address to birthplace)
                    if filename == self.perpetrator_files_json:
                        for pf_record in data:
                            if 'address' in pf_record and 'birthplace' not in pf_record:
                                pf_record['birthplace'] = pf_record['address']
                                del pf_record['address']
                    return data
            except json.JSONDecodeError:
                messagebox.showerror("Fehler", f"Fehler beim Laden von {filename}. Die Datei ist möglicherweise beschädigt. Eine neue leere Datei wird erstellt.")
                return []
        return []

    def save_data(self, data, filename):
        """Speichert Daten in einer JSON-Datei."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            messagebox.showerror("Speicherfehler", f"Konnte Daten nicht speichern in {filename}: {e}")

    def generate_random_case_number(self, length=8):
        """Generiert ein zufälliges Aktenzeichen (Buchstaben und Zahlen)."""
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choice(characters) for i in range(length))

    def get_perpetrator_by_name(self, name):
        """Sucht eine Täterakte nach Namen."""
        for pf in self.perpetrator_files:
            if pf['name'].lower() == name.lower():
                return pf
        return None

    def create_widgets(self):
        """Erstellt die GUI-Widgets und Tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Design: Apply a modern theme and configure styles ---
        style = ttk.Style()
        style.theme_use('clam') # 'clam' theme often provides a good base for modern look

        # Configure general frame and labelframe backgrounds
        style.configure('TFrame', background='#f0f0f0') # Light grey for frames
        style.configure('TLabelframe', background='#f0f0f0', borderwidth=1, relief="solid", bordercolor='#cccccc') # Light grey for labelframes, subtle border
        style.configure('TLabelframe.Label', background='#f0f0f0', foreground='#333333', font=('Arial', 12, 'bold')) # Label for labelframes

        # Configure ttk.Label
        style.configure('TLabel', background='#f0f0f0', foreground='#333333')

        # Configure ttk.Entry
        style.map('TEntry',
                  background=[('focus', '#ffffff'), ('!focus', '#ffffff')], # White background
                  fieldbackground=[('focus', '#ffffff'), ('!focus', '#ffffff')], # White background
                  foreground=[('readonly', '#555555'), ('!readonly', '#333333')], # Darker text color
                  bordercolor=[('focus', '#4a90e2'), ('!focus', '#cccccc')], # Blue border on focus
                  lightcolor=[('focus', '#4a90e2'), ('!focus', '#cccccc')],
                  darkcolor=[('focus', '#4a90e2'), ('!focus', '#cccccc')])

        # Configure ttk.Button
        style.configure('TButton',
                        font=('Arial', 10),
                        background='#358DFF', # A shade of blue
                        foreground='white',
                        borderwidth=0,
                        relief="flat",
                        padding=[10, 5]) # Add padding
        style.map('TButton',
                  background=[('active', '#126ADD')], # Darker blue on hover
                  foreground=[('active', 'white')])

        # Accent Button (e.g., for "Bericht erstellen")
        style.configure("Accent.TButton",
                        font=("Arial", 12, "bold"),
                        foreground="white",
                        background="#4CAF50", # Green
                        borderwidth=0,
                        relief="flat",
                        padding=[12, 6])
        style.map("Accent.TButton",
                  background=[('active', '#45a049')]) # Darker green on hover
        
        # CAccent Button (e.g., for "Bericht Kopieren")
        style.configure("CAccent.TButton",
                        font=("Arial", 12, "bold"),
                        foreground="white",
                        background="#358DFF", # Green
                        borderwidth=0,
                        relief="flat",
                        padding=[12, 6])
        style.map("CAccent.TButton",
                  background=[('active', "#126ADD")]) # Darker green on hover

        # Configure Listbox and ScrolledText (tk widgets, need direct bg config)
        # These will be set directly where they are created.


        # Tab Order: Notizen, Anzeigen, Täterakten, Straftaten verwalten, Anzeigen Presets
        # Notes Tab
        self.notes_frame = ttk.Frame(self.notebook, padding="15 15 15 15") # Increased padding
        self.notebook.add(self.notes_frame, text="Notizen")
        self.create_notes_tab(self.notes_frame)
        
        # Reports Tab (main entry for new cases, links to perpetrator files)
        self.reports_frame = ttk.Frame(self.notebook, padding="15 15 15 15") # Increased padding
        self.notebook.add(self.reports_frame, text="Anzeigen")
        self.create_reports_tab(self.reports_frame)

        # Perpetrator Files Tab (cumulative records of individuals)
        self.perpetrator_files_frame = ttk.Frame(self.notebook, padding="15 15 15 15") # Increased padding
        self.notebook.add(self.perpetrator_files_frame, text="Täterakten")
        self.create_perpetrator_files_tab(self.perpetrator_files_frame)

        # Manage Crimes Tab (new)
        self.manage_crimes_frame = ttk.Frame(self.notebook, padding="15 15 15 15") # Increased padding
        self.notebook.add(self.manage_crimes_frame, text="Straftaten verwalten")
        self.create_manage_crimes_tab(self.manage_crimes_frame)

        # Report Presets Tab
        self.report_presets_frame = ttk.Frame(self.notebook, padding="15 15 15 15") # Increased padding
        self.notebook.add(self.report_presets_frame, text="Bericht Presets") #Anzeigen Presets
        self.create_report_presets_tab(self.report_presets_frame)

    def _create_scrollable_tab(self, parent_container):
        """Creates a scrollable frame within a parent container (a tab)."""
        # Create a canvas and a vertical scrollbar
        canvas = tk.Canvas(parent_container, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent_container, orient="vertical", command=canvas.yview)
        
        # This frame will contain all the widgets and will be scrolled by the canvas
        scrollable_frame = ttk.Frame(canvas)

        # Bind the frame's configure event to update the canvas scroll region
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        # Create a window in the canvas for the scrollable frame
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


        return scrollable_frame

    # --- Notes Tab Functions ---
    def create_notes_tab(self, parent_frame):
        """Creates widgets for the Notes tab."""
        content_frame = self._create_scrollable_tab(parent_frame)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1) # Let the list group expand
        content_frame.grid_rowconfigure(2, weight=1) # Let the selected note group expand

        # --- Design: LabelFrame for grouping ---
        new_note_group = ttk.LabelFrame(content_frame, text="Neue Notiz hinzufügen", padding="15 10")
        new_note_group.grid(row=0, column=0, pady=10, padx=10, sticky="ew")
        new_note_group.grid_columnconfigure(1, weight=1)

        ttk.Label(new_note_group, text="Titel:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.new_note_title_entry = ttk.Entry(new_note_group)
        self.new_note_title_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(new_note_group, text="Inhalt:").grid(row=1, column=0, sticky="nw", padx=5, pady=2)
        self.new_note_content_text = scrolledtext.ScrolledText(new_note_group, wrap=tk.WORD, height=8, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.new_note_content_text.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        add_note_button = ttk.Button(new_note_group, text="Notiz hinzufügen", command=self.add_note)
        add_note_button.grid(row=2, column=0, columnspan=2, pady=10)

        # --- Design: LabelFrame for grouping ---
        notes_list_group = ttk.LabelFrame(content_frame, text="Ihre Notizen", padding="15 10")
        notes_list_group.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")
        notes_list_group.grid_rowconfigure(0, weight=1)
        notes_list_group.grid_columnconfigure(0, weight=1)

        self.notes_listbox = tk.Listbox(notes_list_group, selectmode=tk.SINGLE, font=("Arial", 10), bg='#ffffff', fg='#333333', selectbackground='#cceeff', selectforeground='#333333', relief="flat", borderwidth=1) # Design: Listbox bg/fg/selection/relief
        self.notes_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.notes_listbox.bind('<<ListboxSelect>>', self.display_selected_note)
        notes_scrollbar = ttk.Scrollbar(notes_list_group, orient="vertical", command=self.notes_listbox.yview)
        notes_scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        self.notes_listbox.config(yscrollcommand=notes_scrollbar.set)

        button_frame = ttk.Frame(notes_list_group)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        edit_note_button = ttk.Button(button_frame, text="Notiz bearbeiten", command=self.start_editing_note)
        edit_note_button.grid(row=0, column=0, padx=5, sticky="ew")
        delete_note_button = ttk.Button(button_frame, text="Notiz löschen", command=self.delete_note)
        delete_note_button.grid(row=0, column=1, padx=5, sticky="ew")

        # --- Design: LabelFrame for grouping ---
        selected_note_group = ttk.LabelFrame(content_frame, text="Ausgewählte Notiz", padding="15 10")
        selected_note_group.grid(row=2, column=0, pady=10, padx=10, sticky="nsew")
        selected_note_group.grid_rowconfigure(0, weight=1)
        selected_note_group.grid_columnconfigure(0, weight=1)

        self.selected_note_content_text = scrolledtext.ScrolledText(selected_note_group, wrap=tk.WORD, height=8, state='disabled', bg='#ffffff', fg='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.selected_note_content_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.populate_notes_list()

    def populate_notes_list(self):
        """Populates the notes listbox with data."""
        self.notes_listbox.delete(0, tk.END)
        sorted_notes = sorted(self.notes, key=lambda x: x.get('timestamp', ''), reverse=True)
        for i, note in enumerate(sorted_notes):
            self.notes_listbox.insert(tk.END, note['title'])

    def display_selected_note(self, event):
        """Displays the content of the selected note."""
        selected_indices = self.notes_listbox.curselection()
        if not selected_indices: return
        index = selected_indices[0]
        sorted_notes = sorted(self.notes, key=lambda x: x.get('timestamp', ''), reverse=True)
        selected_note = sorted_notes[index]
        self.selected_note_content_text.config(state='normal')
        self.selected_note_content_text.delete(1.0, tk.END)
        self.selected_note_content_text.insert(tk.END, selected_note['content'])
        self.selected_note_content_text.config(state='disabled')

    def add_note(self):
        """Adds a new note."""
        title = self.new_note_title_entry.get().strip()
        content = self.new_note_content_text.get(1.0, tk.END).strip()
        if not title or not content:
            messagebox.showwarning("Eingabefehler", "Titel und Inhalt der Notiz dürfen nicht leer sein.")
            return
        self.notes.append({"id": str(uuid.uuid4()), "title": title, "content": content, "timestamp": datetime.now().isoformat()})
        self.save_data(self.notes, self.notes_file)
        self.populate_notes_list()
        self.new_note_title_entry.delete(0, tk.END)
        self.new_note_content_text.delete(1.0, tk.END)
        messagebox.showinfo("Erfolg", "Notiz erfolgreich hinzugefügt!")

    def start_editing_note(self):
        """Prepares a note for editing."""
        selected_indices = self.notes_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Notiz zum Bearbeiten aus.")
            return
        index = selected_indices[0]
        sorted_notes = sorted(self.notes, key=lambda x: x.get('timestamp', ''), reverse=True)
        self.editing_note_index = self.notes.index(sorted_notes[index])
        note = self.notes[self.editing_note_index]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Notiz bearbeiten")
        edit_window.geometry("500x400")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.grid_rowconfigure(1, weight=1)
        edit_window.grid_columnconfigure(1, weight=1)

        ttk.Label(edit_window, text="Titel:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        edit_title_entry = ttk.Entry(edit_window)
        edit_title_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        edit_title_entry.insert(0, note['title'])
        ttk.Label(edit_window, text="Inhalt:").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        edit_content_text = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD, height=10, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        edit_content_text.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        edit_content_text.insert(1.0, note['content'])

        def save_edited_note():
            new_title = edit_title_entry.get().strip()
            new_content = edit_content_text.get(1.0, tk.END).strip()
            if not new_title or not new_content:
                messagebox.showwarning("Eingabefehler", "Titel und Inhalt dürfen nicht leer sein.", parent=edit_window)
                return
            self.notes[self.editing_note_index]['title'] = new_title
            self.notes[self.editing_note_index]['content'] = new_content
            self.save_data(self.notes, self.notes_file)
            self.populate_notes_list()
            self.display_selected_note(None)
            messagebox.showinfo("Erfolg", "Notiz erfolgreich aktualisiert!", parent=edit_window)
            edit_window.destroy()
        ttk.Button(edit_window, text="Speichern", command=save_edited_note).grid(row=2, column=0, columnspan=2, pady=10)

    def delete_note(self):
        """Deletes the selected note."""
        selected_indices = self.notes_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Notiz zum Löschen aus.")
            return
        index = selected_indices[0]
        if messagebox.askyesno("Bestätigen", "Möchten Sie diese Notiz wirklich löschen?"):
            sorted_notes = sorted(self.notes, key=lambda x: x.get('timestamp', ''), reverse=True)
            original_note_to_delete = sorted_notes[index]
            original_index = self.notes.index(original_note_to_delete)
            del self.notes[original_index]
            self.save_data(self.notes, self.notes_file)
            self.populate_notes_list()
            self.selected_note_content_text.config(state='normal')
            self.selected_note_content_text.delete(1.0, tk.END)
            self.selected_note_content_text.config(state='disabled')
            messagebox.showinfo("Erfolg", "Notiz erfolgreich gelöscht!")

    def open_crime_selection_dialog(self, current_selection_list, target_label_widget):
        """Opens a dialog for selecting crimes."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Straftaten auswählen")
        dialog.geometry("550x650")
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.grid_rowconfigure(1, weight=1) # Listbox frame (now row 1)
        dialog.grid_rowconfigure(2, weight=0) # Add new crime section (now row 2)
        dialog.grid_rowconfigure(3, weight=0) # Buttons (now row 3)
        dialog.grid_columnconfigure(0, weight=1)

        # --- Search Field ---
        search_frame = ttk.Frame(dialog, padding="10")
        search_frame.grid(row=0, column=0, sticky="ew")
        search_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(search_frame, text="Suchen:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        search_entry = ttk.Entry(search_frame)
        search_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # --- Existing Crimes Section ---
        listbox_frame = ttk.LabelFrame(dialog, text="Vorhandene Straftaten", padding="10")
        listbox_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10) # Adjusted row
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)

        # Use a frame for checkboxes
        checkbox_container = ttk.Frame(listbox_frame)
        checkbox_container.grid(row=0, column=0, sticky="nsew")
        checkbox_container.grid_columnconfigure(0, weight=1) # Allow checkboxes to expand

        # This will hold ALL BooleanVars for ALL predefined crimes, keyed by a unique identifier
        all_crimes_vars = {} 
        # Initialize all_crimes_vars once when the dialog is created
        for i, crime_obj in enumerate(self.predefined_crimes):
            # Use a tuple (name, paragraph) as a unique key for each crime object
            crime_key = (crime_obj['name'], crime_obj.get('paragraph', ''))
            var = tk.BooleanVar(value=False)
            # Set initial state based on current_selection_list
            if any(c.get('name') == crime_obj.get('name') and c.get('paragraph') == crime_obj.get('paragraph') for c in current_selection_list):
                var.set(True)
            all_crimes_vars[crime_key] = var

        # Add a scrollbar to the checkbox container if needed
        canvas_for_checkboxes = tk.Canvas(checkbox_container, bg='#f0f0f0') # Design: Canvas bg
        canvas_for_checkboxes.grid(row=0, column=0, sticky="nsew")
        
        inner_frame = ttk.Frame(canvas_for_checkboxes)
        canvas_for_checkboxes.create_window((0, 0), window=inner_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas_for_checkboxes.configure(scrollregion=canvas_for_checkboxes.bbox("all"))

        inner_frame.bind("<Configure>", _on_frame_configure)

        def populate_checkboxes(filter_text=""):
            # Clear existing checkboxes
            for widget in inner_frame.winfo_children():
                widget.destroy()

            filtered_crimes = [
                crime_obj for crime_obj in self.predefined_crimes
                if filter_text.lower() in crime_obj['name'].lower() or \
                   (crime_obj.get('paragraph') and filter_text.lower() in crime_obj['paragraph'].lower())
            ]
            
            for i, crime_obj in enumerate(filtered_crimes):
                crime_key = (crime_obj['name'], crime_obj.get('paragraph', ''))
                var = all_crimes_vars[crime_key] # Get the existing BooleanVar
                display_text = f"{crime_obj['name']} ({crime_obj['paragraph']})" if crime_obj.get('paragraph') else crime_obj['name']
                
                cb = ttk.Checkbutton(inner_frame, text=display_text, variable=var)
                cb.pack(anchor="w", padx=5, pady=1)

            _on_frame_configure(None) # Update scrollregion

        search_entry.bind("<KeyRelease>", lambda event: populate_checkboxes(search_entry.get()))
        populate_checkboxes() # Initial population

        v_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=canvas_for_checkboxes.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        canvas_for_checkboxes.config(yscrollcommand=v_scrollbar.set)
        
        # --- Add New Crime Section ---
        add_crime_frame = ttk.LabelFrame(dialog, text="Neue Straftat hinzufügen", padding="10")
        add_crime_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10) # Adjusted row
        add_crime_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(add_crime_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        new_crime_name_entry = ttk.Entry(add_crime_frame)
        new_crime_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(add_crime_frame, text="Paragraph:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        new_crime_paragraph_entry = ttk.Entry(add_crime_frame)
        new_crime_paragraph_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(add_crime_frame, text="Hafteinheiten:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        new_crime_detention_entry = ttk.Entry(add_crime_frame)
        new_crime_detention_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        new_crime_detention_entry.insert(0, "0") # Default value

        ttk.Label(add_crime_frame, text="Geldstrafe:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        new_crime_fine_entry = ttk.Entry(add_crime_frame)
        new_crime_fine_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        new_crime_fine_entry.insert(0, "0") # Default value


        def add_new_crime_to_predefined():
            name = new_crime_name_entry.get().strip()
            paragraph = new_crime_paragraph_entry.get().strip()
            detention = new_crime_detention_entry.get().strip()
            fine = new_crime_fine_entry.get().strip()

            if not name:
                messagebox.showwarning("Eingabefehler", "Name der Straftat darf nicht leer sein.", parent=dialog)
                return
            
            try:
                detention = int(detention)
                fine = int(fine)
            except ValueError:
                messagebox.showwarning("Eingabefehler", "Hafteinheiten und Geldstrafe müssen Zahlen sein.", parent=dialog)
                return

            new_crime_obj = {"name": name, "paragraph": paragraph, "detention_units": detention, "fine": fine}
            # Check if crime already exists (case-insensitive name match)
            if any(c['name'].lower() == name.lower() and c.get('paragraph', '').lower() == paragraph.lower() for c in self.predefined_crimes):
                messagebox.showwarning("Warnung", "Diese Straftat existiert bereits.", parent=dialog)
                return

            self.predefined_crimes.append(new_crime_obj)
            self.save_data(self.predefined_crimes, self.predefined_crimes_file)
            
            # Add the new crime's BooleanVar to all_crimes_vars
            new_crime_key = (new_crime_obj['name'], new_crime_obj.get('paragraph', ''))
            all_crimes_vars[new_crime_key] = tk.BooleanVar(value=False) # Initially not selected

            # Re-populate checkboxes to include the new crime
            populate_checkboxes(search_entry.get())

            new_crime_name_entry.delete(0, tk.END)
            new_crime_paragraph_entry.delete(0, tk.END)
            new_crime_detention_entry.delete(0, tk.END)
            new_crime_fine_entry.delete(0, tk.END)
            new_crime_detention_entry.insert(0, "0")
            new_crime_fine_entry.insert(0, "0")
            messagebox.showinfo("Erfolg", "Neue Straftat hinzugefügt!", parent=dialog)

        ttk.Button(add_crime_frame, text="Straftat hinzufügen", command=add_new_crime_to_predefined).grid(row=4, column=0, columnspan=2, pady=5)

        # --- Dialog Buttons ---
        # Define on_ok and on_cancel here, before they are used by the buttons
        def on_ok():
            selected_crimes_from_dialog = []
            for crime_obj_in_list in self.predefined_crimes: # Iterate through the full list of crimes
                crime_key = (crime_obj_in_list['name'], crime_obj_in_list.get('paragraph', ''))
                if crime_key in all_crimes_vars and all_crimes_vars[crime_key].get():
                    selected_crimes_from_dialog.append(crime_obj_in_list)
            
            current_selection_list[:] = selected_crimes_from_dialog
            
            target_label_widget.config(text=self.format_crime_list(selected_crimes_from_dialog))
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, pady=10) # Adjusted row
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=on_cancel).pack(side="left", padx=5)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel) # Handle window close

    def format_crime_list(self, crimes_list_of_dicts):
        """Formats a list of crimes (dictionaries) for display."""
        if not crimes_list_of_dicts:
            return "Keine Straftaten ausgewählt"
        
        formatted_crimes = []
        for crime_obj in crimes_list_of_dicts:
            # Ensure crime_obj is a dictionary. If it's a string (from old data), convert it.
            if isinstance(crime_obj, str):
                crime_obj = {"name": crime_obj, "paragraph": "", "detention_units": 0, "fine": 0}

            if crime_obj.get("paragraph"):
                formatted_crimes.append(f"{crime_obj['name']} ({crime_obj['paragraph']})")
            else:
                formatted_crimes.append(crime_obj['name'])

        if len(formatted_crimes) == 1:
            return formatted_crimes[0]
        if len(formatted_crimes) == 2:
            return f"{formatted_crimes[0]} und {formatted_crimes[1]}"
        
        all_but_last = ", ".join(formatted_crimes[:-1])
        return f"{all_but_last} und {formatted_crimes[-1]}"

    # --- Reports Tab Functions ---
    def create_reports_tab(self, parent_frame):
        """Erstellt die Widgets für den Anzeigen-Tab."""
        content_frame = self._create_scrollable_tab(parent_frame)
        content_frame.grid_columnconfigure(0, weight=1)

        # --- Design: LabelFrame for grouping ---
        new_report_group = ttk.LabelFrame(content_frame, text="Neue Anzeige hinzufügen", padding="15 10")
        new_report_group.grid(row=0, column=0, columnspan=3, pady=10, padx=10, sticky="ew")
        new_report_group.grid_columnconfigure(1, weight=1)

        ttk.Label(new_report_group, text="Anzeigen-ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.new_report_id_entry = ttk.Entry(new_report_group)
        self.new_report_id_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(new_report_group, text="Generieren", command=lambda: self.new_report_id_entry.delete(0, tk.END) or self.new_report_id_entry.insert(0, self.generate_random_case_number())).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(new_report_group, text="Tätername:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.new_report_perpetrator_name_entry = ttk.Entry(new_report_group)
        self.new_report_perpetrator_name_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(new_report_group, text="Typ:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.new_report_type_entry = ttk.Entry(new_report_group)
        self.new_report_type_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(new_report_group, text="Straftaten:").grid(row=3, column=0, sticky="nw", padx=5, pady=2)
        report_crimes_frame = ttk.Frame(new_report_group)
        report_crimes_frame.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        report_crimes_frame.grid_columnconfigure(0, weight=1)
        self.new_report_selected_crimes = []
        self.new_report_crimes_display_label = ttk.Label(report_crimes_frame, text="Keine Straftaten ausgewählt", anchor="w", wraplength=300)
        self.new_report_crimes_display_label.grid(row=0, column=0, sticky="ew")
        ttk.Button(report_crimes_frame, text="Auswählen", command=lambda: self.open_crime_selection_dialog(self.new_report_selected_crimes, self.new_report_crimes_display_label)).grid(row=0, column=1, sticky="e", padx=(5,0))

        ttk.Label(new_report_group, text="Beschreibung:").grid(row=4, column=0, sticky="nw", padx=5, pady=2)
        self.new_report_description_text = scrolledtext.ScrolledText(new_report_group, wrap=tk.WORD, height=6, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.new_report_description_text.grid(row=4, column=1, sticky="ew", padx=5, pady=2)
        
        add_report_button = ttk.Button(new_report_group, text="Anzeige hinzufügen", command=self.add_report)
        add_report_button.grid(row=5, column=0, columnspan=3, pady=10)

        # --- Design: LabelFrame for grouping ---
        reports_list_group = ttk.LabelFrame(content_frame, text="Ihre Anzeigen", padding="15 10")
        reports_list_group.grid(row=1, column=0, columnspan=3, pady=10, padx=10, sticky="nsew")
        reports_list_group.grid_rowconfigure(0, weight=1)
        reports_list_group.grid_columnconfigure(0, weight=1)

        self.reports_listbox = tk.Listbox(reports_list_group, selectmode=tk.SINGLE, font=("Arial", 10), bg='#ffffff', fg='#333333', selectbackground='#cceeff', selectforeground='#333333', relief="flat", borderwidth=1) # Design: Listbox bg/fg/selection/relief
        self.reports_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.reports_listbox.bind('<<ListboxSelect>>', self.display_selected_report)
        reports_scrollbar = ttk.Scrollbar(reports_list_group, orient="vertical", command=self.reports_listbox.yview)
        reports_scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        self.reports_listbox.config(yscrollcommand=reports_scrollbar.set)

        button_frame = ttk.Frame(reports_list_group)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        edit_report_button = ttk.Button(button_frame, text="Anzeige bearbeiten", command=self.start_editing_report)
        edit_report_button.grid(row=0, column=0, padx=5, sticky="ew")
        delete_report_button = ttk.Button(button_frame, text="Anzeige löschen", command=self.delete_report)
        delete_report_button.grid(row=0, column=1, padx=5, sticky="ew")

        # --- Design: LabelFrame for grouping ---
        selected_report_group = ttk.LabelFrame(content_frame, text="Ausgewählte Anzeige", padding="15 10")
        selected_report_group.grid(row=2, column=0, columnspan=3, pady=10, padx=10, sticky="nsew")
        selected_report_group.grid_rowconfigure(0, weight=1)
        selected_report_group.grid_columnconfigure(0, weight=1)

        self.selected_report_content_text = scrolledtext.ScrolledText(selected_report_group, wrap=tk.WORD, height=8, state='disabled', bg='#ffffff', fg='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.selected_report_content_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.populate_reports_list()

    def populate_reports_list(self):
        """Populates the reports listbox with data."""
        self.reports_listbox.delete(0, tk.END)
        for report in self.reports:
            self.reports_listbox.insert(tk.END, f"{report['report_id']} - {report['perpetrator_name']} ({report['type']})")

    def display_selected_report(self, event):
        """Displays the content of the selected report."""
        selected_indices = self.reports_listbox.curselection()
        if not selected_indices: return
        index = selected_indices[0]
        selected_report = self.reports[index]
        content = (f"Anzeigen-ID: {selected_report.get('report_id', 'N/A')}\n"
                   f"Tätername: {selected_report.get('perpetrator_name', 'N/A')}\n"
                   f"Typ: {selected_report.get('type', 'N/A')}\n"
                   f"Straftaten: {self.format_crime_list(selected_report.get('crimes_committed', []))}\n"
                   f"Beschreibung: {selected_report.get('description', 'N/A')}\n"
                   f"Erstellt: {datetime.fromisoformat(selected_report['timestamp']).strftime('%d.%m.%Y %H:%M Uhr') if 'timestamp' in selected_report else 'N/A'}")
        self.selected_report_content_text.config(state='normal')
        self.selected_report_content_text.delete(1.0, tk.END)
        self.selected_report_content_text.insert(tk.END, content)
        self.selected_report_content_text.config(state='disabled')

    def add_report(self):
        """Adds a new report and links/creates a perpetrator file."""
        report_id = self.new_report_id_entry.get().strip()
        perpetrator_name = self.new_report_perpetrator_name_entry.get().strip()
        report_type = self.new_report_type_entry.get().strip()
        crimes_committed = self.new_report_selected_crimes # List of crime dicts
        description = self.new_report_description_text.get(1.0, tk.END).strip()

        if not report_id or not perpetrator_name or not report_type or not crimes_committed:
            messagebox.showwarning("Eingabefehler", "Anzeigen-ID, Tätername, Typ und Straftaten dürfen nicht leer sein.")
            return
        
        # Find or create perpetrator file
        perpetrator_file = self.get_perpetrator_by_name(perpetrator_name)
        if not perpetrator_file:
            # Create new perpetrator file
            perpetrator_file = {
                "id": str(uuid.uuid4()),
                "name": perpetrator_name,
                "dob": "", "birthplace": "", "description": "", "image_filename": None, # Changed address to birthplace
                "timestamp": datetime.now().isoformat(),
                "total_detention_units": 0,
                "total_fine": 0,
                "linked_report_ids": []
            }
            self.perpetrator_files.append(perpetrator_file)
            messagebox.showinfo("Täterakte erstellt", f"Neue Täterakte für '{perpetrator_name}' wurde automatisch erstellt.")
        
        # Calculate penalties for this report
        report_detention_units = sum(c.get('detention_units', 0) for c in crimes_committed)
        report_fine = sum(c.get('fine', 0) for c in crimes_committed)

        # Update perpetrator file with accumulated penalties and linked report
        perpetrator_file['total_detention_units'] += report_detention_units
        perpetrator_file['total_fine'] += report_fine
        
        new_report_id = str(uuid.uuid4()) # Generate unique ID for the report itself
        perpetrator_file['linked_report_ids'].append(new_report_id)

        self.reports.append({
            "id": new_report_id,
            "report_id": report_id, # The user-defined ID
            "perpetrator_name": perpetrator_name,
            "type": report_type,
            "crimes_committed": crimes_committed,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "linked_perpetrator_id": perpetrator_file['id']
        })
        self.save_data(self.reports, self.reports_file)
        self.save_data(self.perpetrator_files, self.perpetrator_files_json) # Save updated perpetrator file

        self.populate_reports_list()
        self.populate_perpetrator_files_list() # Update perpetrator list in its tab

        self.new_report_id_entry.delete(0, tk.END)
        self.new_report_perpetrator_name_entry.delete(0, tk.END)
        self.new_report_type_entry.delete(0, tk.END)
        self.new_report_selected_crimes = []
        self.new_report_crimes_display_label.config(text="Keine Straftaten ausgewählt")
        self.new_report_description_text.delete(1.0, tk.END)
        messagebox.showinfo("Erfolg", "Anzeige erfolgreich hinzugefügt und Täterakte aktualisiert/erstellt!")

    def start_editing_report(self):
        """Prepares a report for editing."""
        selected_indices = self.reports_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Anzeige zum Bearbeiten aus.")
            return
        index = selected_indices[0]
        report = self.reports[index]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Anzeige bearbeiten")
        edit_window.geometry("700x600")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.grid_rowconfigure(5, weight=1) # Description
        edit_window.grid_columnconfigure(1, weight=1)

        ttk.Label(edit_window, text="Anzeigen-ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        edit_report_id_entry = ttk.Entry(edit_window)
        edit_report_id_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        edit_report_id_entry.insert(0, report['report_id'])

        ttk.Label(edit_window, text="Tätername:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        edit_perpetrator_name_entry = ttk.Entry(edit_window)
        edit_perpetrator_name_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        edit_perpetrator_name_entry.insert(0, report['perpetrator_name'])

        ttk.Label(edit_window, text="Typ:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        edit_report_type_entry = ttk.Entry(edit_window)
        edit_report_type_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        edit_report_type_entry.insert(0, report['type'])

        ttk.Label(edit_window, text="Straftaten:").grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        edit_report_crimes_frame = ttk.Frame(edit_window)
        edit_report_crimes_frame.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        edit_report_crimes_frame.grid_columnconfigure(0, weight=1)
        
        self.edit_report_selected_crimes_var = list(report['crimes_committed'])
        edit_report_crimes_display_label = ttk.Label(edit_report_crimes_frame, text=self.format_crime_list(self.edit_report_selected_crimes_var), anchor="w", wraplength=300)
        edit_report_crimes_display_label.grid(row=0, column=0, sticky="ew")
        ttk.Button(edit_report_crimes_frame, text="Auswählen", command=lambda: self.open_crime_selection_dialog(self.edit_report_selected_crimes_var, edit_report_crimes_display_label)).grid(row=0, column=1, sticky="e", padx=(5,0))

        ttk.Label(edit_window, text="Beschreibung:").grid(row=4, column=0, sticky="nw", padx=5, pady=5)
        edit_description_text = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD, height=10, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        edit_description_text.grid(row=4, column=1, sticky="nsew", padx=5, pady=5)
        edit_description_text.insert(1.0, report['description'])

        def save_edited_report():
            old_perpetrator_id = report.get('linked_perpetrator_id')
            old_crimes = list(report.get('crimes_committed', [])) # Copy for comparison

            new_report_id = edit_report_id_entry.get().strip()
            new_perpetrator_name = edit_perpetrator_name_entry.get().strip()
            new_report_type = edit_report_type_entry.get().strip()
            new_crimes_committed = self.edit_report_selected_crimes_var # Get from dialog
            new_description = edit_description_text.get(1.0, tk.END).strip()

            if not new_report_id or not new_perpetrator_name or not new_report_type or not new_crimes_committed:
                messagebox.showwarning("Eingabefehler", "Anzeigen-ID, Tätername, Typ und Straftaten dürfen nicht leer sein.", parent=edit_window)
                return
            
            # --- Handle perpetrator file updates ---
            # 1. Revert old perpetrator's penalties if perpetrator name changed or crimes changed
            if old_perpetrator_id:
                old_perpetrator_file = next((pf for pf in self.perpetrator_files if pf['id'] == old_perpetrator_id), None)
                if old_perpetrator_file:
                    old_report_detention = sum(c.get('detention_units', 0) for c in old_crimes)
                    old_report_fine = sum(c.get('fine', 0) for c in old_crimes)
                    old_perpetrator_file['total_detention_units'] -= old_report_detention
                    old_perpetrator_file['total_fine'] -= old_report_fine
                    if report['id'] in old_perpetrator_file['linked_report_ids']:
                        old_perpetrator_file['linked_report_ids'].remove(report['id'])

            # 2. Find or create new perpetrator file
            new_perpetrator_file = self.get_perpetrator_by_name(new_perpetrator_name)
            if not new_perpetrator_file:
                new_perpetrator_file = {
                    "id": str(uuid.uuid4()),
                    "name": new_perpetrator_name,
                    "dob": "", "birthplace": "", "description": "", "image_filename": None, # Changed address to birthplace
                    "timestamp": datetime.now().isoformat(),
                    "total_detention_units": 0,
                    "total_fine": 0,
                    "linked_report_ids": []
                }
                self.perpetrator_files.append(new_perpetrator_file)

            # 3. Apply new report's penalties to the new/updated perpetrator file
            new_report_detention = sum(c.get('detention_units', 0) for c in new_crimes_committed)
            new_report_fine = sum(c.get('fine', 0) for c in new_crimes_committed)
            new_perpetrator_file['total_detention_units'] += new_report_detention
            new_perpetrator_file['total_fine'] += new_report_fine
            if report['id'] not in new_perpetrator_file['linked_report_ids']:
                new_perpetrator_file['linked_report_ids'].append(report['id'])


            # Update report details
            report['report_id'] = new_report_id
            report['perpetrator_name'] = new_perpetrator_name
            report['type'] = new_report_type
            report['crimes_committed'] = new_crimes_committed
            report['description'] = new_description
            report['linked_perpetrator_id'] = new_perpetrator_file['id']

            self.save_data(self.reports, self.reports_file)
            self.save_data(self.perpetrator_files, self.perpetrator_files_json) # Save updated perpetrator files

            self.populate_reports_list()
            self.populate_perpetrator_files_list() # Refresh perpetrator list in its tab
            self.display_selected_report(None)
            messagebox.showinfo("Erfolg", "Anzeige erfolgreich aktualisiert und Täterakte angepasst!", parent=edit_window)
            edit_window.destroy()
        ttk.Button(edit_window, text="Speichern", command=save_edited_report).grid(row=6, column=0, columnspan=2, pady=10)

    def delete_report(self):
        """Deletes the selected report and updates the linked perpetrator file."""
        selected_indices = self.reports_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Anzeige zum Löschen aus.")
            return
        index = selected_indices[0]
        report_to_delete = self.reports[index]

        if messagebox.askyesno("Bestätigen", "Möchten Sie diese Anzeige wirklich löschen? Die zugehörigen Strafen werden von der Täterakte abgezogen."):
            # Revert penalties from linked perpetrator file
            perpetrator_id = report_to_delete.get('linked_perpetrator_id')
            if perpetrator_id:
                perpetrator_file = next((pf for pf in self.perpetrator_files if pf['id'] == perpetrator_id), None)
                if perpetrator_file:
                    report_detention = sum(c.get('detention_units', 0) for c in report_to_delete.get('crimes_committed', []))
                    report_fine = sum(c.get('fine', 0) for c in report_to_delete.get('crimes_committed', []))
                    perpetrator_file['total_detention_units'] -= report_detention
                    perpetrator_file['total_fine'] -= report_fine
                    if report_to_delete['id'] in perpetrator_file['linked_report_ids']:
                        perpetrator_file['linked_report_ids'].remove(report_to_delete['id'])
                    self.save_data(self.perpetrator_files, self.perpetrator_files_json) # Save updated perpetrator file

            del self.reports[index]
            self.save_data(self.reports, self.reports_file)
            self.populate_reports_list()
            self.populate_perpetrator_files_list() # Update perpetrator list in its tab
            self.selected_report_content_text.config(state='normal')
            self.selected_report_content_text.delete(1.0, tk.END)
            self.selected_report_content_text.config(state='disabled')
            messagebox.showinfo("Erfolg", "Anzeige erfolgreich gelöscht und Täterakte angepasst!")

    # --- Perpetrator Files Tab Functions ---
    def create_perpetrator_files_tab(self, parent_frame):
        """Erstellt die Widgets für den Täterakten-Tab."""
        content_frame = self._create_scrollable_tab(parent_frame)
        # Input section
        input_frame = ttk.LabelFrame(content_frame, text="Neue Täterakte hinzufügen", padding="15 10") # Design: LabelFrame
        input_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=10, padx=10)
        input_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.new_pf_name_entry = ttk.Entry(input_frame)
        self.new_pf_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(input_frame, text="Geburtsdatum:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.new_pf_dob_entry = ttk.Entry(input_frame)
        self.new_pf_dob_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(input_frame, text="Geburtsort:").grid(row=2, column=0, sticky="w", padx=5, pady=2) # Changed label
        self.new_pf_birthplace_entry = ttk.Entry(input_frame) # Changed variable name
        self.new_pf_birthplace_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(input_frame, text="Beschreibung:").grid(row=3, column=0, sticky="nw", padx=5, pady=2)
        self.new_pf_description_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=5, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.new_pf_description_text.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        # Image section within input frame
        image_input_frame = ttk.Frame(input_frame)
        image_input_frame.grid(row=0, column=2, rowspan=4, padx=10, pady=5, sticky="nsew") # Adjusted row/column for better layout
        image_input_frame.grid_rowconfigure(0, weight=1)
        image_input_frame.grid_columnconfigure(0, weight=1)

        self.perpetrator_image_label = ttk.Label(image_input_frame, text="[Kein Bild]", anchor="center")
        self.perpetrator_image_label.grid(row=0, column=0, sticky="nsew")
        self.perpetrator_image_label.bind("<Configure>", self.resize_perpetrator_image)

        ttk.Button(image_input_frame, text="Bild auswählen", command=self.select_perpetrator_image).grid(row=1, column=0, pady=2, sticky="ew")
        ttk.Button(image_input_frame, text="Bild entfernen", command=self.clear_perpetrator_image).grid(row=2, column=0, pady=2, sticky="ew")

        add_pf_button = ttk.Button(input_frame, text="Täterakte hinzufügen", command=self.add_perpetrator_file)
        add_pf_button.grid(row=4, column=0, columnspan=3, pady=10) # Adjusted row

        # List and display section
        list_display_frame = ttk.LabelFrame(content_frame, text="Ihre Täterakten", padding="15 10") # Design: LabelFrame
        list_display_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=10, padx=10)
        list_display_frame.grid_rowconfigure(1, weight=1)
        list_display_frame.grid_columnconfigure(0, weight=1)

        self.perpetrator_files_listbox = tk.Listbox(list_display_frame, selectmode=tk.SINGLE, font=("Arial", 10), bg='#ffffff', fg='#333333', selectbackground='#cceeff', selectforeground='#333333', relief="flat", borderwidth=1) # Design: Listbox bg/fg/selection/relief
        self.perpetrator_files_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.perpetrator_files_listbox.bind('<<ListboxSelect>>', self.display_selected_perpetrator_file)
        pf_scrollbar = ttk.Scrollbar(list_display_frame, orient="vertical", command=self.perpetrator_files_listbox.yview)
        pf_scrollbar.grid(row=1, column=1, sticky="ns", pady=5)
        self.perpetrator_files_listbox.config(yscrollcommand=pf_scrollbar.set)

        button_frame = ttk.Frame(list_display_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        edit_pf_button = ttk.Button(button_frame, text="Täterakte bearbeiten", command=self.start_editing_perpetrator_file)
        edit_pf_button.grid(row=0, column=0, padx=5, sticky="ew")
        delete_pf_button = ttk.Button(button_frame, text="Täterakte löschen", command=self.delete_perpetrator_file)
        delete_pf_button.grid(row=0, column=1, padx=5, sticky="ew")

        selected_pf_group = ttk.LabelFrame(content_frame, text="Ausgewählte Täterakte", padding="15 10") # Design: LabelFrame
        selected_pf_group.grid(row=2, column=0, columnspan=3, pady=10, padx=10, sticky="nsew")
        selected_pf_group.grid_rowconfigure(0, weight=1)
        selected_pf_group.grid_columnconfigure(0, weight=1)

        self.selected_pf_content_text = scrolledtext.ScrolledText(selected_pf_group, wrap=tk.WORD, height=8, state='disabled', bg='#ffffff', fg='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.selected_pf_content_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.populate_perpetrator_files_list()
        self.load_placeholder_image_pf() # Load placeholder on startup for this tab

    def populate_perpetrator_files_list(self):
        """Populates the perpetrator files listbox with data."""
        self.perpetrator_files_listbox.delete(0, tk.END)
        for pf in self.perpetrator_files:
            self.perpetrator_files_listbox.insert(tk.END, f"{pf['name']} ({pf.get('dob', 'N/A')})")

    def display_selected_perpetrator_file(self, event):
        """Displays the content of the selected perpetrator file."""
        selected_indices = self.perpetrator_files_listbox.curselection()
        if not selected_indices: return
        index = selected_indices[0]
        selected_pf = self.perpetrator_files[index]

        # Get linked reports for display
        linked_reports_info = []
        for report_id in selected_pf.get('linked_report_ids', []):
            report = next((r for r in self.reports if r['id'] == report_id), None)
            if report:
                linked_reports_info.append(f"  - {report['report_id']} ({report['type']}): {self.format_crime_list(report.get('crimes_committed', []))}")
        
        content = (f"Name: {selected_pf.get('name', 'N/A')}\n"
                   f"Geburtsdatum: {selected_pf.get('dob', 'N/A')}\n"
                   f"Geburtsort: {selected_pf.get('birthplace', 'N/A')}\n" # Changed to birthplace
                   f"Beschreibung: {selected_pf.get('description', 'N/A')}\n"
                   f"Gesamt-Hafteinheiten: {selected_pf.get('total_detention_units', 0)}\n"
                   f"Gesamt-Geldstrafe: {selected_pf.get('total_fine', 0)} €\n"
                   f"Erstellt: {datetime.fromisoformat(selected_pf['timestamp']).strftime('%d.%m.%Y %H:%M Uhr') if 'timestamp' in selected_pf else 'N/A'}\n"
                   f"Zugeordnete Anzeigen:\n" + "\n".join(linked_reports_info if linked_reports_info else ["  - Keine"]))
        
        self.selected_pf_content_text.config(state='normal')
        self.selected_pf_content_text.delete(1.0, tk.END)
        self.selected_pf_content_text.insert(tk.END, content)
        self.selected_pf_content_text.config(state='disabled')

        # Display perpetrator image
        image_filename = selected_pf.get('image_filename')
        if image_filename:
            self.current_perpetrator_image_path = os.path.join(self.perpetrator_images_dir, image_filename)
        else:
            self.current_perpetrator_image_path = None
        self.display_perpetrator_image()

    def add_perpetrator_file(self):
        """Adds a new perpetrator file."""
        name = self.new_pf_name_entry.get().strip()
        dob = self.new_pf_dob_entry.get().strip()
        birthplace = self.new_pf_birthplace_entry.get().strip() # Changed variable name
        description = self.new_pf_description_text.get(1.0, tk.END).strip()

        if not name:
            messagebox.showwarning("Eingabefehler", "Name des Täters darf nicht leer sein.")
            return
        
        if self.get_perpetrator_by_name(name):
            messagebox.showwarning("Warnung", f"Eine Täterakte für '{name}' existiert bereits. Bitte verwenden Sie einen eindeutigen Namen oder bearbeiten Sie die bestehende Akte.")
            return

        image_filename = None
        # The image is already saved as a UUID.png in the perpetrator_images_dir by select_perpetrator_image
        if self.current_perpetrator_image_path and os.path.exists(self.current_perpetrator_image_path):
            image_filename = os.path.basename(self.current_perpetrator_image_path)

        self.perpetrator_files.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "dob": dob,
            "birthplace": birthplace, # Changed field name
            "description": description,
            "image_filename": image_filename,
            "timestamp": datetime.now().isoformat(),
            "total_detention_units": 0, # Initialize
            "total_fine": 0, # Initialize
            "linked_report_ids": [] # Initialize
        })
        self.save_data(self.perpetrator_files, self.perpetrator_files_json)
        self.populate_perpetrator_files_list()
        self.new_pf_name_entry.delete(0, tk.END)
        self.new_pf_dob_entry.delete(0, tk.END)
        self.new_pf_birthplace_entry.delete(0, tk.END) # Changed variable name
        self.new_pf_description_text.delete(1.0, tk.END)
        self.clear_perpetrator_image() # Clear image selection after adding
        messagebox.showinfo("Erfolg", "Täterakte erfolgreich hinzugefügt!")

    def start_editing_perpetrator_file(self):
        """Prepares a perpetrator file for editing."""
        selected_indices = self.perpetrator_files_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Täterakte zum Bearbeiten aus.")
            return
        index = selected_indices[0]
        pf_record = self.perpetrator_files[index]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Täterakte bearbeiten")
        edit_window.geometry("700x600")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.grid_rowconfigure(4, weight=1) # Description
        edit_window.grid_columnconfigure(1, weight=1) # Input fields

        ttk.Label(edit_window, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        edit_name_entry = ttk.Entry(edit_window)
        edit_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        edit_name_entry.insert(0, pf_record['name'])
        ttk.Label(edit_window, text="Geburtsdatum:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        edit_dob_entry = ttk.Entry(edit_window)
        edit_dob_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        edit_dob_entry.insert(0, pf_record.get('dob', ''))
        ttk.Label(edit_window, text="Geburtsort:").grid(row=2, column=0, sticky="w", padx=5, pady=5) # Changed label
        edit_birthplace_entry = ttk.Entry(edit_window) # Changed variable name
        edit_birthplace_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        edit_birthplace_entry.insert(0, pf_record.get('birthplace', pf_record.get('address', ''))) # Migrate old 'address' to 'birthplace' for display
        ttk.Label(edit_window, text="Beschreibung:").grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        edit_description_text = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD, height=10, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        edit_description_text.grid(row=3, column=1, sticky="nsew", padx=5, pady=5)
        edit_description_text.insert(1.0, pf_record.get('description', ''))

        # Image section in edit window
        image_edit_frame = ttk.Frame(edit_window)
        image_edit_frame.grid(row=0, column=2, rowspan=5, padx=10, pady=5, sticky="nsew")
        image_edit_frame.grid_rowconfigure(0, weight=1)
        image_edit_frame.grid_columnconfigure(0, weight=1)

        self.edit_perpetrator_image_label = ttk.Label(image_edit_frame, text="[Kein Bild]", anchor="center")
        self.edit_perpetrator_image_label.grid(row=0, column=0, sticky="nsew")
        self.edit_perpetrator_image_label.bind("<Configure>", self.resize_edit_perpetrator_image)

        # Load current image for editing
        current_image_filename = pf_record.get('image_filename')
        self.current_edit_perpetrator_image_path = None
        if current_image_filename:
            self.current_edit_perpetrator_image_path = os.path.join(self.perpetrator_images_dir, current_image_filename)
        self.display_edit_perpetrator_image()

        ttk.Button(image_edit_frame, text="Neues Bild auswählen", command=lambda: self.select_edit_perpetrator_image(pf_record)).grid(row=1, column=0, pady=2, sticky="ew")
        ttk.Button(image_edit_frame, text="Bild entfernen", command=lambda: self.clear_edit_perpetrator_image(pf_record)).grid(row=2, column=0, pady=2, sticky="ew")


        def save_edited_pf():
            new_name = edit_name_entry.get().strip()
            new_dob = edit_dob_entry.get().strip()
            new_birthplace = edit_birthplace_entry.get().strip() # Changed variable name
            new_description = edit_description_text.get(1.0, tk.END).strip()
            
            # Prevent changing name to an existing one (unless it's the same record)
            existing_pf = self.get_perpetrator_by_name(new_name)
            if existing_pf and existing_pf['id'] != pf_record['id']:
                messagebox.showwarning("Warnung", f"Eine Täterakte für '{new_name}' existiert bereits. Bitte verwenden Sie einen eindeutigen Namen.", parent=edit_window)
                return

            if not new_name:
                messagebox.showwarning("Eingabefehler", "Name des Täters darf nicht leer sein.", parent=edit_window)
                return

            # If name changed, update linked reports
            if new_name != pf_record['name']:
                for report in self.reports:
                    if report.get('linked_perpetrator_id') == pf_record['id']:
                        report['perpetrator_name'] = new_name
                self.save_data(self.reports, self.reports_file) # Save reports after updating

            pf_record['name'] = new_name
            pf_record['dob'] = new_dob
            pf_record['birthplace'] = new_birthplace # Changed field name
            pf_record['description'] = new_description

            # Handle image update/deletion
            if self.current_edit_perpetrator_image_path and os.path.exists(self.current_edit_perpetrator_image_path):
                # If a new image was selected and cropped, its path will be different from the old one
                if os.path.basename(self.current_edit_perpetrator_image_path) != pf_record.get('image_filename'):
                    # Delete old image if it existed
                    if pf_record.get('image_filename') and os.path.exists(os.path.join(self.perpetrator_images_dir, pf_record['image_filename'])):
                        os.remove(os.path.join(self.perpetrator_images_dir, pf_record['image_filename']))
                    # The new image is already saved by select_edit_perpetrator_image, just update the filename in record
                    pf_record['image_filename'] = os.path.basename(self.current_edit_perpetrator_image_path)
            else: # Image was cleared or never existed
                if pf_record.get('image_filename') and os.path.exists(os.path.join(self.perpetrator_images_dir, pf_record['image_filename'])):
                    os.remove(os.path.join(self.perpetrator_images_dir, pf_record['image_filename']))
                pf_record['image_filename'] = None


            self.save_data(self.perpetrator_files, self.perpetrator_files_json)
            self.populate_perpetrator_files_list()
            self.display_selected_perpetrator_file(None) # Refresh display
            messagebox.showinfo("Erfolg", "Täterakte erfolgreich aktualisiert!", parent=edit_window)
            edit_window.destroy()

        ttk.Button(edit_window, text="Speichern", command=save_edited_pf).grid(row=5, column=0, columnspan=3, pady=10)

    def delete_perpetrator_file(self):
        """Löscht die ausgewählte Täterakte."""
        selected_indices = self.perpetrator_files_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Täterakte zum Löschen aus.")
            return
        index = selected_indices[0]
        pf_record = self.perpetrator_files[index]

        if messagebox.askyesno("Bestätigen", "Möchten Sie diese Täterakte wirklich löschen? Alle verknüpften Anzeigen bleiben bestehen, verlieren aber die Verknüpfung."):
            # Remove link from reports that point to this perpetrator
            for report in self.reports:
                if report.get('linked_perpetrator_id') == pf_record['id']:
                    report['linked_perpetrator_id'] = None # Break the link
            self.save_data(self.reports, self.reports_file) # Save updated reports

            # Delete associated image file if it exists
            if pf_record.get('image_filename'):
                image_full_path = os.path.join(self.perpetrator_images_dir, pf_record['image_filename'])
                if os.path.exists(image_full_path):
                    try:
                        os.remove(image_full_path)
                    except Exception as e:
                        print(f"Fehler beim Löschen des Bildes: {e}")
            del self.perpetrator_files[index]
            self.save_data(self.perpetrator_files, self.perpetrator_files_json)
            self.populate_perpetrator_files_list()
            self.selected_pf_content_text.config(state='normal')
            self.selected_pf_content_text.delete(1.0, tk.END)
            self.selected_pf_content_text.config(state='disabled')
            self.clear_perpetrator_image() # Clear display after deletion
            messagebox.showinfo("Erfolg", "Täterakte erfolgreich gelöscht!")

    # Image handling for Perpetrator Files (create/view tab)
    def select_perpetrator_image(self):
        """Öffnet einen Dateidialog zur Auswahl eines Straftäterbildes für die neue Akte und startet den Zuschnitt."""
        file_path = filedialog.askopenfilename(
            title="Straftäterbild auswählen",
            filetypes=[("Bilddateien", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Alle Dateien", "*.*")]
        )
        if file_path:
            try:
                original_pil_image = Image.open(file_path)
                cropper = ImageCropper(self.root, original_pil_image)
                self.root.wait_window(cropper) # Wait for cropper dialog to close
                
                if cropper.cropped_image:
                    # Generate a unique filename for the cropped 150x150 image
                    new_image_filename = f"{uuid.uuid4()}.png" # Always save as PNG for consistency
                    destination_path = os.path.join(self.perpetrator_images_dir, new_image_filename)
                    
                    cropper.cropped_image.save(destination_path)
                    self.current_perpetrator_image_path = destination_path
                    self.display_perpetrator_image()
                else:
                    self.clear_perpetrator_image() # User cancelled cropping
            except Exception as e:
                messagebox.showerror("Bildfehler", f"Fehler beim Laden oder Zuschneiden des Bildes: {e}")
                self.clear_perpetrator_image()
        else:
            self.clear_perpetrator_image() # User cancelled file selection

    def display_perpetrator_image(self):
        """Zeigt das Straftäterbild oder einen Platzhalter im Erstellungs-/Anzeige-Tab an."""
        target_width = self.perpetrator_image_label.winfo_width() if self.perpetrator_image_label.winfo_width() > 0 else 150
        target_height = self.perpetrator_image_label.winfo_height() if self.perpetrator_image_label.winfo_height() > 0 else 150

        if self.current_perpetrator_image_path and os.path.exists(self.current_perpetrator_image_path):
            try:
                # Load the already cropped and resized image
                display_image = Image.open(self.current_perpetrator_image_path)
                # Ensure it's still within label bounds if label is smaller than 150x150
                display_image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                self.perpetrator_photo_image = ImageTk.PhotoImage(display_image)
                self.perpetrator_image_label.config(image=self.perpetrator_photo_image, text="")
            except Exception as e:
                messagebox.showerror("Bildfehler", f"Konnte Bild nicht laden: {e}. Zeige Platzhalter an.")
                self.load_placeholder_image_pf()
        else:
            self.load_placeholder_image_pf()

    def load_placeholder_image_pf(self):
        """Lädt und zeigt ein Platzhalterbild an (Person mit ?) für den Erstellungs-/Anzeige-Tab."""
        try:
            img = Image.new('RGB', (150, 150), color = (200, 200, 200))
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 80)
            except IOError:
                font = ImageFont.load_default()

            d.ellipse((30, 20, 120, 110), fill=(100, 100, 100), outline=(50, 50, 50), width=2)
            d.line((75, 110, 75, 130), fill=(100, 100, 100), width=5)
            d.arc((20, 100, 130, 180), 0, 180, fill=(100, 100, 100), width=5)

            text = "?"
            text_bbox = d.textbbox((0,0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            d.text(((150 - text_width) / 2, (150 - text_height) / 2), text, font=font, fill=(0, 0, 0))

            self.perpetrator_photo_image = ImageTk.PhotoImage(img)
            self.perpetrator_image_label.config(image=self.perpetrator_photo_image, text="")
        except Exception as e:
            print(f"Fehler beim Laden des Platzhalterbildes: {e}")
            self.perpetrator_image_label.config(image="", text="[Unbekannt]")

    def resize_perpetrator_image(self, event):
        """Passt die Größe des Straftäterbildes im Erstellungs-/Anzeige-Tab an."""
        self.display_perpetrator_image()

    def clear_perpetrator_image(self):
        """Entfernt das Straftäterbild und zeigt den Platzhalter im Erstellungs-/Anzeige-Tab an."""
        self.current_perpetrator_image_path = None
        self.perpetrator_photo_image = None
        self.load_placeholder_image_pf()

    # Image handling for Perpetrator Files (edit window)
    def select_edit_perpetrator_image(self, pf_record):
        """Öffnet einen Dateidialog zur Auswahl eines Straftäterbildes für das Bearbeitungsfenster und startet den Zuschnitt."""
        file_path = filedialog.askopenfilename(
            title="Neues Straftäterbild auswählen",
            filetypes=[("Bilddateien", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Alle Dateien", "*.*")]
        )
        if file_path:
            try:
                original_pil_image = Image.open(file_path)
                cropper = ImageCropper(self.root, original_pil_image)
                self.root.wait_window(cropper) # Wait for cropper dialog to close
                
                if cropper.cropped_image:
                    new_image_filename = f"{uuid.uuid4()}.png"
                    destination_path = os.path.join(self.perpetrator_images_dir, new_image_filename)
                    cropper.cropped_image.save(destination_path)
                    self.current_edit_perpetrator_image_path = destination_path
                    self.display_edit_perpetrator_image()
                else:
                    # If user cancelled cropping, revert to the image that was there before opening cropper
                    current_image_filename = pf_record.get('image_filename')
                    if current_image_filename:
                        self.current_edit_perpetrator_image_path = os.path.join(self.perpetrator_images_dir, current_image_filename)
                    else:
                        self.current_edit_perpetrator_image_path = None
                    self.display_edit_perpetrator_image()
            except Exception as e:
                messagebox.showerror("Bildfehler", f"Fehler beim Laden oder Zuschneiden des Bildes: {e}", parent=self.edit_perpetrator_image_label.winfo_toplevel())
                self.clear_edit_perpetrator_image(pf_record)
        else:
            # If user cancelled file selection, revert to the image that was there before opening dialog
            current_image_filename = pf_record.get('image_filename')
            if current_image_filename:
                self.current_edit_perpetrator_image_path = os.path.join(self.perpetrator_images_dir, current_image_filename)
            else:
                self.current_edit_perpetrator_image_path = None
            self.display_edit_perpetrator_image()


    def display_edit_perpetrator_image(self):
        """Zeigt das Straftäterbild oder einen Platzhalter im Bearbeitungsfenster an."""
        target_width = self.edit_perpetrator_image_label.winfo_width() if self.edit_perpetrator_image_label.winfo_width() > 0 else 150
        target_height = self.edit_perpetrator_image_label.winfo_height() if self.edit_perpetrator_image_label.winfo_height() > 0 else 150

        if self.current_edit_perpetrator_image_path and os.path.exists(self.current_edit_perpetrator_image_path):
            try:
                display_image = Image.open(self.current_edit_perpetrator_image_path)
                display_image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                self.edit_perpetrator_photo_image = ImageTk.PhotoImage(display_image)
                self.edit_perpetrator_image_label.config(image=self.edit_perpetrator_photo_image, text="")
            except Exception as e:
                messagebox.showerror("Bildfehler", f"Konnte Bild nicht laden: {e}. Zeige Platzhalter an.", parent=self.edit_perpetrator_image_label.winfo_toplevel())
                self.load_placeholder_image_edit_pf()
        else:
            self.load_placeholder_image_edit_pf()

    def load_placeholder_image_edit_pf(self):
        """Lädt und zeigt ein Platzhalterbild an (Person mit ?) für das Bearbeitungsfenster."""
        try:
            img = Image.new('RGB', (150, 150), color = (200, 200, 200))
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 80)
            except IOError:
                font = ImageFont.load_default()

            d.ellipse((30, 20, 120, 110), fill=(100, 100, 100), outline=(50, 50, 50), width=2)
            d.line((75, 110, 75, 130), fill=(100, 100, 100), width=5)
            d.arc((20, 100, 130, 180), 0, 180, fill=(100, 100, 100), width=5)

            text = "?"
            text_bbox = d.textbbox((0,0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            d.text(((150 - text_width) / 2, (150 - text_height) / 2), text, font=font, fill=(0, 0, 0))

            self.edit_perpetrator_photo_image = ImageTk.PhotoImage(img)
            self.edit_perpetrator_image_label.config(image=self.edit_perpetrator_photo_image, text="")
        except Exception as e:
            print(f"Fehler beim Laden des Platzhalterbildes im Bearbeitungsfenster: {e}")
            self.edit_perpetrator_image_label.config(image="", text="[Unbekannt]")

    def resize_edit_perpetrator_image(self, event):
        """Passt die Größe des Straftäterbildes im Bearbeitungsfenster an."""
        self.display_edit_perpetrator_image()

    def clear_edit_perpetrator_image(self, pf_record):
        """Entfernt das Straftäterbild und zeigt den Platzhalter im Bearbeitungsfenster an."""
        self.current_edit_perpetrator_image_path = None
        self.edit_perpetrator_photo_image = None
        self.load_placeholder_image_edit_pf()

    # --- Manage Crimes Tab Functions (New) ---
    def create_manage_crimes_tab(self, parent_frame):
        """Creates widgets for the Manage Crimes tab."""
        content_frame = self._create_scrollable_tab(parent_frame)
        # Add New Crime Section
        add_crime_frame = ttk.LabelFrame(content_frame, text="Neue Straftat hinzufügen", padding="15 10") # Design: LabelFrame
        add_crime_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        add_crime_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(add_crime_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.manage_crime_name_entry = ttk.Entry(add_crime_frame)
        self.manage_crime_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(add_crime_frame, text="Paragraph:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.manage_crime_paragraph_entry = ttk.Entry(add_crime_frame)
        self.manage_crime_paragraph_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(add_crime_frame, text="Hafteinheiten:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.manage_crime_detention_entry = ttk.Entry(add_crime_frame)
        self.manage_crime_detention_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.manage_crime_detention_entry.insert(0, "0")

        ttk.Label(add_crime_frame, text="Geldstrafe:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.manage_crime_fine_entry = ttk.Entry(add_crime_frame)
        self.manage_crime_fine_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        self.manage_crime_fine_entry.insert(0, "0")

        ttk.Button(add_crime_frame, text="Straftat hinzufügen", command=self.add_predefined_crime).grid(row=4, column=0, columnspan=2, pady=10)

        # List of Predefined Crimes
        list_crimes_frame = ttk.LabelFrame(content_frame, text="Vorhandene Straftaten", padding="15 10") # Design: LabelFrame
        list_crimes_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        list_crimes_frame.grid_rowconfigure(0, weight=1)
        list_crimes_frame.grid_columnconfigure(0, weight=1)

        self.predefined_crimes_listbox = tk.Listbox(list_crimes_frame, selectmode=tk.SINGLE, font=("Arial", 10), bg='#ffffff', fg='#333333', selectbackground='#cceeff', selectforeground='#333333', relief="flat", borderwidth=1) # Design: Listbox bg/fg/selection/relief
        self.predefined_crimes_listbox.grid(row=0, column=0, sticky="nsew")
        self.predefined_crimes_listbox.bind('<<ListboxSelect>>', self.display_selected_predefined_crime)

        crimes_scrollbar = ttk.Scrollbar(list_crimes_frame, orient="vertical", command=self.predefined_crimes_listbox.yview)
        crimes_scrollbar.grid(row=0, column=1, sticky="ns")
        self.predefined_crimes_listbox.config(yscrollcommand=crimes_scrollbar.set)

        # Buttons for editing/deleting predefined crimes
        button_frame = ttk.Frame(list_crimes_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        edit_crime_button = ttk.Button(button_frame, text="Straftat bearbeiten", command=self.start_editing_predefined_crime)
        edit_crime_button.grid(row=0, column=0, padx=5, sticky="ew")
        delete_crime_button = ttk.Button(button_frame, text="Straftat löschen", command=self.delete_predefined_crime)
        delete_crime_button.grid(row=0, column=1, padx=5, sticky="ew")

        self.populate_predefined_crimes_list()

    def populate_predefined_crimes_list(self):
        """Füllt die Listbox der vordefinierten Straftaten."""
        self.predefined_crimes_listbox.delete(0, tk.END)
        for crime_obj in self.predefined_crimes:
            display_text = f"{crime_obj['name']} ({crime_obj.get('paragraph', 'N/A')}) - {crime_obj.get('detention_units', 0)} HE, {crime_obj.get('fine', 0)} €"
            self.predefined_crimes_listbox.insert(tk.END, display_text)

    def display_selected_predefined_crime(self, event):
        """Zeigt Details der ausgewählten vordefinierten Straftat an."""
        selected_indices = self.predefined_crimes_listbox.curselection()
        if not selected_indices: return
        index = selected_indices[0]
        crime_obj = self.predefined_crimes[index]
        # You could display details in a label or text widget if desired,
        # for now, just selecting it in the listbox is enough.

    def add_predefined_crime(self):
        """Fügt eine neue vordefinierte Straftat hinzu."""
        name = self.manage_crime_name_entry.get().strip()
        paragraph = self.manage_crime_paragraph_entry.get().strip()
        detention_units_str = self.manage_crime_detention_entry.get().strip()
        fine_str = self.manage_crime_fine_entry.get().strip()

        if not name:
            messagebox.showwarning("Eingabefehler", "Name der Straftat darf nicht leer sein.")
            return
        
        try:
            detention_units = int(detention_units_str)
            fine = int(fine_str)
        except ValueError:
            messagebox.showwarning("Eingabefehler", "Hafteinheiten und Geldstrafe müssen Zahlen sein.")
            return

        # Check for duplicates (case-insensitive name and paragraph)
        if any(c['name'].lower() == name.lower() and c.get('paragraph', '').lower() == paragraph.lower() for c in self.predefined_crimes):
            messagebox.showwarning("Warnung", "Diese Straftat existiert bereits.")
            return

        self.predefined_crimes.append({
            "name": name,
            "paragraph": paragraph,
            "detention_units": detention_units,
            "fine": fine
        })
        self.save_data(self.predefined_crimes, self.predefined_crimes_file)
        self.populate_predefined_crimes_list()
        self.manage_crime_name_entry.delete(0, tk.END)
        self.manage_crime_paragraph_entry.delete(0, tk.END)
        self.manage_crime_detention_entry.delete(0, tk.END)
        self.manage_crime_fine_entry.delete(0, tk.END)
        self.manage_crime_detention_entry.insert(0, "0")
        self.manage_crime_fine_entry.insert(0, "0")
        messagebox.showinfo("Erfolg", "Straftat erfolgreich hinzugefügt!")

    def start_editing_predefined_crime(self):
        """Bereitet das Bearbeiten einer vordefinierten Straftat vor."""
        selected_indices = self.predefined_crimes_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Straftat zum Bearbeiten aus.")
            return
        index = selected_indices[0]
        crime_obj = self.predefined_crimes[index]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Straftat bearbeiten")
        edit_window.geometry("400x300")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.grid_columnconfigure(1, weight=1)

        ttk.Label(edit_window, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        edit_name_entry = ttk.Entry(edit_window)
        edit_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        edit_name_entry.insert(0, crime_obj['name'])

        ttk.Label(edit_window, text="Paragraph:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        edit_paragraph_entry = ttk.Entry(edit_window)
        edit_paragraph_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        edit_paragraph_entry.insert(0, crime_obj.get('paragraph', ''))

        ttk.Label(edit_window, text="Hafteinheiten:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        edit_detention_entry = ttk.Entry(edit_window)
        edit_detention_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        edit_detention_entry.insert(0, str(crime_obj.get('detention_units', 0)))

        ttk.Label(edit_window, text="Geldstrafe:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        edit_fine_entry = ttk.Entry(edit_window)
        edit_fine_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        edit_fine_entry.insert(0, str(crime_obj.get('fine', 0)))

        def save_edited_crime():
            new_name = edit_name_entry.get().strip()
            new_paragraph = edit_paragraph_entry.get().strip()
            new_detention_str = edit_detention_entry.get().strip()
            new_fine_str = edit_fine_entry.get().strip()

            if not new_name:
                messagebox.showwarning("Eingabefehler", "Name der Straftat darf nicht leer sein.", parent=edit_window)
                return
            
            try:
                new_detention = int(new_detention_str)
                new_fine = int(new_fine_str)
            except ValueError:
                messagebox.showwarning("Eingabefehler", "Hafteinheiten und Geldstrafe müssen Zahlen sein.", parent=edit_window)
                return

            # Check for duplicates (case-insensitive name and paragraph), excluding the current crime being edited
            if any(c['name'].lower() == new_name.lower() and c.get('paragraph', '').lower() == new_paragraph.lower() and c != crime_obj for c in self.predefined_crimes):
                messagebox.showwarning("Warnung", "Diese Straftat existiert bereits.", parent=edit_window)
                return

            crime_obj['name'] = new_name
            crime_obj['paragraph'] = new_paragraph
            crime_obj['detention_units'] = new_detention
            crime_obj['fine'] = new_fine
            self.save_data(self.predefined_crimes, self.predefined_crimes_file)
            self.populate_predefined_crimes_list()
            messagebox.showinfo("Erfolg", "Straftat erfolgreich aktualisiert!", parent=edit_window)
            edit_window.destroy()

        ttk.Button(edit_window, text="Speichern", command=save_edited_crime).grid(row=4, column=0, columnspan=2, pady=10)

    def delete_predefined_crime(self):
        """Löscht eine vordefinierte Straftat."""
        selected_indices = self.predefined_crimes_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie eine Straftat zum Löschen aus.")
            return
        index = selected_indices[0]
        if messagebox.askyesno("Bestätigen", "Möchten Sie diese Straftat wirklich löschen?"):
            del self.predefined_crimes[index]
            self.save_data(self.predefined_crimes, self.predefined_crimes_file)
            self.populate_predefined_crimes_list()
            messagebox.showinfo("Erfolg", "Straftat erfolgreich gelöscht!")

    # --- Report Presets Tab Functions ---
    def create_report_presets_tab(self, parent_frame):
        """Creates widgets for the Report Presets tab."""
        content_frame = self._create_scrollable_tab(parent_frame)
        top_frame = ttk.LabelFrame(content_frame, text="Neues Preset hinzufügen", padding="15 10") # Design: LabelFrame
        top_frame.pack(fill="x", pady=10, padx=10)
        top_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2) # Adjusted row
        self.new_report_preset_name_entry = ttk.Entry(top_frame)
        self.new_report_preset_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2) # Adjusted row
        ttk.Label(top_frame, text="Vorlage (Platzhalter wie [name]):").grid(row=1, column=0, sticky="nw", padx=5, pady=2) # Adjusted row
        self.new_report_preset_template_text = scrolledtext.ScrolledText(top_frame, wrap=tk.WORD, height=6, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.new_report_preset_template_text.grid(row=1, column=1, sticky="ew", padx=5, pady=2) # Adjusted row
        add_report_preset_button = ttk.Button(top_frame, text="Preset hinzufügen", command=self.add_report_preset)
        add_report_preset_button.grid(row=2, column=0, columnspan=2, pady=10) # Adjusted row

        list_frame = ttk.LabelFrame(content_frame, text="Ihre Presets", padding="15 10") # Design: LabelFrame
        list_frame.pack(fill="both", expand=True, pady=10, padx=10)
        list_frame.grid_rowconfigure(0, weight=1) # Listbox row
        list_frame.grid_columnconfigure(0, weight=1)

        self.report_presets_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, font=("Arial", 10), bg='#ffffff', fg='#333333', selectbackground='#cceeff', selectforeground='#333333', relief="flat", borderwidth=1) # Design: Listbox bg/fg/selection/relief
        self.report_presets_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.report_presets_listbox.bind('<<ListboxSelect>>', self.display_selected_report_preset_template)
        report_presets_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.report_presets_listbox.yview)
        report_presets_scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        self.report_presets_listbox.config(yscrollcommand=report_presets_scrollbar.set)

        button_frame = ttk.Frame(list_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew") # Adjusted row
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        copy_template_button = ttk.Button(button_frame, text="Vorlage kopieren", command=self.copy_selected_report_preset_template)
        copy_template_button.grid(row=0, column=0, padx=5, sticky="ew")
        edit_report_preset_button = ttk.Button(button_frame, text="Preset bearbeiten", command=self.start_editing_report_preset)
        edit_report_preset_button.grid(row=0, column=1, padx=5, sticky="ew")
        delete_report_preset_button = ttk.Button(button_frame, text="Preset löschen", command=self.delete_report_preset)
        delete_report_preset_button.grid(row=0, column=2, padx=5, sticky="ew")

        self.fill_report_preset_frame = ttk.LabelFrame(content_frame, text="Preset ausfüllen & Bericht erstellen", padding="15 10") # Design: LabelFrame
        self.fill_report_preset_frame.pack(fill="both", expand=True, pady=10, padx=10)
        self.fill_report_preset_frame.grid_columnconfigure(0, weight=1)
        self.fill_report_preset_frame.grid_columnconfigure(1, weight=1)
        self.fill_report_preset_frame.grid_columnconfigure(2, weight=1)

        self.dynamic_inputs_frame = ttk.Frame(self.fill_report_preset_frame)
        self.dynamic_inputs_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        self.dynamic_inputs_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(self.fill_report_preset_frame, text="Bericht erstellen", command=self.generate_report, style="Accent.TButton").grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.generated_report_text = scrolledtext.ScrolledText(self.fill_report_preset_frame, wrap=tk.WORD, height=10, state='disabled', bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        self.generated_report_text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.fill_report_preset_frame.grid_rowconfigure(2, weight=1)

        ttk.Button(self.fill_report_preset_frame, text="Bericht kopieren", command=self.copy_generated_report, style="CAccent.TButton").grid(row=3, column=0,columnspan=3, padx=5, pady=5, sticky="ew")

        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 12, "bold"), foreground="white", background="#4CAF50", borderwidth=0)
        style.map("Accent.TButton", background=[('active', '#45a049')])

        self.populate_report_presets_list()

    def populate_report_presets_list(self):
        """Populates the report presets listbox with data."""
        self.report_presets_listbox.delete(0, tk.END)
        for i, preset in enumerate(self.report_presets):
            self.report_presets_listbox.insert(tk.END, preset['name'])

    def display_selected_report_preset_template(self, event):
        """Displays the template of the selected preset and creates dynamic input fields."""
        selected_indices = self.report_presets_listbox.curselection()
        if not selected_indices: return
        index = selected_indices[0]
        self.selected_report_preset = self.report_presets[index]

        for widget in self.dynamic_inputs_frame.winfo_children():
            widget.destroy()
        self.dynamic_input_widgets = {}

        template_string = self.selected_report_preset['template_string']
        placeholders = self.extract_placeholders(template_string)

        row_idx = 0
        unique_placeholders = []
        for p in placeholders:
            if p not in unique_placeholders:
                unique_placeholders.append(p)

        for placeholder in unique_placeholders:
            label_text = placeholder.replace('[', '').replace(']', '') + ":"
            ttk.Label(self.dynamic_inputs_frame, text=label_text).grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
            entry = ttk.Entry(self.dynamic_inputs_frame)
            entry.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
            self.dynamic_input_widgets[placeholder] = entry
            row_idx += 1

        if '[Datum]' in self.dynamic_input_widgets:
            self.dynamic_input_widgets['[Datum]'].insert(0, datetime.now().strftime("%d.%m.%Y"))
        if '[uhrzeit]' in self.dynamic_input_widgets:
            self.dynamic_input_widgets['[uhrzeit]'].insert(0, datetime.now().strftime("%H:%M Uhr"))

    def extract_placeholders(self, template_string):
        """Extracts placeholders from the template string."""
        # Use re.findall to find all occurrences of [something]
        return re.findall(r'\[(.*?)\]', template_string)

    def add_report_preset(self):
        """Adds a new preset."""
        name = self.new_report_preset_name_entry.get().strip()
        template_string = self.new_report_preset_template_text.get(1.0, tk.END).strip()
        if not name or not template_string:
            messagebox.showwarning("Eingabefehler", "Name und Vorlage des Presets dürfen nicht leer sein.")
            return
        self.report_presets.append({"id": str(uuid.uuid4()), "name": name, "template_string": template_string})
        self.save_data(self.report_presets, self.report_presets_file)
        self.populate_report_presets_list()
        self.new_report_preset_name_entry.delete(0, tk.END)
        self.new_report_preset_template_text.delete(1.0, tk.END)
        messagebox.showinfo("Erfolg", "Preset erfolgreich hinzugefügt!")

    def start_editing_report_preset(self):
        """Prepares a preset for editing."""
        selected_indices = self.report_presets_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie ein Preset zum Bearbeiten aus.")
            return
        index = selected_indices[0]
        self.editing_report_preset_index = index
        preset = self.report_presets[index]

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Preset bearbeiten")
        edit_window.geometry("600x500")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.grid_rowconfigure(1, weight=1)
        edit_window.grid_columnconfigure(1, weight=1)

        ttk.Label(edit_window, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        edit_name_entry = ttk.Entry(edit_window)
        edit_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        edit_name_entry.insert(0, preset['name'])
        ttk.Label(edit_window, text="Vorlage:").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        edit_template_text = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD, height=15, bg='#ffffff', fg='#333333', insertbackground='#333333', relief="flat", borderwidth=1) # Design: ScrolledText bg/fg/relief
        edit_template_text.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        edit_template_text.insert(1.0, preset['template_string'])

        def save_edited_report_preset():
            new_name = edit_name_entry.get().strip()
            new_template_string = edit_template_text.get(1.0, tk.END).strip()
            if not new_name or not new_template_string:
                messagebox.showwarning("Eingabefehler", "Name und Vorlage dürfen nicht leer sein.", parent=edit_window)
                return
            self.report_presets[self.editing_report_preset_index]['name'] = new_name
            self.report_presets[self.editing_report_preset_index]['template_string'] = new_template_string
            self.save_data(self.report_presets, self.report_presets_file)
            self.populate_report_presets_list()
            if hasattr(self, 'selected_report_preset') and self.selected_report_preset == preset:
                self.display_selected_report_preset_template(None)
            messagebox.showinfo("Erfolg", "Preset erfolgreich aktualisiert!", parent=edit_window)
            edit_window.destroy()
        ttk.Button(edit_window, text="Speichern", command=save_edited_report_preset).grid(row=2, column=0, columnspan=2, pady=10)

    def delete_report_preset(self):
        """Löscht das ausgewählte Preset."""
        selected_indices = self.report_presets_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie ein Preset zum Löschen aus.")
            return
        index = selected_indices[0]
        if messagebox.askyesno("Bestätigen", "Möchten Sie dieses Preset wirklich löschen?"):
            del self.report_presets[index]
            self.save_data(self.report_presets, self.report_presets_file)
            self.populate_report_presets_list()
            if hasattr(self, 'selected_report_preset') and self.report_presets_listbox.curselection() == ():
                 for widget in self.dynamic_inputs_frame.winfo_children():
                     widget.destroy()
                 self.dynamic_input_widgets = {}
                 self.generated_report_text.config(state='normal')
                 self.generated_report_text.delete(1.0, tk.END)
                 self.generated_report_text.config(state='disabled')
            messagebox.showinfo("Erfolg", "Preset erfolgreich gelöscht!")

    def copy_selected_report_preset_template(self):
        """Kopiert die Vorlage des ausgewählten Presets in die Zwischenablage."""
        selected_indices = self.report_presets_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie ein Preset zum Kopieren aus.")
            return
        index = selected_indices[0]
        template_to_copy = self.report_presets[index]['template_string']
        self.root.clipboard_clear()
        self.root.clipboard_append(template_to_copy)
        messagebox.showinfo("Kopiert", "Vorlage in die Zwischenablage kopiert!")

    def generate_report(self):
        """Generiert den Bericht basierend auf der ausgewählten Vorlage und den Eingaben."""
        if not hasattr(self, 'selected_report_preset') or not self.selected_report_preset:
            messagebox.showwarning("Auswahlfehler", "Bitte wählen Sie zuerst ein Preset aus.")
            return

        template_string = self.selected_report_preset['template_string']
        generated_content = template_string

        # Extract all possible placeholders from the template
        all_placeholders_in_template = re.findall(r'\[(.*?)\]', template_string)
        
        # Collect all placeholder values from user inputs
        placeholder_values = {}
        for placeholder_key, entry_widget in self.dynamic_input_widgets.items():
            placeholder_values[placeholder_key] = entry_widget.get().strip()

        # First pass: Replace filled placeholders
        for placeholder_key_raw, user_input in placeholder_values.items():
            full_placeholder = f"[{placeholder_key_raw}]"
            generated_content = generated_content.replace(full_placeholder, user_input)

        # Second pass: Remove any remaining, unfilled placeholders (with their brackets)
        # We need to iterate through the *original* placeholders from the template
        # and check if they still exist in the generated content.
        for placeholder_raw in all_placeholders_in_template:
            full_placeholder = f"[{placeholder_raw}]"
            if full_placeholder in generated_content:
                generated_content = generated_content.replace(full_placeholder, "")


        self.generated_report_text.config(state='normal')
        self.generated_report_text.delete(1.0, tk.END)
        self.generated_report_text.insert(tk.END, generated_content)
        self.generated_report_text.config(state='disabled')
        messagebox.showinfo("Bericht erstellt", "Der Bericht wurde erfolgreich generiert!")

    def copy_generated_report(self):
        """Kopiert den generierten Bericht in die Zwischenablage."""
        report_content = self.generated_report_text.get(1.0, tk.END).strip()
        if not report_content:
            messagebox.showwarning("Nichts zu kopieren", "Es wurde noch kein Bericht generiert.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(report_content)
        messagebox.showinfo("Kopiert", "Bericht in die Zwischenablage kopiert!")

    def export_signature_as_image(self):
        """Exportiert den Unterschriftsteil als Bild."""
        report_content = self.generated_report_text.get(1.0, tk.END).strip()
        if not report_content:
            messagebox.showwarning("Fehler", "Bitte generieren Sie zuerst einen Bericht.")
            return

        signature_line_start = report_content.find("Unterschrift [Officer Name]:")
        if signature_line_start == -1:
            messagebox.showwarning("Fehler", "Unterschriftsteil nicht im Bericht gefunden. Bitte überprüfen Sie das Preset-Format.")
            return

        signature_line_end = report_content.find("\n", signature_line_start)
        if signature_line_end == -1:
            signature_text = report_content[signature_line_start:].strip()
        else:
            signature_text = report_content[signature_line_start:signature_line_end].strip()

        if not signature_text:
            messagebox.showwarning("Fehler", "Kein Unterschriftstext zum Exportieren gefunden.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("Alle Dateien", "*.*")],
            title="Unterschrift als Bild speichern unter"
        )
        if not file_path: return

        try:
            img_width = 600
            img_height = 100
            img = Image.new('RGB', (255, 255, 255), color = (255, 255, 255)) # Set background to white
            d = ImageDraw.Draw(img)

            try:
                font_paths = [
                    "C:/Windows/Fonts/Gabriola.ttf",
                    "C:/Windows/Fonts/Brush Script MT.ttf",
                    "C:/Windows/Fonts/Segoe Script.ttf",
                    "C:/Windows/Fonts/Comic Sans MS.ttf"
                ]
                signature_font = None
                for f_path in font_paths:
                    if os.path.exists(f_path):
                        signature_font = ImageFont.truetype(f_path, 30)
                        break
                if not signature_font:
                    signature_font = ImageFont.load_default()
                    messagebox.showwarning("Schriftart-Warnung", "Keine passende Kursivschriftart gefunden. Standard-Schriftart wird verwendet.", parent=self.root)

            except Exception as e:
                print(f"Fehler beim Laden der Schriftart: {e}")
                signature_font = ImageFont.load_default()
                messagebox.showwarning("Schriftart-Warnung", "Fehler beim Laden der Schriftart. Standard-Schriftart wird verwendet.", parent=self.root)

            text_bbox = d.textbbox((0,0), signature_text, font=signature_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            x = (img_width - text_width) / 2
            y = (img_height - text_height) / 2

            d.text((x, y), signature_text, font=signature_font, fill=(0, 0, 0))

            img.save(file_path)
            messagebox.showinfo("Export erfolgreich", f"Unterschrift als Bild gespeichert unter:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Exportfehler", f"Fehler beim Exportieren der Unterschrift als Bild: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PoliceRPApp(root)
    # Load placeholder image for the perpetrator files tab on startup
    root.mainloop()
