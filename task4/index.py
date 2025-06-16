import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, Canvas, Frame
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
from utils import *

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False


class DraggableElement:
    def __init__(self, canvas, element_type, x, y, scale=1.0, **kwargs):
        self.canvas = canvas
        self.element_type = element_type
        self.scale = scale
        self.x = x
        self.y = y
        self.selected = False
        
        self.create_element()
        self.bind_events()
    
    def create_element(self):
        if self.element_type == "horns":
            self.create_horns()
        elif self.element_type == "mustache":
            self.create_mustache()
        elif self.element_type == "text":
            self.create_text()
    
    def create_horns(self):
        size = int(40 * self.scale)
        self.elements = []
        
        # Left horn
        left_points = [
            self.x - size, self.y + size//2,
            self.x - size//2, self.y - size//2,
            self.x - size//4, self.y + size//2
        ]
        left_horn = self.canvas.create_polygon(left_points, fill="#8B4513", outline="#654321", width=2, tags="element")
        
        # Right horn
        right_points = [
            self.x + size, self.y + size//2,
            self.x + size//2, self.y - size//2,
            self.x + size//4, self.y + size//2
        ]
        right_horn = self.canvas.create_polygon(right_points, fill="#8B4513", outline="#654321", width=2, tags="element")
        
        self.elements = [left_horn, right_horn]
    
    def create_mustache(self):
        size = int(50 * self.scale)
        
        # Main mustache body
        main_mustache = self.canvas.create_oval(
            self.x - size, self.y - size//4,
            self.x + size, self.y + size//4,
            fill="black", outline="black", tags="element"
        )
        
        # Left curl
        left_curl = self.canvas.create_oval(
            self.x - size*1.2, self.y - size//6,
            self.x - size*0.7, self.y + size//6,
            fill="black", outline="black", tags="element"
        )
        
        # Right curl
        right_curl = self.canvas.create_oval(
            self.x + size*0.7, self.y - size//6,
            self.x + size*1.2, self.y + size//6,
            fill="black", outline="black", tags="element"
        )
        
        self.elements = [main_mustache, left_curl, right_curl]
    
    def create_text(self):
        font_size = int(20 * self.scale)
        self.text_id = self.canvas.create_text(
            self.x, self.y, 
            text=getattr(self, 'text_content', 'Sample Text'),
            font=("Arial", font_size, "bold"),
            fill=getattr(self, 'text_color', 'white'),
            tags="element"
        )
        self.elements = [self.text_id]
    
    def bind_events(self):
        for element in self.elements:
            self.canvas.tag_bind(element, "<Button-1>", self.on_click)
            self.canvas.tag_bind(element, "<B1-Motion>", self.on_drag)
            self.canvas.tag_bind(element, "<ButtonRelease-1>", self.on_release)
    
    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.select()
    
    def on_drag(self, event):
        dx = event.x - self.start_x
        dy = event.y - self.start_y
        
        # Update position
        self.x += dx
        self.y += dy
        
        # Keep within canvas bounds
        self.x = max(20, min(self.x, 620))
        self.y = max(20, min(self.y, 460))
        
        # Move all elements
        for element in self.elements:
            self.canvas.move(element, dx, dy)
        
        self.start_x = event.x
        self.start_y = event.y
    
    def on_release(self, event):
        pass
    
    def select(self):
        self.selected = True
        # Add selection highlight
        for element in self.elements:
            self.canvas.create_rectangle(
                *self.canvas.bbox(element), 
                outline="yellow", width=2, tags="selection"
            )
    
    def deselect(self):
        self.selected = False
        self.canvas.delete("selection")
    
    def update_scale(self, new_scale):
        self.scale = new_scale
        self.delete()
        self.create_element()
        self.bind_events()
        if self.selected:
            self.select()
    
    def delete(self):
        for element in self.elements:
            self.canvas.delete(element)
        self.canvas.delete("selection")


class TextElement(DraggableElement):
    def __init__(self, canvas, x, y, text_content="Sample Text", font_size=20, text_color="white", bold=False, italic=False):
        self.text_content = text_content
        self.font_size = font_size
        self.text_color = text_color
        self.bold = bold
        self.italic = italic
        super().__init__(canvas, "text", x, y, 1.0)
    
    def create_text(self):
        if not self.text_content.strip():
            return
            
        font_style = []
        if self.bold:
            font_style.append("bold")
        if self.italic:
            font_style.append("italic")
        font_tuple = ("Arial", self.font_size) + tuple(font_style)
        
        # Create the text
        self.text_id = self.canvas.create_text(
            self.x, self.y, 
            text=self.text_content,
            font=font_tuple,
            fill=self.text_color,
            tags="element"
        )
        
        # Get text bounds for wrapper
        bbox = self.canvas.bbox(self.text_id)
        if bbox:
            padding = 5
            # Create transparent wrapper rectangle for easier selection
            self.wrapper_id = self.canvas.create_rectangle(
                bbox[0] - padding, bbox[1] - padding,
                bbox[2] + padding, bbox[3] + padding,
                fill="", outline="", width=0,
                tags="element"
            )
            
            self.elements = [self.wrapper_id, self.text_id]
        else:
            self.elements = [self.text_id]
    
    def update_text(self, text_content="", font_size=20, text_color="white", bold=False, italic=False):
        self.text_content = text_content
        self.font_size = font_size
        self.text_color = text_color
        self.bold = bold
        self.italic = italic
        
        if self.text_content.strip():
            self.delete()
            self.create_element()
            self.bind_events()
            if self.selected:
                self.select()
    
    def on_drag(self, event):
        dx = event.x - self.start_x
        dy = event.y - self.start_y
        
        # Update position
        self.x += dx
        self.y += dy
        
        # Keep within canvas bounds
        self.x = max(30, min(self.x, 610))
        self.y = max(30, min(self.y, 450))
        
        # Move all elements
        for element in self.elements:
            self.canvas.move(element, dx, dy)
        
        # Update wrapper position after moving text
        if len(self.elements) > 1:
            bbox = self.canvas.bbox(self.text_id)
            if bbox:
                padding = 5
                self.canvas.coords(self.wrapper_id, 
                    bbox[0] - padding, bbox[1] - padding,
                    bbox[2] + padding, bbox[3] + padding)
        
        self.start_x = event.x
        self.start_y = event.y


class PhotoBooth:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Photo Booth Prototype - Canvas Based")
        self.root.geometry("1200x800")
        
        # Image dimensions (4:3 aspect ratio)
        self.image_width = 640
        self.image_height = 480
        
        self.current_image = None
        self.captured_image = None
        self.original_captured_image = None
        self.cap = None
        self.picam = None
        self.camera_type = None
        
        self.elements = []
        self.text_element = None
        self.selected_element = None
        
        self.setup_ui()
        self.start_camera()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top section with preview and canvas
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Camera preview (left)
        camera_frame = ttk.LabelFrame(preview_frame, text="Camera Preview", padding=10)
        camera_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        self.camera_label = ttk.Label(camera_frame, text="Camera Loading...")
        self.camera_label.pack()
        
        # Canvas for captured photo (center)
        canvas_frame = ttk.LabelFrame(preview_frame, text="Photo Canvas (Drag Elements)", padding=10)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.photo_canvas = Canvas(
            canvas_frame, 
            width=self.image_width, 
            height=self.image_height,
            bg="gray20"
        )
        self.photo_canvas.pack()
        self.photo_canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Element selector (right)
        selector_frame = ttk.LabelFrame(preview_frame, text="Element Selector", padding=10)
        selector_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Element management
        elements_list_frame = ttk.LabelFrame(selector_frame, text="Active Elements", padding=5)
        elements_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.elements_listbox = tk.Listbox(elements_list_frame, height=8, width=20)
        self.elements_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.elements_listbox.bind('<Button-1>', self.select_element_from_list)
        
        list_buttons_frame = ttk.Frame(elements_list_frame)
        list_buttons_frame.pack(pady=5)
        
        ttk.Button(list_buttons_frame, text="Delete Selected", command=self.delete_selected_element).pack(pady=2)
        ttk.Button(list_buttons_frame, text="Clear All", command=self.clear_elements).pack(pady=2)
        
        # Quick add buttons
        quick_add_frame = ttk.LabelFrame(selector_frame, text="Quick Add", padding=5)
        quick_add_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(quick_add_frame, text="Add Horns", command=self.add_horns, width=15).pack(pady=2)
        ttk.Button(quick_add_frame, text="Add Mustache", command=self.add_mustache, width=15).pack(pady=2)
        
        # Element scale control
        scale_frame = ttk.LabelFrame(selector_frame, text="Selected Element", padding=5)
        scale_frame.pack(fill=tk.X)
        
        ttk.Label(scale_frame, text="Size:").pack()
        self.element_scale_var = tk.DoubleVar(value=1.0)
        self.element_scale_var.trace_add('write', self.on_element_scale_change)
        scale_slider = ttk.Scale(scale_frame, from_=0.5, to=3.0, variable=self.element_scale_var, orient=tk.HORIZONTAL, length=150)
        scale_slider.pack(pady=5)
        
        self.scale_label = ttk.Label(scale_frame, text="1.0x")
        self.scale_label.pack()
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Take Photo", command=self.take_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Photo", command=self.delete_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Photo", command=self.save_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Image", command=self.load_image_file).pack(side=tk.LEFT, padx=5)
        
        # Controls notebook
        self.setup_controls(main_frame)
    
    def setup_controls(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        basic_frame = ttk.Frame(notebook)
        text_frame = ttk.Frame(notebook)
        effects_frame = ttk.Frame(notebook)
        
        notebook.add(basic_frame, text="Basic")
        notebook.add(text_frame, text="Text")
        notebook.add(effects_frame, text="Effects")
        
        self.setup_basic_controls(basic_frame)
        self.setup_text_controls(text_frame)
        self.setup_effects_controls(effects_frame)
    
    def setup_basic_controls(self, parent):
        ttk.Label(parent, text="Rotation:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.rotation_var = tk.DoubleVar()
        self.rotation_var.trace_add('write', self.on_rotation_change)
        ttk.Scale(parent, from_=-180, to=180, variable=self.rotation_var, orient=tk.HORIZONTAL, length=200).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(parent, text="Filename:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.filename_var = tk.StringVar(value="photo.jpg")
        ttk.Entry(parent, textvariable=self.filename_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Reset", command=self.reset_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Elements", command=self.clear_elements).pack(side=tk.LEFT, padx=5)
    
    def setup_text_controls(self, parent):
        ttk.Label(parent, text="Text:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.text_var = tk.StringVar()
        self.text_var.trace_add('write', self.on_text_change)
        ttk.Entry(parent, textvariable=self.text_var, width=30).grid(row=0, column=1, columnspan=2, padx=5, pady=5)
        
        ttk.Label(parent, text="Font Size:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.font_size_var = tk.IntVar(value=20)
        self.font_size_var.trace_add('write', self.update_font_size_label)
        self.font_size_var.trace_add('write', self.on_text_change)
        ttk.Scale(parent, from_=12, to=60, variable=self.font_size_var, orient=tk.HORIZONTAL, length=150).grid(row=1, column=1, padx=5, pady=5)
        self.font_size_label = ttk.Label(parent, text="20")
        self.font_size_label.grid(row=1, column=2, padx=5, pady=5)
        
        ttk.Label(parent, text="Color:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.text_color = "white"
        self.color_button = ttk.Button(parent, text="Choose Color", command=self.choose_text_color)
        self.color_button.grid(row=2, column=1, padx=5, pady=5)
        self.color_preview = tk.Label(parent, text="   ", bg="white", relief="solid", borderwidth=1, width=4, height=1)
        self.color_preview.grid(row=2, column=2, padx=5, pady=5)
        
        style_frame = ttk.Frame(parent)
        style_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.bold_var = tk.BooleanVar()
        self.bold_var.trace_add('write', self.on_text_change)
        ttk.Checkbutton(style_frame, text="Bold", variable=self.bold_var).pack(side=tk.LEFT, padx=10)
        
        self.italic_var = tk.BooleanVar()
        self.italic_var.trace_add('write', self.on_text_change)
        ttk.Checkbutton(style_frame, text="Italic", variable=self.italic_var).pack(side=tk.LEFT, padx=10)
        
        info_frame = ttk.Frame(parent)
        info_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        ttk.Label(info_frame, text="Click on canvas to place text at center").pack()
        ttk.Label(info_frame, text="Text will be automatically centered on the image").pack()
        
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Center Text", command=self.center_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Text", command=self.remove_text).pack(side=tk.LEFT, padx=5)
    
    def setup_effects_controls(self, parent):
        ttk.Label(parent, text="Image Effects:").grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=10)
        
        # Rotation control (duplicate from basic for convenience)
        ttk.Label(parent, text="Rotation:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        rotation_var2 = tk.DoubleVar()
        rotation_var2.trace_add('write', lambda *args: self.rotation_var.set(rotation_var2.get()))
        self.rotation_var.trace_add('write', lambda *args: rotation_var2.set(self.rotation_var.get()))
        ttk.Scale(parent, from_=-180, to=180, variable=rotation_var2, orient=tk.HORIZONTAL, length=200).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(parent, text="Note: Element controls are now in the sidebar").grid(row=2, column=0, columnspan=3, pady=20)
        ttk.Label(parent, text="• Use the Element Selector panel to manage elements").grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=20)
        ttk.Label(parent, text="• Click elements in the list to select them").grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=20)
        ttk.Label(parent, text="• Use Quick Add buttons for horns and mustache").grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=20)
        ttk.Label(parent, text="• Adjust size with the slider when element is selected").grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=20)
    
    def on_canvas_click(self, event):
        # Deselect all elements first
        self.deselect_all()
        
        # If there's text, place it at center of canvas (not click position)
        if self.text_var.get().strip():
            if self.text_element:
                self.text_element.delete()
            
            # Always center the text
            center_x = self.image_width // 2
            center_y = self.image_height // 2
            
            self.text_element = TextElement(
                self.photo_canvas, center_x, center_y,
                self.text_var.get(),
                self.font_size_var.get(),
                self.text_color,
                self.bold_var.get(),
                self.italic_var.get()
            )
    
    def deselect_all(self):
        for element in self.elements:
            element.deselect()
        if self.text_element:
            self.text_element.deselect()
        self.selected_element = None
    
    def on_rotation_change(self, *args):
        self.update_photo_display()
    
    def on_text_change(self, *args):
        if self.text_element and self.text_var.get().strip():
            self.text_element.update_text(
                self.text_var.get(),
                self.font_size_var.get(),
                self.text_color,
                self.bold_var.get(),
                self.italic_var.get()
            )
        elif not self.text_var.get().strip() and self.text_element:
            self.text_element.delete()
            self.text_element = None
    
    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose text color", initialcolor=self.text_color)
        if color[1]:
            self.text_color = color[1]
            self.color_preview.config(bg=self.text_color)
            self.on_text_change()
    
    def on_element_scale_change(self, *args):
        scale = self.element_scale_var.get()
        self.scale_label.config(text=f"{scale:.1f}x")
        
        if self.selected_element:
            self.selected_element.update_scale(scale)
    
    def select_element_from_list(self, event):
        selection = self.elements_listbox.curselection()
        if selection:
            self.deselect_all()
            idx = selection[0]
            if idx < len(self.elements):
                self.selected_element = self.elements[idx]
                self.selected_element.select()
                self.element_scale_var.set(self.selected_element.scale)
    
    def update_elements_list(self):
        self.elements_listbox.delete(0, tk.END)
        for i, element in enumerate(self.elements):
            name = f"{i+1}. {element.element_type.title()} at ({int(element.x)}, {int(element.y)})"
            self.elements_listbox.insert(tk.END, name)
    
    def add_horns(self):
        if self.captured_image is None:
            messagebox.showwarning("No Photo", "Please take a photo first!")
            return
        
        horns = DraggableElement(self.photo_canvas, "horns", 320, 120, 1.0)
        self.elements.append(horns)
        self.update_elements_list()
    
    def add_mustache(self):
        if self.captured_image is None:
            messagebox.showwarning("No Photo", "Please take a photo first!")
            return
        
        mustache = DraggableElement(self.photo_canvas, "mustache", 320, 360, 1.0)
        self.elements.append(mustache)
        self.update_elements_list()
    
    def delete_selected_element(self):
        if self.selected_element:
            self.selected_element.delete()
            if self.selected_element in self.elements:
                self.elements.remove(self.selected_element)
            self.selected_element = None
            self.update_elements_list()
    
    def clear_elements(self):
        for element in self.elements:
            element.delete()
        if self.text_element:
            self.text_element.delete()
            self.text_element = None
        self.elements.clear()
        self.update_elements_list()
    
    def start_camera(self):
        if PICAMERA_AVAILABLE:
            self.init_pi_camera()
        else:
            self.init_opencv_camera()
    
    def init_pi_camera(self):
        try:
            self.picam = Picamera2()
            config = self.picam.create_preview_configuration(main={"size": (640, 480)})
            self.picam.configure(config)
            self.picam.start()
            self.camera_type = "picamera"
            self.update_pi_camera()
        except Exception as e:
            self.init_opencv_camera()
    
    def init_opencv_camera(self):
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Could not open camera")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            ret, test_frame = self.cap.read()
            if not ret:
                raise Exception("Could not read from camera")
            
            self.camera_type = "opencv"
            self.update_opencv_camera()
        except Exception as e:
            self.load_default_image()
    
    def load_default_image(self):
        self.current_image = create_default_image()
        self.camera_type = "none"
        self.update_camera_preview()
    
    def load_image_file(self):
        file_path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff")]
        )
        if file_path:
            img = load_and_process_image(file_path, (640, 480))
            if img is not None:
                self.current_image = img
                self.update_camera_preview()
                messagebox.showinfo("Image Loaded", "Image loaded successfully!")
            else:
                messagebox.showerror("Error", "Could not load the selected image")
    
    def update_pi_camera(self):
        if self.picam and self.camera_type == "picamera":
            frame = self.picam.capture_array()
            self.current_image = process_camera_frame(frame, "picamera")
            self.update_camera_preview()
        self.root.after(30, self.update_pi_camera)
    
    def update_opencv_camera(self):
        if self.cap and self.cap.isOpened() and self.camera_type == "opencv":
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.current_image = process_camera_frame(frame, "opencv")
                self.update_camera_preview()
            else:
                self.load_default_image()
                return
        self.root.after(30, self.update_opencv_camera)
    
    def update_camera_preview(self):
        if self.current_image is not None:
            tk_image = convert_to_tk_image(self.current_image, (320, 240))
            if tk_image:
                self.camera_label.configure(image=tk_image, text="")
                self.camera_label.image = tk_image
    
    def update_photo_display(self):
        if self.captured_image is not None:
            # Apply rotation to the captured image
            display_image = self.captured_image.copy()
            if self.rotation_var.get() != 0:
                display_image = apply_rotation_to_image(display_image, self.rotation_var.get())
            
            # Convert to PhotoImage and display on canvas
            tk_image = convert_to_tk_image(display_image, (self.image_width, self.image_height))
            if tk_image:
                # Clear previous image but keep elements
                self.photo_canvas.delete("background_image")
                self.photo_canvas.create_image(
                    self.image_width//2, self.image_height//2, 
                    image=tk_image, 
                    tags="background_image"
                )
                # Keep reference to prevent garbage collection
                self.photo_canvas.image = tk_image
                # Send background to back
                self.photo_canvas.tag_lower("background_image")
    
    def take_photo(self):
        if self.current_image is not None:
            self.captured_image = self.current_image.copy()
            self.original_captured_image = self.current_image.copy()
            self.update_photo_display()
            messagebox.showinfo("Photo Taken", "Photo captured successfully!")
        else:
            messagebox.showwarning("No Image", "No image available to capture!")
    
    def delete_photo(self):
        if self.captured_image is not None:
            self.captured_image = None
            self.original_captured_image = None
            self.photo_canvas.delete("background_image")
            self.clear_elements()
            messagebox.showinfo("Photo Deleted", "Photo deleted successfully!")
        else:
            messagebox.showwarning("No Photo", "No photo to delete!")
    
    def save_photo(self):
        if self.captured_image is None:
            messagebox.showwarning("No Photo", "Please take a photo first!")
            return
        
        # Create final image with elements rendered
        final_image = self.captured_image.copy()
        if self.rotation_var.get() != 0:
            final_image = apply_rotation_to_image(final_image, self.rotation_var.get())
        
        filename = self.filename_var.get()
        if not filename.endswith(('.jpg', '.jpeg', '.png')):
            filename += '.jpg'
        
        cv2.imwrite(filename, final_image)
        messagebox.showinfo("Photo Saved", f"Photo saved as {filename}")
    
    def reset_image(self):
        self.captured_image = None
        self.original_captured_image = None
        self.photo_canvas.delete("background_image")
        self.clear_elements()
        self.text_var.set("")
        self.rotation_var.set(0)
        self.font_size_var.set(20)
        self.bold_var.set(False)
        self.italic_var.set(False)
        self.text_color = "white"
        messagebox.showinfo("Reset", "Image and settings reset!")
    
    def update_font_size_label(self, *args):
        self.font_size_label.config(text=str(self.font_size_var.get()))
    
    def center_text(self):
        if self.text_element:
            self.text_element.delete()
            self.text_element = TextElement(
                self.photo_canvas, self.image_width//2, self.image_height//2,
                self.text_var.get(),
                self.font_size_var.get(),
                self.text_color,
                self.bold_var.get(),
                self.italic_var.get()
            )
    
    def remove_text(self):
        if self.text_element:
            self.text_element.delete()
            self.text_element = None
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        if self.cap:
            self.cap.release()
        if self.picam:
            self.picam.stop()
            self.picam.close()
        self.root.destroy()


if __name__ == "__main__":
    app = PhotoBooth()
    app.run()
