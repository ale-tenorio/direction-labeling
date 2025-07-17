import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageSequence
import os
import csv
import math
import sys

# --- Configuration ---
GIF_DIRECTORY = "gifs" 
CSV_FILE = "labels.csv"
CANVAS_WIDTH = 400
CANVAS_HEIGHT = 200

class AngleLabeler:
    def __init__(self, root, gif_folder, csv_path):
        self.root = root
        self.gif_folder = gif_folder
        self.csv_path = csv_path
        
        ### MODIFIED: New data structures for navigation ###
        self.all_gifs = []          # List of all GIF filenames
        self.labels = {}            # Dictionary to store labels: {filename: angle}
        self.current_gif_index = 0
        
        self.gif_frames = []
        self.current_frame_index = 0
        self.animation_job = None
        
        self.selected_angle = None

        # --- Setup the GUI ---
        self.root.title("GIF Angle Labeler")
        self.root.resizable(False, False)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Canvas and lines (unchanged)
        self.canvas = tk.Canvas(main_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="black")
        self.canvas.grid(row=0, column=0, columnspan=3, pady=5)
        self.image_on_canvas = self.canvas.create_image(CANVAS_WIDTH/2, CANVAS_HEIGHT/2, anchor=tk.CENTER)
        self.selected_line = self.canvas.create_line(0,0,0,0, fill="red", width=3, state=tk.HIDDEN)
        self.hover_line = self.canvas.create_line(0,0,0,0, fill="red", width=2, dash=(4, 4))

        # Labels (unchanged)
        self.filename_label = ttk.Label(main_frame, text="Filename: N/A", font=("Helvetica", 10))
        self.filename_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.progress_label = ttk.Label(main_frame, text="Progress: 0/0", font=("Helvetica", 10))
        self.progress_label.grid(row=2, column=0, columnspan=3, sticky=tk.W)
        self.angle_value_label = ttk.Label(main_frame, text="Move mouse to select angle", font=("Helvetica", 12))
        self.angle_value_label.grid(row=3, column=0, columnspan=3, pady=10)

        # Buttons (Skip button is modified)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Back (←)", command=self.go_to_previous_gif).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save & Next", command=self.save_and_next).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Skip (→)", command=self.go_to_next_gif).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Quit", command=self.root.quit).pack(side=tk.LEFT, padx=5)

        ### MODIFIED: Bind arrow keys and mouse events ###
        self.root.bind('<Motion>', self.on_mouse_move)
        self.root.bind('<Button-1>', self.on_mouse_click)
        self.root.bind('<Right>', self.go_to_next_gif)
        self.root.bind('<Left>', self.go_to_previous_gif)

        ### MODIFIED: New startup sequence ###
        self.initialize_data_and_load()

    ### NEW: Replaces old load_gif_list ###
    def initialize_data_and_load(self):
        """Loads all GIF filenames, reads existing labels, and loads the first unlabeled GIF."""
        if not os.path.exists(self.gif_folder):
            messagebox.showerror("Error", f"The directory '{self.gif_folder}' was not found.")
            self.root.quit()
            return
            
        self.all_gifs = sorted([f for f in os.listdir(self.gif_folder) if f.lower().endswith('.gif')])
        if not self.all_gifs:
            messagebox.showinfo("Information", f"No GIFs found in '{self.gif_folder}'.")
            self.root.quit()
            return
        
        # Load existing labels from CSV into the dictionary
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None) # Skip header
                    for row in reader:
                        if row: self.labels[row[0]] = float(row[1])
            except (IOError, IndexError, ValueError) as e:
                messagebox.showerror("CSV Error", f"Could not read {self.csv_path}.\nError: {e}")
                self.root.quit()
                return

        # Find the first GIF that is not in our labels dictionary
        start_index = 0
        for i, filename in enumerate(self.all_gifs):
            if filename not in self.labels:
                start_index = i
                break
        else: # If all GIFs are labeled, start at the first one
            start_index = 0

        self.load_gif_at_index(start_index)

    ### NEW: Main navigation functions ###
    def go_to_next_gif(self, event=None):
        """Loads the next GIF in the list."""
        if self.current_gif_index < len(self.all_gifs) - 1:
            self.load_gif_at_index(self.current_gif_index + 1)
        else:
            messagebox.showinfo("End of List", "You have reached the last GIF.")

    def go_to_previous_gif(self, event=None):
        """Loads the previous GIF in the list."""
        if self.current_gif_index > 0:
            self.load_gif_at_index(self.current_gif_index - 1)
        else:
            messagebox.showinfo("Start of List", "You are at the first GIF.")

    ### MODIFIED: Replaces load_next_gif with a more general function ###
    def load_gif_at_index(self, index):
        """Loads the GIF at a specific index, checking if it's already labeled."""
        if not (0 <= index < len(self.all_gifs)):
            return # Should not happen due to checks in nav functions, but safe

        self.current_gif_index = index
        filename = self.all_gifs[self.current_gif_index]
        
        # Cancel old animation and reset state
        if self.animation_job: self.root.after_cancel(self.animation_job)
        self.selected_angle = None
        self.canvas.itemconfig(self.hover_line, state=tk.NORMAL)
        
        # Load the GIF frames (stretching to fit)
        filepath = os.path.join(self.gif_folder, filename)
        self.gif_frames = []
        try:
            with Image.open(filepath) as img:
                for frame in ImageSequence.Iterator(img):
                    resized_frame = frame.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(resized_frame.convert("RGBA")))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load {filename}.\nError: {e}")
            self.go_to_next_gif() # Skip corrupted file
            return

        self.current_frame_index = 0
        self.animate_gif()
        self.update_progress()
        self.filename_label.config(text=f"Filename: {filename}")

        # Check if this GIF has a label and display it
        if filename in self.labels:
            self.selected_angle = self.labels[filename]
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)
            self.angle_value_label.config(text=f"Saved: {self.selected_angle:.1f}° (Click to change)")
        else:
            self.canvas.itemconfig(self.selected_line, state=tk.HIDDEN)
            self.angle_value_label.config(text="Move mouse to select angle")


    ### MODIFIED: The core saving logic now rewrites the file ###
    def save_and_next(self):
        """Saves or overwrites the label and moves to the next GIF."""
        if self.selected_angle is None:
            messagebox.showwarning("No Angle Selected", "Please click on the image to select an angle before saving.")
            return

        filename = self.all_gifs[self.current_gif_index]
        self.labels[filename] = self.selected_angle

        # Rewrite the entire CSV file with the updated labels dictionary
        try:
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'angle'])
                # Sort items by original all_gifs list order for consistency
                for fname in self.all_gifs:
                    if fname in self.labels:
                        writer.writerow([fname, f"{self.labels[fname]:.2f}"])
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not write to {self.csv_path}.\nError: {e}")
            return
        
        self.go_to_next_gif()
    
    def update_progress(self):
        total = len(self.all_gifs)
        current_num = self.current_gif_index + 1
        self.progress_label.config(text=f"Progress: {current_num}/{total}")

    # --- Unchanged methods below ---

    def animate_gif(self):
        if not self.gif_frames: return
        frame = self.gif_frames[self.current_frame_index]
        self.canvas.itemconfig(self.image_on_canvas, image=frame)
        self.current_frame_index = (self.current_frame_index + 1) % len(self.gif_frames)
        self.animation_job = self.root.after(100, self.animate_gif)

    def _get_canvas_coords(self, event):
        canvas_x = event.x_root - self.canvas.winfo_rootx()
        canvas_y = event.y_root - self.canvas.winfo_rooty()
        return canvas_x, canvas_y

    def calculate_angle_from_coords(self, x, y):
        origin_x = CANVAS_WIDTH / 2
        origin_y = 0
        dx = x - origin_x
        dy = y - origin_y
        rads = math.atan2(dy, dx)
        degs = math.degrees(rads)
        angle = 180 - degs
        return max(0, min(180, angle))

    def on_mouse_move(self, event):
        x, y = self._get_canvas_coords(event)
        hover_angle = self.calculate_angle_from_coords(x, y)
        
        if self.selected_angle is not None:
            self.angle_value_label.config(text=f"Hover: {hover_angle:.1f}° | Selected: {self.selected_angle:.1f}°")
        else:
            self.angle_value_label.config(text=f"Angle: {hover_angle:.1f}°")
            
        self.draw_angle_line(hover_angle, self.hover_line)
    
    def on_mouse_click(self, event):
        x, y = self._get_canvas_coords(event)
        if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
            angle = self.calculate_angle_from_coords(x, y)
            self.selected_angle = angle
            self.angle_value_label.config(text=f"Hover: {angle:.1f}° | Selected: {self.selected_angle:.1f}°")
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)

    def draw_angle_line(self, angle, line_widget):
        origin_x = CANVAS_WIDTH / 2
        origin_y = 0
        line_length = CANVAS_HEIGHT * 0.95
        angle_rad = math.radians(180 - angle)
        end_x = origin_x + line_length * math.cos(angle_rad)
        end_y = origin_y + line_length * math.sin(angle_rad)
        self.canvas.coords(line_widget, origin_x, origin_y, end_x, end_y)

if __name__ == "__main__":
    root = tk.Tk()
    app = AngleLabeler(root, GIF_DIRECTORY, CSV_FILE)
    root.mainloop()