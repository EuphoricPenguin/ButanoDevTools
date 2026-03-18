#!/usr/bin/env python3
"""
Arlo Graphics Tool - Tkinter GUI for converting images to Butano-compatible BMP format.

Features:
1. Preview image display
2. File open dialog for PNG/BMP images
3. Save as dialog for BMP output
4. JSON configuration generation
5. Real-time preview of conversion settings
6. Eyedropper tool for alpha channel selection
7. Valid sprite size enforcement for Butano compatibility
8. Spritesheet support for any size
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk
import json
import os
import sys

class ArloGraphicsTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Arlo Graphics Tool")
        self.root.geometry("900x700")
        
        # Current image and paths
        self.current_image = None
        self.image_path = None
        self.bmp_path = None
        self.json_path = None
        
        # Eyedropper settings
        self.alpha_color = (0, 255, 0)  # Default green for transparency
        self.eyedropper_active = False
        
        # Valid GBA sprite sizes (width x height in pixels)
        # Based on GBA hardware limitations and Butano compatibility
        self.valid_sprite_sizes = [
            (8, 8), (16, 8), (8, 16), (16, 16), (32, 8), (8, 32),
            (32, 16), (16, 32), (32, 32), (64, 32), (32, 64), (64, 64)
        ]
        
        # Conversion settings
        self.settings = {
            "type": "sprite",
            "width": 16,
            "height": 20,
            "bpp_mode": "bpp_4",
            "colors_count": 16,
            "compression": "auto",
            "alpha_color": "#00FF00"  # Default green for transparency
        }
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frames
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Top button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # Buttons
        ttk.Button(button_frame, text="Open Image", command=self.open_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save BMP As...", command=self.save_bmp_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Generate JSON", command=self.generate_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview Conversion", command=self.preview_conversion).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Eyedropper Tool", command=self.toggle_eyedropper).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Validate Sprite Size", command=self.validate_sprite_size).pack(side=tk.LEFT, padx=5)
        
        # Left panel - image preview
        preview_frame = ttk.LabelFrame(main_frame, text="Image Preview", padding="10")
        preview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        self.preview_label = ttk.Label(preview_frame, text="No image loaded", background="white")
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - settings and info
        settings_frame = ttk.LabelFrame(main_frame, text="Conversion Settings", padding="10")
        settings_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Settings controls
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.BOTH, expand=True)
        
        # Type setting
        ttk.Label(settings_grid, text="Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value=self.settings["type"])
        type_combo = ttk.Combobox(settings_grid, textvariable=self.type_var, 
                                  values=["sprite", "regular_bg_tiles", "sprite_palette", "sprite_tiles"], 
                                  state="readonly", width=20)
        type_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        type_combo.bind("<<ComboboxSelected>>", self.update_settings)
        
        # Width setting
        ttk.Label(settings_grid, text="Width:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.width_var = tk.StringVar(value=str(self.settings["width"]))
        width_spin = ttk.Spinbox(settings_grid, from_=1, to=256, textvariable=self.width_var, 
                                 width=18, command=self.update_settings)
        width_spin.grid(row=1, column=1, sticky=tk.W, pady=5)
        width_spin.bind("<KeyRelease>", self.update_settings)
        
        # Height setting
        ttk.Label(settings_grid, text="Height:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.height_var = tk.StringVar(value=str(self.settings["height"]))
        height_spin = ttk.Spinbox(settings_grid, from_=1, to=256, textvariable=self.height_var, 
                                  width=18, command=self.update_settings)
        height_spin.grid(row=2, column=1, sticky=tk.W, pady=5)
        height_spin.bind("<KeyRelease>", self.update_settings)
        
        # BPP mode setting
        ttk.Label(settings_grid, text="BPP Mode:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.bpp_var = tk.StringVar(value=self.settings["bpp_mode"])
        bpp_combo = ttk.Combobox(settings_grid, textvariable=self.bpp_var, 
                                 values=["bpp_4", "bpp_8"], state="readonly", width=20)
        bpp_combo.grid(row=3, column=1, sticky=tk.W, pady=5)
        bpp_combo.bind("<<ComboboxSelected>>", self.update_settings)
        
        # Colors count setting
        ttk.Label(settings_grid, text="Colors Count:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.colors_var = tk.StringVar(value=str(self.settings["colors_count"]))
        colors_spin = ttk.Spinbox(settings_grid, from_=1, to=256, textvariable=self.colors_var, 
                                  width=18, command=self.update_settings)
        colors_spin.grid(row=4, column=1, sticky=tk.W, pady=5)
        colors_spin.bind("<KeyRelease>", self.update_settings)
        
        # Compression setting
        ttk.Label(settings_grid, text="Compression:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.compression_var = tk.StringVar(value=self.settings["compression"])
        compression_combo = ttk.Combobox(settings_grid, textvariable=self.compression_var, 
                                         values=["auto", "none", "lz77", "run_length", "huffman"], 
                                         state="readonly", width=20)
        compression_combo.grid(row=5, column=1, sticky=tk.W, pady=5)
        compression_combo.bind("<<ComboboxSelected>>", self.update_settings)
        
        # Info panel at bottom
        info_frame = ttk.LabelFrame(main_frame, text="File Information", padding="10")
        info_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E))
        
        self.info_text = tk.Text(info_frame, height=6, width=80, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        self.info_text.config(state=tk.DISABLED)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Update info display
        self.update_info()
        
    def update_settings(self, event=None):
        """Update settings from UI controls"""
        try:
            self.settings["type"] = self.type_var.get()
            self.settings["width"] = int(self.width_var.get())
            self.settings["height"] = int(self.height_var.get())
            self.settings["bpp_mode"] = self.bpp_var.get()
            self.settings["colors_count"] = int(self.colors_var.get())
            self.settings["compression"] = self.compression_var.get()
            
            # Update colors count based on BPP mode
            if self.settings["bpp_mode"] == "bpp_4":
                self.settings["colors_count"] = 16
                self.colors_var.set("16")
            elif self.settings["bpp_mode"] == "bpp_8":
                self.settings["colors_count"] = 256
                self.colors_var.set("256")
                
            self.update_info()
            self.status_var.set("Settings updated")
        except ValueError:
            pass
    
    def update_info(self):
        """Update information display"""
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        
        if self.image_path:
            self.info_text.insert(tk.END, f"Loaded Image: {os.path.basename(self.image_path)}\n")
            self.info_text.insert(tk.END, f"Path: {self.image_path}\n\n")
        
        self.info_text.insert(tk.END, "Current Settings:\n")
        for key, value in self.settings.items():
            self.info_text.insert(tk.END, f"  {key}: {value}\n")
        
        if self.bmp_path:
            self.info_text.insert(tk.END, f"\nBMP Output: {os.path.basename(self.bmp_path)}\n")
        
        if self.json_path:
            self.info_text.insert(tk.END, f"JSON Output: {os.path.basename(self.json_path)}\n")
        
        self.info_text.config(state=tk.DISABLED)
    
    def open_image(self):
        """Open an image file"""
        filetypes = [
            ("Image files", "*.png *.bmp *.jpg *.jpeg"),
            ("PNG files", "*.png"),
            ("BMP files", "*.bmp"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select an image file",
            filetypes=filetypes
        )
        
        if filename:
            try:
                self.image_path = filename
                self.current_image = Image.open(filename)
                
                # Update settings with image dimensions
                self.settings["width"] = self.current_image.width
                self.settings["height"] = self.current_image.height
                self.width_var.set(str(self.current_image.width))
                self.height_var.set(str(self.current_image.height))
                
                # Update preview
                self.update_preview()
                self.update_info()
                self.status_var.set(f"Loaded: {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def update_preview(self):
        """Update image preview"""
        if self.current_image:
            # Resize for preview while maintaining aspect ratio
            preview_size = (300, 300)
            img = self.current_image.copy()
            img.thumbnail(preview_size, Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo  # Keep reference
        else:
            self.preview_label.config(image="", text="No image loaded")
    
    def save_bmp_as(self):
        """Save current image as BMP"""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save BMP As",
            defaultextension=".bmp",
            filetypes=[("BMP files", "*.bmp"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Convert to Butano-compatible BMP
                bmp_path = self.convert_to_butano_bmp(self.image_path, filename)
                self.bmp_path = bmp_path
                self.update_info()
                self.status_var.set(f"Saved BMP: {os.path.basename(filename)}")
                messagebox.showinfo("Success", f"BMP saved successfully!\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save BMP: {str(e)}")
    
    def generate_json(self):
        """Generate JSON configuration file"""
        if not self.image_path:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        
        # Suggest filename based on image name
        base_name = os.path.splitext(os.path.basename(self.image_path))[0]
        default_name = f"{base_name}.json"
        
        filename = filedialog.asksaveasfilename(
            title="Save JSON Configuration",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.settings, f, indent=4)
                
                self.json_path = filename
                self.update_info()
                self.status_var.set(f"Generated JSON: {os.path.basename(filename)}")
                messagebox.showinfo("Success", f"JSON configuration saved!\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save JSON: {str(e)}")
    
    def preview_conversion(self):
        """Show preview of conversion settings"""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        
        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Conversion Preview")
        preview_window.geometry("400x300")
        
        # Show settings
        text = tk.Text(preview_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert(tk.END, "Conversion Preview\n")
        text.insert(tk.END, "=" * 50 + "\n\n")
        
        text.insert(tk.END, "Image Information:\n")
        text.insert(tk.END, f"  Source: {os.path.basename(self.image_path)}\n")
        text.insert(tk.END, f"  Size: {self.current_image.width} x {self.current_image.height}\n")
        text.insert(tk.END, f"  Mode: {self.current_image.mode}\n\n")
        
        text.insert(tk.END, "Butano Settings:\n")
        for key, value in self.settings.items():
            text.insert(tk.END, f"  {key}: {value}\n")
        
        text.insert(tk.END, "\nButano Requirements:\n")
        text.insert(tk.END, "• BMP format without compression\n")
        text.insert(tk.END, "• 16 or 256 colors only (indexed)\n")
        text.insert(tk.END, "• First color in palette is transparent\n")
        text.insert(tk.END, "• No color space information\n")
        
        text.config(state=tk.DISABLED)
    
    def convert_to_butano_bmp(self, input_path, output_path):
        """Convert image to Butano-compatible BMP"""
        # Based on the original convert_arlo.py logic
        img = Image.open(input_path)
        
        print(f"Converting {input_path} to Butano-compatible BMP...")
        print(f"Original image: {img.size}, mode: {img.mode}")
        
        # Convert RGBA to indexed color with transparency
        if img.mode == 'RGBA':
            print("Processing RGBA image with transparency...")
            
            img_rgba = img.convert('RGBA')
            data = list(img_rgba.getdata())
            
            # Replace pure green with transparent
            new_data = []
            for pixel in data:
                r, g, b, a = pixel
                if (r, g, b) == (0, 255, 0):
                    # Pure green - make fully transparent
                    new_data.append((0, 0, 0, 0))
                else:
                    new_data.append((r, g, b, a))
            
            # Create new image with processed data
            img_processed = Image.new('RGBA', img.size)
            img_processed.putdata(new_data)
            
            # Convert to palette mode
            colors = 16 if self.settings["bpp_mode"] == "bpp_4" else 256
            img_palette = img_processed.convert('P', palette=Image.ADAPTIVE, colors=colors)
            
            # Create transparency palette (first entry transparent)
            palette = img_palette.getpalette()
            if palette:
                # Ensure first palette entry is black (will be transparent)
                palette[0:3] = [0, 0, 0]
                img_palette.putpalette(palette)
            
            img = img_palette
            
        elif img.mode != 'P':
            # Convert to indexed color if not already
            colors = 16 if self.settings["bpp_mode"] == "bpp_4" else 256
            img = img.convert('P', palette=Image.ADAPTIVE, colors=colors)
        
        print(f"Converted to: {img.size}, mode: {img.mode}")
        
        # Save as BMP
        img.save(output_path, 'BMP')
        print(f"Saved to: {output_path}")
        
        # Verify the file
        if os.path.exists(output_path):
            bmp_size = os.path.getsize(output_path)
            print(f"BMP file size: {bmp_size} bytes")
            
            # Try to open and check
            bmp_img = Image.open(output_path)
            print(f"BMP image: {bmp_img.size}, mode: {bmp_img.mode}")
            bmp_img.close()
        
        return output_path
    
    def toggle_eyedropper(self):
        """Toggle eyedropper mode for selecting alpha color"""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        
        self.eyedropper_active = not self.eyedropper_active
        
        if self.eyedropper_active:
            self.status_var.set("Eyedropper active - click on image to select alpha color")
            self.preview_label.config(cursor="cross")
            self.preview_label.bind("<Button-1>", self.pick_alpha_color)
        else:
            self.status_var.set("Eyedropper deactivated")
            self.preview_label.config(cursor="")
            self.preview_label.unbind("<Button-1>")
    
    def pick_alpha_color(self, event):
        """Pick alpha color from clicked position on image"""
        if not self.current_image or not self.eyedropper_active:
            return
        
        # Get click coordinates relative to preview label
        x = event.x
        y = event.y
        
        # Get preview image dimensions
        preview_width = self.preview_label.winfo_width()
        preview_height = self.preview_label.winfo_height()
        
        # Calculate scale factor from original to preview
        orig_width, orig_height = self.current_image.size
        scale_x = orig_width / preview_width if preview_width > 0 else 1
        scale_y = orig_height / preview_height if preview_height > 0 else 1
        
        # Calculate original image coordinates
        orig_x = int(x * scale_x)
        orig_y = int(y * scale_y)
        
        # Clamp to image bounds
        orig_x = max(0, min(orig_x, orig_width - 1))
        orig_y = max(0, min(orig_y, orig_height - 1))
        
        # Get pixel color
        pixel = self.current_image.getpixel((orig_x, orig_y))
        
        if len(pixel) == 4:  # RGBA
            r, g, b, a = pixel
        elif len(pixel) == 3:  # RGB
            r, g, b = pixel
            a = 255
        else:  # Grayscale or palette
            if isinstance(pixel, int):
                r = g = b = pixel
                a = 255
            else:
                r, g, b = pixel[:3]
                a = 255
        
        # Update alpha color
        self.alpha_color = (r, g, b)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.settings["alpha_color"] = hex_color
        
        # Show color picker dialog for confirmation/editing
        color = colorchooser.askcolor(
            title="Select Alpha Color",
            initialcolor=hex_color
        )
        
        if color[0]:  # User didn't cancel
            r, g, b = [int(c) for c in color[0]]
            self.alpha_color = (r, g, b)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            self.settings["alpha_color"] = hex_color
        
        # Deactivate eyedropper
        self.eyedropper_active = False
        self.preview_label.config(cursor="")
        self.preview_label.unbind("<Button-1>")
        self.status_var.set(f"Alpha color set to {hex_color}")
        self.update_info()
    
    def validate_sprite_size(self):
        """Validate current sprite size against Butano compatibility"""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        
        width = self.settings["width"]
        height = self.settings["height"]
        
        # Check if size is valid
        is_valid = (width, height) in self.valid_sprite_sizes
        
        # Create validation window
        validation_window = tk.Toplevel(self.root)
        validation_window.title("Sprite Size Validation")
        validation_window.geometry("400x300")
        
        text = tk.Text(validation_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert(tk.END, "Sprite Size Validation\n")
        text.insert(tk.END, "=" * 50 + "\n\n")
        
        text.insert(tk.END, f"Current Size: {width} x {height} pixels\n\n")
        
        if is_valid:
            text.insert(tk.END, "✅ VALID - This size is compatible with Butano!\n\n")
        else:
            text.insert(tk.END, "❌ INVALID - This size is not compatible with Butano\n\n")
            text.insert(tk.END, "Valid GBA Sprite Sizes:\n")
            for w, h in self.valid_sprite_sizes:
                text.insert(tk.END, f"  • {w} x {h}\n")
            
            text.insert(tk.END, "\nRecommendations:\n")
            text.insert(tk.END, "1. Resize your image to a valid dimension\n")
            text.insert(tk.END, "2. Use a spritesheet with valid sprite dimensions\n")
            text.insert(tk.END, "3. Check if your image is a spritesheet that can be divided\n")
        
        text.insert(tk.END, "\nButano Sprite Requirements:\n")
        text.insert(tk.END, "• Width and height must be powers of 2 (8, 16, 32, 64)\n")
        text.insert(tk.END, "• Maximum size: 64x64 pixels\n")
        text.insert(tk.END, "• Rectangular sprites allowed (e.g., 16x8, 32x16)\n")
        
        text.config(state=tk.DISABLED)
        
        # Add buttons
        button_frame = ttk.Frame(validation_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        if not is_valid:
            ttk.Button(button_frame, text="Suggest Closest Valid Size", 
                      command=lambda: self.suggest_valid_size(width, height, validation_window)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Close", command=validation_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def suggest_valid_size(self, current_width, current_height, parent_window):
        """Suggest closest valid sprite size"""
        closest_size = None
        min_distance = float('inf')
        
        for w, h in self.valid_sprite_sizes:
            # Calculate distance (Euclidean)
            distance = ((w - current_width) ** 2 + (h - current_height) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_size = (w, h)
        
        if closest_size:
            w, h = closest_size
            messagebox.showinfo("Suggested Size", 
                              f"Closest valid sprite size: {w} x {h}\n\n"
                              f"Your current size: {current_width} x {current_height}\n"
                              f"You need to resize by:\n"
                              f"  Width: {w - current_width} pixels\n"
                              f"  Height: {h - current_height} pixels")
            
            # Update settings with suggested size
            self.settings["width"] = w
            self.settings["height"] = h
            self.width_var.set(str(w))
            self.height_var.set(str(h))
            self.update_info()
            self.status_var.set(f"Updated to suggested size: {w}x{h}")
            
            parent_window.destroy()


def main():
    """Main entry point for the application"""
    root = tk.Tk()
    app = ArloGraphicsTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
