"""
GIF Angle Labeling Tool

A graphical user interface (GUI) application for labeling the angle of particle
movement in animated GIFs. The tool allows for rapid, mouse-based selection,
reviewing, and re-labeling of angles.

Dependencies:
- Pillow: For handling animated GIF files.
- tkinter: For the GUI (standard library).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageSequence
import os
import csv
import math

# --- Configuration ---
GIF_DIRECTORY = "uncertainty_sample"
CSV_FILE = "labels_100.csv"
CANVAS_WIDTH = 400
CANVAS_HEIGHT = 200

# --- NEW: Animation Speed Configuration ---
# The delay between frames in milliseconds. Lower is faster.
MIN_DELAY_MS = 10   # Very fast (50 FPS)
MAX_DELAY_MS = 100  # Quite slow (4 FPS)
DEFAULT_SPEED = 5   # Default speed level on a 1-10 scale.
MIN_SPEED_LEVEL = 1
MAX_SPEED_LEVEL = 10

class AngleLabeler:
    """
    The main application class. It encapsulates the GUI, event handling,
    and all the logic for loading, displaying, and saving angle labels.
    """
    def __init__(self, root, gif_folder, csv_path):
        """Initializes the main application window and its components."""
        self.root = root
        self.gif_folder = gif_folder
        self.csv_path = csv_path
        
        self.all_gifs = []
        self.labels = {}
        self.current_gif_index = 0
        
        # --- Session-based progress tracking ---
        self.total_unlabeled_at_start = 0
        self.labeled_this_session = 0
        self.newly_labeled_in_session = set() # NEW: Tracks new labels for accurate undo.
        
        self.gif_frames = []
        self.current_frame_index = 0
        self.animation_job = None
        
        self.selected_angle = None

        self.root.title("GIF Angle Labeler")
        self.root.resizable(False, False)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.canvas = tk.Canvas(main_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="black")
        self.canvas.grid(row=0, column=0, columnspan=3, pady=5)
        self.image_on_canvas = self.canvas.create_image(CANVAS_WIDTH/2, CANVAS_HEIGHT/2, anchor=tk.CENTER)
        
        self.selected_line = self.canvas.create_line(0,0,0,0, fill="red", width=2, state=tk.HIDDEN)
        self.hover_line = self.canvas.create_line(0,0,0,0, fill="red", width=2, dash=(4, 4))

        self.filename_label = ttk.Label(main_frame, text="Filename: N/A", font=("Helvetica", 10))
        self.filename_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.progress_label = ttk.Label(main_frame, text="Session Progress: 0/0", font=("Helvetica", 10))
        self.progress_label.grid(row=2, column=0, columnspan=3, sticky=tk.W)
        self.angle_value_label = ttk.Label(main_frame, text="Move mouse to select angle", font=("Helvetica", 12))
        self.angle_value_label.grid(row=3, column=0, columnspan=3, pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Back (←)", command=self.go_to_previous_gif).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Next (→)", command=self.save_and_go_to_next_sequential).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Next Unlabeled", command=self.find_and_go_to_next_unlabeled).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Undo", command=self.undo_current_selection).pack(side=tk.LEFT, padx=5)

        speed_frame = ttk.Frame(main_frame)
        speed_frame.grid(row=5, column=0, columnspan=3, pady=(10, 0), sticky="ew")
        speed_frame.columnconfigure(1, weight=1)
        ttk.Label(speed_frame, text="Speed:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.animation_speed_var = tk.IntVar(value=DEFAULT_SPEED)
        speed_slider = ttk.Scale(speed_frame, from_=MIN_SPEED_LEVEL, to=MAX_SPEED_LEVEL, orient=tk.HORIZONTAL, variable=self.animation_speed_var)
        speed_slider.grid(row=0, column=1, sticky="ew")

        self.root.bind('<Motion>', self.on_mouse_move)
        self.root.bind('<Button-1>', self.on_mouse_click)
        self.root.bind('<Right>', self.save_and_go_to_next_sequential)
        self.root.bind('<Left>', self.go_to_previous_gif)

        self.initialize_data_and_load()

    def initialize_data_and_load(self):
        # This method is unchanged.
        if not os.path.exists(self.gif_folder):
            messagebox.showerror("Error", f"The directory '{self.gif_folder}' was not found.")
            self.root.quit()
            return
            
        self.all_gifs = sorted([f for f in os.listdir(self.gif_folder) if f.lower().endswith('.gif')])
        if not self.all_gifs:
            messagebox.showinfo("Information", f"No GIFs found in '{self.gif_folder}'.")
            self.root.quit()
            return
        
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row: self.labels[row[0]] = float(row[1])
            except (IOError, IndexError, ValueError) as e:
                messagebox.showerror("CSV Error", f"Could not read {self.csv_path}.\nError: {e}")
                self.root.quit()
                return
        
        self.total_unlabeled_at_start = len(self.all_gifs) - len(self.labels)
        self.labeled_this_session = 0
        self.newly_labeled_in_session.clear() # Reset for the new session.
        self.update_progress()

        start_index = 0
        for i, filename in enumerate(self.all_gifs):
            if filename not in self.labels:
                start_index = i
                break
        else:
            start_index = 0

        self.load_gif_at_index(start_index)

    def go_to_next_gif(self, event=None):
        # This method is unchanged.
        if self.current_gif_index < len(self.all_gifs) - 1:
            self.load_gif_at_index(self.current_gif_index + 1)
        else:
            messagebox.showinfo("End of List", "You have reached the last GIF.")

    def go_to_previous_gif(self, event=None):
        # This method is unchanged.
        if self.current_gif_index > 0:
            self.load_gif_at_index(self.current_gif_index - 1)
        else:
            messagebox.showinfo("Start of List", "You are at the first GIF.")

    def find_and_go_to_next_unlabeled(self, event=None):
        # This method is unchanged.
        self._save_current_selection_if_exists()
        
        start_search_index = self.current_gif_index
        num_gifs = len(self.all_gifs)

        for i in range(1, num_gifs):
            check_index = (start_search_index + i) % num_gifs
            filename = self.all_gifs[check_index]
            if filename not in self.labels:
                self.load_gif_at_index(check_index)
                return

        messagebox.showinfo("Complete!", "All GIFs are now labeled. You can continue to review them with the arrow keys.")
        self.go_to_next_gif()

    def load_gif_at_index(self, index):
        # This method is unchanged.
        if not (0 <= index < len(self.all_gifs)):
            return

        self.current_gif_index = index
        filename = self.all_gifs[self.current_gif_index]
        
        if self.animation_job: self.root.after_cancel(self.animation_job)
        self.selected_angle = None
        
        self.draw_angle_line(90, self.hover_line)
        
        filepath = os.path.join(self.gif_folder, filename)
        self.gif_frames = []
        try:
            with Image.open(filepath) as img:
                for frame in ImageSequence.Iterator(img):
                    resized_frame = frame.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(resized_frame.convert("RGBA")))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load {filename}.\nError: {e}")
            self.go_to_next_gif()
            return

        self.current_frame_index = 0
        self.animate_gif()
        
        self.filename_label.config(text=f"[{self.current_gif_index + 1}/{len(self.all_gifs)}] {filename}")

        if filename in self.labels:
            self.selected_angle = self.labels[filename]
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)
            self.angle_value_label.config(text=f"Saved: {self.selected_angle:.1f}° (Click to change)")
        else:
            self.canvas.itemconfig(self.selected_line, state=tk.HIDDEN)
            self.angle_value_label.config(text="Move mouse to select angle")
    
    ### MODIFIED: This function now tracks new labels in the session set. ###
    def _save_current_selection_if_exists(self):
        """
        Checks if an angle has been selected. If so, saves it and updates
        the session counter if the label is new.
        """
        if self.selected_angle is not None:
            filename = self.all_gifs[self.current_gif_index]
            
            is_new_label = filename not in self.labels
            
            self.labels[filename] = self.selected_angle
            self._write_labels_to_csv()
            
            if is_new_label:
                self.labeled_this_session += 1
                self.newly_labeled_in_session.add(filename) # Add to our session tracker
                self.update_progress()
    
    def _write_labels_to_csv(self):
        # This method is unchanged.
        try:
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'angle'])
                for fname in self.all_gifs:
                    if fname in self.labels:
                        writer.writerow([fname, f"{self.labels[fname]:.2f}"])
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not write to {self.csv_path}.\nError: {e}")

    def save_and_go_to_next_sequential(self, event=None):
        # This method is unchanged.
        self._save_current_selection_if_exists()
        self.go_to_next_gif()
    
    ### MODIFIED: This function now accurately updates session progress on undo. ###
    def undo_current_selection(self, event=None):
        """
        Removes the saved label for the currently displayed GIF. If the label
        was created in this session, it decrements the session counter.
        """
        filename = self.all_gifs[self.current_gif_index]
        
        if filename in self.labels:
            # Check if this was a label made during the current session.
            if filename in self.newly_labeled_in_session:
                self.newly_labeled_in_session.remove(filename)
                self.labeled_this_session -= 1
                self.update_progress() # Update the display

            del self.labels[filename]
            self._write_labels_to_csv()
            self.selected_angle = None
            self.canvas.itemconfig(self.selected_line, state=tk.HIDDEN)
            self.total_unlabeled_at_start += 1
            self.update_progress()
            self.angle_value_label.config(text="Move mouse to select angle")
            self.root.bell()
        else:
            pass

    def update_progress(self):
        # This method is unchanged.
        total_str = str(self.total_unlabeled_at_start) if self.total_unlabeled_at_start > 0 else "-"
        session_str = str(self.labeled_this_session)
        self.progress_label.config(text=f"Session Progress: {session_str}/{total_str}")

    def _get_current_delay(self):
        # This method is unchanged.
        current_speed = self.animation_speed_var.get()
        speed_range = MAX_SPEED_LEVEL - MIN_SPEED_LEVEL
        if speed_range == 0: return MIN_DELAY_MS
        delay_range = MAX_DELAY_MS - MIN_DELAY_MS
        percent_speed = (current_speed - MIN_SPEED_LEVEL) / speed_range
        delay = MAX_DELAY_MS - (percent_speed * delay_range)
        return int(delay)

    def animate_gif(self):
        # This method is unchanged.
        if not self.gif_frames: return
        frame = self.gif_frames[self.current_frame_index]
        self.canvas.itemconfig(self.image_on_canvas, image=frame)
        self.current_frame_index = (self.current_frame_index + 1) % len(self.gif_frames)
        delay = self._get_current_delay()
        self.animation_job = self.root.after(delay, self.animate_gif)

    def _get_canvas_coords(self, event):
        # This method is unchanged.
        canvas_x = event.x_root - self.canvas.winfo_rootx()
        canvas_y = event.y_root - self.canvas.winfo_rooty()
        return canvas_x, canvas_y

    def calculate_angle_from_coords(self, x, y):
        # This method is unchanged.
        origin_x = CANVAS_WIDTH / 2
        origin_y = 0
        rads = math.atan2(y - origin_y, x - origin_x)
        degs = math.degrees(rads)
        angle = 180 - degs
        return max(0, min(180, angle))

    def on_mouse_move(self, event):
        # This method is unchanged.
        x, y = self._get_canvas_coords(event)
        if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
            hover_angle = self.calculate_angle_from_coords(x, y)
            if self.selected_angle is not None:
                self.angle_value_label.config(text=f"Hover: {hover_angle:.1f}° | Selected: {self.selected_angle:.1f}°")
            else:
                self.angle_value_label.config(text=f"Angle: {hover_angle:.1f}°")
            self.draw_angle_line(hover_angle, self.hover_line)
    
    def on_mouse_click(self, event):
        # This method is unchanged.
        x, y = self._get_canvas_coords(event)
        if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
            angle = self.calculate_angle_from_coords(x, y)
            self.selected_angle = angle
            self.angle_value_label.config(text=f"Hover: {angle:.1f}° | Selected: {self.selected_angle:.1f}°")
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)

    def draw_angle_line(self, angle, line_widget):
        # This method is unchanged.
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