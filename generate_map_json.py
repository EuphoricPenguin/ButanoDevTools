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
from tkinter import filedialog, scrolledtext


def generate_json_descriptor(tmx_file, json_file):
    try:
        tree = ET.parse(tmx_file)
        root = tree.getroot()

        groups = sorted(root.findall('group'), key=lambda g: g.get('name'))

        all_graphics = []
        all_objects = []
        all_tiles = []

        for group in groups:
            group_name = group.get('name')

            for layer in group.findall('layer'):
                layer_name = layer.get('name')
                path = f"{group_name}/{layer_name}"
                if 'collision' in layer_name.lower():
                    all_tiles.append(path)
                else:
                    all_graphics.append(path)

            object_groups = group.findall('objectgroup')
            if len(object_groups) == 1:
                all_objects.append(f"{group_name}/{object_groups[0].get('name')}")
            elif len(object_groups) > 1:
                all_objects.append([
                    f"{group_name}/{og.get('name')}" for og in object_groups
                ])

        descriptor = {
            "graphics": all_graphics,
            "objects": all_objects,
            "tiles": all_tiles
        }

        with open(json_file, 'w') as f:
            json.dump(descriptor, f, indent=4)

        return True, f"Generated: {os.path.basename(json_file)}\n  Graphics: {all_graphics}\n  Objects: {all_objects}\n  Tiles: {all_tiles}"
    except Exception as e:
        return False, f"Error generating {os.path.basename(json_file)}: {str(e)}"


def process_maps_folder(maps_folder, log_widget):
    if not os.path.exists(maps_folder):
        log_widget.insert(tk.END, f"Error: '{maps_folder}' folder not found!\n")
        return

    tmx_files = [
        os.path.join(maps_folder, f)
        for f in os.listdir(maps_folder)
        if f.endswith('.tmx')
    ]

    if not tmx_files:
        log_widget.insert(tk.END, f"No .tmx files found in '{maps_folder}'!\n")
        return

    log_widget.insert(tk.END, f"Found {len(tmx_files)} .tmx file(s):\n")
    for tmx_file in tmx_files:
        log_widget.insert(tk.END, f"  - {os.path.basename(tmx_file)}\n")
    log_widget.insert(tk.END, "\n")

    generated_count = 0
    skipped_count = 0

    for tmx_file in tmx_files:
        json_file = os.path.splitext(tmx_file)[0] + '.json'

        if os.path.exists(json_file):
            log_widget.insert(tk.END, f"Skipping: {os.path.basename(json_file)} (already exists)\n")
            skipped_count += 1
        else:
            success, message = generate_json_descriptor(tmx_file, json_file)
            log_widget.insert(tk.END, message + "\n")
            if success:
                generated_count += 1

    log_widget.insert(tk.END, f"\nSummary: Generated {generated_count}, Skipped {skipped_count}\n")
    log_widget.insert(tk.END, "Done! Review the JSON files before running make.\n")
    log_widget.see(tk.END)


def browse_folder(entry_widget):
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)


def main():
    root = tk.Tk()
    root.title("Butano-Tiled JSON Generator")
    root.geometry("600x500")
    root.resizable(True, True)

    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    folder_frame = tk.Frame(main_frame)
    folder_frame.pack(fill=tk.X, pady=(0, 10))

    tk.Label(folder_frame, text="Maps Folder:").pack(side=tk.LEFT)

    folder_entry = tk.Entry(folder_frame)
    folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
    folder_entry.insert(0, "maps")

    tk.Button(folder_frame, text="Browse...", command=lambda: browse_folder(folder_entry)).pack(side=tk.LEFT)

    tk.Button(
        main_frame,
        text="Generate JSON Files",
        command=lambda: process_maps_folder(folder_entry.get(), log_text),
        bg="#4CAF50",
        fg="white",
        font=("Arial", 10, "bold")
    ).pack(fill=tk.X, pady=(0, 10))

    tk.Label(main_frame, text="Log:").pack(anchor=tk.W)

    log_text = scrolledtext.ScrolledText(main_frame, height=15)
    log_text.pack(fill=tk.BOTH, expand=True)

    log_text.insert(tk.END, "Welcome to Butano-Tiled JSON Generator!\n")
    log_text.insert(tk.END, "Select a maps folder and click 'Generate JSON Files'.\n")
    log_text.insert(tk.END, "Layers with 'collision' in the name go to tiles; everything else goes to graphics.\n")
    log_text.insert(tk.END, "Review and edit the generated JSON files before running make.\n\n")

    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f'+{x}+{y}')

    root.mainloop()


if __name__ == "__main__":
    main()