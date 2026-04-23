#!/usr/bin/env python3
"""
Generate JSON descriptor files for all .tmx files in a selected maps folder.
This script parses Tiled map files and creates corresponding JSON files
for use with butano-tiled.
"""

import os
import json
import sys
import argparse
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
        npc_positions = {}

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
            
            # Extract NPC positions from the NPCs object group
            for object_group in object_groups:
                og_name = object_group.get('name')
                if og_name and 'npc' in og_name.lower():
                    for obj in object_group.findall('object'):
                        npc_name = obj.get('name')
                        npc_x = obj.get('x')
                        npc_y = obj.get('y')
                        if npc_name and npc_x and npc_y:
                            # Convert pixel coordinates to tile coordinates (16x16 tiles)
                            tile_x = int(npc_x) // 16
                            tile_y = int(npc_y) // 16
                            npc_positions[npc_name] = {
                                "tile_x": tile_x,
                                "tile_y": tile_y,
                                "pixel_x": int(npc_x),
                                "pixel_y": int(npc_y)
                            }

        descriptor = {
            "graphics": all_graphics,
            "objects": all_objects,
            "tiles": all_tiles
        }
        
        # Add NPC positions if any were found
        if npc_positions:
            descriptor["npcs"] = npc_positions

        with open(json_file, 'w') as f:
            json.dump(descriptor, f, indent=4)

        return True, f"Generated: {os.path.basename(json_file)}\n  Graphics: {all_graphics}\n  Objects: {all_objects}\n  Tiles: {all_tiles}\n  NPCs: {list(npc_positions.keys())}"
    except Exception as e:
        return False, f"Error generating {os.path.basename(json_file)}: {str(e)}"


def process_maps_folder(maps_folder, log_widget=None, force_overwrite=False):
    """
    Process maps folder and generate JSON descriptors.
    If log_widget is None, output goes to stdout (CLI mode).
    If force_overwrite is True, regenerate all JSON files even if they exist.
    """
    def log_message(message):
        if log_widget is not None:
            log_widget.insert(tk.END, message + "\n")
        else:
            print(message)

    if not os.path.exists(maps_folder):
        log_message(f"Error: '{maps_folder}' folder not found!")
        return False

    tmx_files = [
        os.path.join(maps_folder, f)
        for f in os.listdir(maps_folder)
        if f.endswith('.tmx')
    ]

    if not tmx_files:
        log_message(f"No .tmx files found in '{maps_folder}'!")
        return False

    log_message(f"Found {len(tmx_files)} .tmx file(s):")
    for tmx_file in tmx_files:
        log_message(f"  - {os.path.basename(tmx_file)}")
    log_message("")

    generated_count = 0
    skipped_count = 0

    for tmx_file in tmx_files:
        json_file = os.path.splitext(tmx_file)[0] + '.json'

        if os.path.exists(json_file) and not force_overwrite:
            log_message(f"Skipping: {os.path.basename(json_file)} (already exists)")
            skipped_count += 1
        else:
            success, message = generate_json_descriptor(tmx_file, json_file)
            log_message(message)
            if success:
                generated_count += 1

    log_message(f"\nSummary: Generated {generated_count}, Skipped {skipped_count}")
    log_message("Done! Review the JSON files before running make.")
    if log_widget is not None:
        log_widget.see(tk.END)
    
    return True


def browse_folder(entry_widget):
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)


def main_gui():
    """Launch the GUI interface."""
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


def main():
    """Main entry point - handles both CLI and GUI modes."""
    parser = argparse.ArgumentParser(
        description="Generate JSON descriptor files for Tiled map files (.tmx)",
        epilog="If --maps-dir is not provided, the GUI will launch."
    )
    parser.add_argument(
        '--maps-dir',
        '-d',
        type=str,
        help='Path to the maps directory (can be absolute or relative). If provided, runs in CLI mode.'
    )
    parser.add_argument(
        '--force',
        '-f',
        action='store_true',
        help='Overwrite existing JSON files instead of skipping them.'
    )
    
    args = parser.parse_args()
    
    if args.maps_dir:
        # CLI mode
        maps_dir = os.path.abspath(args.maps_dir)
        process_maps_folder(maps_dir, force_overwrite=args.force)
    else:
        # GUI mode
        main_gui()


if __name__ == "__main__":
    main()