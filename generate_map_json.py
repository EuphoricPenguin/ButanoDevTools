#!/usr/bin/env python3
"""
Generate JSON descriptor files for all .tmx files in a selected maps folder.
This script parses Tiled map files and creates corresponding JSON files
for use with butano-tiled.
"""

import os
import json
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

def get_layer_names(tmx_file):
    """
    Extract all layer names from a .tmx file.
    
    :param tmx_file: Path to the .tmx file
    :returns: List of layer names
    """
    tree = ET.parse(tmx_file)
    root = tree.getroot()
    
    layer_names = []
    
    # Find all layer elements
    for layer in root.findall('.//layer'):
        name = layer.get('name')
        if name:
            layer_names.append(name)
    
    return layer_names

def generate_json_descriptor(tmx_file, json_file):
    """
    Generate a JSON descriptor file for a .tmx file.
    
    :param tmx_file: Path to the .tmx file
    :param json_file: Path to the output .json file
    :returns: Tuple of (success, message)
    """
    try:
        layer_names = get_layer_names(tmx_file)
        
        # Create the JSON descriptor
        descriptor = {
            "graphics": layer_names,
            "objects": [],
            "tiles": []
        }
        
        # Write the JSON file
        with open(json_file, 'w') as f:
            json.dump(descriptor, f, indent=4)
        
        return True, f"Generated: {os.path.basename(json_file)}\n  Graphics layers: {layer_names}"
    except Exception as e:
        return False, f"Error generating {os.path.basename(json_file)}: {str(e)}"

def process_maps_folder(maps_folder, log_widget):
    """
    Process all .tmx files in the maps folder.
    
    :param maps_folder: Path to the maps folder
    :param log_widget: Tkinter text widget for logging
    """
    if not os.path.exists(maps_folder):
        log_widget.insert(tk.END, f"Error: '{maps_folder}' folder not found!\n")
        return
    
    # Find all .tmx files in the maps folder
    tmx_files = []
    for file in os.listdir(maps_folder):
        if file.endswith('.tmx'):
            tmx_files.append(os.path.join(maps_folder, file))
    
    if not tmx_files:
        log_widget.insert(tk.END, f"No .tmx files found in '{maps_folder}' folder!\n")
        return
    
    log_widget.insert(tk.END, f"Found {len(tmx_files)} .tmx file(s) in '{maps_folder}' folder:\n")
    for tmx_file in tmx_files:
        log_widget.insert(tk.END, f"  - {os.path.basename(tmx_file)}\n")
    log_widget.insert(tk.END, "\n")
    
    # Generate JSON files for each .tmx file
    generated_count = 0
    skipped_count = 0
    
    for tmx_file in tmx_files:
        # Create the JSON filename (same base name, .json extension)
        json_file = os.path.splitext(tmx_file)[0] + '.json'
        
        # Check if JSON file already exists
        if os.path.exists(json_file):
            log_widget.insert(tk.END, f"Skipping: {os.path.basename(json_file)} (already exists)\n")
            skipped_count += 1
        else:
            success, message = generate_json_descriptor(tmx_file, json_file)
            log_widget.insert(tk.END, message + "\n")
            if success:
                generated_count += 1
    
    log_widget.insert(tk.END, f"\nSummary: Generated {generated_count} file(s), Skipped {skipped_count} file(s)\n")
    log_widget.insert(tk.END, "Done! You can now run 'make' to build your maps.\n")
    log_widget.see(tk.END)

def browse_folder(entry_widget):
    """
    Open a folder browser dialog and update the entry widget.
    
    :param entry_widget: Tkinter entry widget to update
    """
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def main():
    """Main function with tkinter GUI."""
    root = tk.Tk()
    root.title("Butano-Tiled JSON Generator")
    root.geometry("600x500")
    root.resizable(True, True)
    
    # Create main frame
    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Folder selection
    folder_frame = tk.Frame(main_frame)
    folder_frame.pack(fill=tk.X, pady=(0, 10))
    
    tk.Label(folder_frame, text="Maps Folder:").pack(side=tk.LEFT)
    
    folder_entry = tk.Entry(folder_frame)
    folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
    folder_entry.insert(0, "maps")
    
    browse_button = tk.Button(folder_frame, text="Browse...", command=lambda: browse_folder(folder_entry))
    browse_button.pack(side=tk.LEFT)
    
    # Generate button
    generate_button = tk.Button(
        main_frame, 
        text="Generate JSON Files", 
        command=lambda: process_maps_folder(folder_entry.get(), log_text),
        bg="#4CAF50",
        fg="white",
        font=("Arial", 10, "bold")
    )
    generate_button.pack(fill=tk.X, pady=(0, 10))
    
    # Log area
    tk.Label(main_frame, text="Log:").pack(anchor=tk.W)
    
    log_text = scrolledtext.ScrolledText(main_frame, height=15)
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # Initial message
    log_text.insert(tk.END, "Welcome to Butano-Tiled JSON Generator!\n")
    log_text.insert(tk.END, "Select a maps folder containing .tmx files and click 'Generate JSON Files'.\n\n")
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()