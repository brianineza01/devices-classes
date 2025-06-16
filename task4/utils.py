import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont


def create_default_image():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img.fill(32)
    cv2.putText(img, "No Camera Available", (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(img, "Load an image to continue", (120, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    return img.astype(np.uint8)


def create_error_image(size=(640, 480)):
    error_img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    error_img.fill(64)
    cv2.putText(error_img, "Image Error", (size[0]//2-60, size[1]//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return error_img


def normalize_image(img):
    if img is None or img.size == 0:
        return None
    
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)
    
    return img


def resize_image_to_aspect_ratio(img, target_width=640, target_height=480):
    if img is None:
        return None
    
    h, w = img.shape[:2]
    target_aspect = target_width / target_height
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        new_width = target_width
        new_height = int(target_width / current_aspect)
    else:
        new_height = target_height
        new_width = int(target_height * current_aspect)
    
    resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    canvas.fill(32)
    
    y_offset = (target_height - new_height) // 2
    x_offset = (target_width - new_width) // 2
    
    canvas[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = resized
    
    return canvas


def convert_to_tk_image(cv_image, target_size=(640, 480)):
    if cv_image is None or cv_image.size == 0:
        return None
    
    img = cv_image.copy()
    img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(img_rgb)
    return ImageTk.PhotoImage(pil_image)


def process_camera_frame(frame, camera_type="opencv"):
    if frame is None:
        return None
    
    if camera_type == "picamera":
        if len(frame.shape) == 3:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    else:
        if len(frame.shape) == 3:
            frame_bgr = frame
        else:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    
    if frame_bgr.dtype != np.uint8:
        frame_bgr = frame_bgr.astype(np.uint8)
    
    flipped = cv2.flip(frame_bgr, 1)
    return resize_image_to_aspect_ratio(flipped, 640, 480)


def load_and_process_image(file_path, target_size=(640, 480)):
    img = cv2.imread(file_path)
    if img is None:
        return None
    
    img = normalize_image(img)
    if img is not None:
        img = resize_image_to_aspect_ratio(img, target_size[0], target_size[1])
    
    return img


def apply_rotation_to_image(img, rotation=0):
    if rotation == 0:
        return img
    
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    rotated = pil_img.rotate(rotation, expand=True, fillcolor=(255, 255, 255))
    final_img = np.array(rotated)
    return cv2.cvtColor(final_img, cv2.COLOR_RGB2BGR)


def get_font(size=40, bold=False, italic=False):
    font_paths = [
        "arial.ttf",
        "Arial.ttf", 
        "/System/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    
    if bold and italic:
        bold_italic_paths = [
            "arialbi.ttf",
            "Arial Bold Italic.ttf",
            "/System/Library/Fonts/Arial Bold Italic.ttf"
        ]
        font_paths = bold_italic_paths + font_paths
    elif bold:
        bold_paths = [
            "arialbd.ttf", 
            "Arial Bold.ttf",
            "/System/Library/Fonts/Arial Bold.ttf"
        ]
        font_paths = bold_paths + font_paths
    elif italic:
        italic_paths = [
            "ariali.ttf",
            "Arial Italic.ttf", 
            "/System/Library/Fonts/Arial Italic.ttf"
        ]
        font_paths = italic_paths + font_paths
    
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    
    return ImageFont.load_default()


def add_text_overlay(pil_img, text, font_size=40, color=(255, 255, 255), position="bottom", bold=False, italic=False, custom_x=None, custom_y=None):
    if not text or text.strip() == "":
        return
        
    draw = ImageDraw.Draw(pil_img)
    font = get_font(font_size, bold, italic)
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    if custom_x is not None and custom_y is not None:
        x = max(0, min(custom_x, pil_img.width - text_width))
        y = max(0, min(custom_y, pil_img.height - text_height))
    elif position == "top":
        x = (pil_img.width - text_width) // 2
        y = 20
    elif position == "center":
        x = (pil_img.width - text_width) // 2
        y = (pil_img.height - text_height) // 2
    elif position == "bottom":
        x = (pil_img.width - text_width) // 2
        y = pil_img.height - text_height - 20
    elif position == "top-left":
        x = 20
        y = 20
    elif position == "top-right":
        x = pil_img.width - text_width - 20
        y = 20
    elif position == "bottom-left":
        x = 20
        y = pil_img.height - text_height - 20
    elif position == "bottom-right":
        x = pil_img.width - text_width - 20
        y = pil_img.height - text_height - 20
    else:
        x = (pil_img.width - text_width) // 2
        y = pil_img.height - text_height - 20
    
    draw.text((x, y), text, fill=color, font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    return (x, y, text_width, text_height)


def draw_horns(pil_img, x_pos=None, y_pos=None, scale=1.0):
    draw = ImageDraw.Draw(pil_img)
    width, height = pil_img.size
    
    base_horn_width = int((width // 10) * scale)
    base_horn_height = int((height // 8) * scale)
    
    if x_pos is None:
        left_horn_x = width // 3
        right_horn_x = 2 * width // 3
    else:
        left_horn_x = x_pos - base_horn_width
        right_horn_x = x_pos + base_horn_width
    
    if y_pos is None:
        horn_y = height // 8
    else:
        horn_y = y_pos
    
    horn_points_left = [
        (left_horn_x, horn_y + base_horn_height),
        (left_horn_x - base_horn_width // 2, horn_y),
        (left_horn_x + base_horn_width // 2, horn_y)
    ]
    
    horn_points_right = [
        (right_horn_x, horn_y + base_horn_height),
        (right_horn_x - base_horn_width // 2, horn_y),
        (right_horn_x + base_horn_width // 2, horn_y)
    ]
    
    draw.polygon(horn_points_left, fill=(139, 69, 19), outline=(101, 67, 33))
    draw.polygon(horn_points_right, fill=(139, 69, 19), outline=(101, 67, 33))


def draw_mustache(pil_img, x_pos=None, y_pos=None, scale=1.0):
    draw = ImageDraw.Draw(pil_img)
    width, height = pil_img.size
    
    base_mustache_width = int((width // 6) * scale)
    base_mustache_height = int((height // 20) * scale)
    
    if x_pos is None:
        center_x = width // 2
    else:
        center_x = x_pos
    
    if y_pos is None:
        center_y = 2 * height // 3
    else:
        center_y = y_pos
    
    ellipse_coords = [
        center_x - base_mustache_width, center_y - base_mustache_height,
        center_x + base_mustache_width, center_y + base_mustache_height
    ]
    
    draw.ellipse(ellipse_coords, fill=(0, 0, 0))
    
    left_curve = [
        center_x - base_mustache_width // 2, center_y,
        center_x - base_mustache_width, center_y - base_mustache_height // 2
    ]
    right_curve = [
        center_x + base_mustache_width // 2, center_y,
        center_x + base_mustache_width, center_y - base_mustache_height // 2
    ]
    
    curve_size = int(10 * scale)
    draw.ellipse([left_curve[0] - curve_size, left_curve[1] - curve_size//2, 
                 left_curve[0] + curve_size, left_curve[1] + curve_size//2], fill=(0, 0, 0))
    draw.ellipse([right_curve[0] - curve_size, right_curve[1] - curve_size//2, 
                 right_curve[0] + curve_size, right_curve[1] + curve_size//2], fill=(0, 0, 0))


def apply_image_effects(img, rotation=0, text="", font_size=40, text_color=(255, 255, 255), text_position="bottom", text_bold=False, text_italic=False, text_x=None, text_y=None, elements=None):
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    
    if rotation != 0:
        pil_img = pil_img.rotate(rotation, expand=True, fillcolor=(255, 255, 255))
    
    if elements:
        for element in elements:
            if element['type'] == 'horns':
                draw_horns(pil_img, element.get('x'), element.get('y'), element.get('scale', 1.0))
            elif element['type'] == 'mustache':
                draw_mustache(pil_img, element.get('x'), element.get('y'), element.get('scale', 1.0))
    
    text_bounds = None
    if text and text.strip():
        text_bounds = add_text_overlay(pil_img, text, font_size, text_color, text_position, text_bold, text_italic, text_x, text_y)
    
    final_img = np.array(pil_img)
    return cv2.cvtColor(final_img, cv2.COLOR_RGB2BGR), text_bounds 