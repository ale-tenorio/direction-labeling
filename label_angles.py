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
# These are the main settings you can adjust.
GIF_DIRECTORY = "gifs"          # The folder containing your GIF files.
CSV_FILE = "labels.csv"         # The output file where labels are saved.
CANVAS_WIDTH = 400              # The width of the GIF display area.
CANVAS_HEIGHT = 200             # The height of the GIF display area.

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
        
        # --- Data Members ---
        self.all_gifs = []          # An ordered list of all GIF filenames found.
        self.labels = {}            # A dictionary to store labels: {filename: angle}.
        self.current_gif_index = 0  # The index of the currently displayed GIF.
        
        # --- Animation State ---
        self.gif_frames = []        # A list to hold each frame of the current GIF.
        self.current_frame_index = 0
        self.animation_job = None   # A reference to the 'after' job for animation.
        
        # --- Interaction State ---
        self.selected_angle = None  # The angle currently selected by the user's click.

        # --- GUI Setup ---
        self.root.title("GIF Angle Labeler")
        self.root.resizable(False, False)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Canvas for displaying the GIF and angle lines.
        self.canvas = tk.Canvas(main_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="black")
        self.canvas.grid(row=0, column=0, columnspan=3, pady=5)
        self.image_on_canvas = self.canvas.create_image(CANVAS_WIDTH/2, CANVAS_HEIGHT/2, anchor=tk.CENTER)
        
        # Angle lines are drawn on top of the GIF.
        self.selected_line = self.canvas.create_line(0,0,0,0, fill="red", width=2, state=tk.HIDDEN)
        self.hover_line = self.canvas.create_line(0,0,0,0, fill="red", width=2, dash=(4, 4))

        # --- Information Labels ---
        self.filename_label = ttk.Label(main_frame, text="Filename: N/A", font=("Helvetica", 10))
        self.filename_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.progress_label = ttk.Label(main_frame, text="Progress: 0/0", font=("Helvetica", 10))
        self.progress_label.grid(row=2, column=0, columnspan=3, sticky=tk.W)
        self.angle_value_label = ttk.Label(main_frame, text="Move mouse to select angle", font=("Helvetica", 12))
        self.angle_value_label.grid(row=3, column=0, columnspan=3, pady=10)

        # --- Control Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Back (←)", command=self.go_to_previous_gif).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save & Next", command=self.save_and_next).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Skip (→)", command=self.go_to_next_gif).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Quit", command=self.root.quit).pack(side=tk.LEFT, padx=5)

        # --- Event Bindings ---
        # Bind events to the root window to capture them anywhere inside the app.
        self.root.bind('<Motion>', self.on_mouse_move)
        self.root.bind('<Button-1>', self.on_mouse_click)
        self.root.bind('<Right>', self.go_to_next_gif)
        self.root.bind('<Left>', self.go_to_previous_gif)

        # Start the application by loading data.
        self.initialize_data_and_load()

    def initialize_data_and_load(self):
        """
        Scans the GIF directory, loads existing labels from the CSV, and
        navigates to the first unlabeled item.
        """
        if not os.path.exists(self.gif_folder):
            messagebox.showerror("Error", f"The directory '{self.gif_folder}' was not found.")
            self.root.quit()
            return
            
        # Find all GIFs and sort them for a consistent order.
        self.all_gifs = sorted([f for f in os.listdir(self.gif_folder) if f.lower().endswith('.gif')])
        if not self.all_gifs:
            messagebox.showinfo("Information", f"No GIFs found in '{self.gif_folder}'.")
            self.root.quit()
            return
        
        # Load existing labels from the CSV into the labels dictionary for quick lookups.
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None) # Skip the header row.
                    for row in reader:
                        if row: self.labels[row[0]] = float(row[1])
            except (IOError, IndexError, ValueError) as e:
                messagebox.showerror("CSV Error", f"Could not read {self.csv_path}.\nError: {e}")
                self.root.quit()
                return

        # Determine the starting point: the first GIF without a label.
        start_index = 0
        for i, filename in enumerate(self.all_gifs):
            if filename not in self.labels:
                start_index = i
                break
        else:
            # If all GIFs are labeled, start at the beginning for review.
            start_index = 0

        self.load_gif_at_index(start_index)

    def go_to_next_gif(self, event=None):
        """Navigates to the next GIF in the sequence for review."""
        if self.current_gif_index < len(self.all_gifs) - 1:
            self.load_gif_at_index(self.current_gif_index + 1)
        else:
            messagebox.showinfo("End of List", "You have reached the last GIF.")

    def go_to_previous_gif(self, event=None):
        """Navigates to the previous GIF in the sequence for review."""
        if self.current_gif_index > 0:
            self.load_gif_at_index(self.current_gif_index - 1)
        else:
            messagebox.showinfo("Start of List", "You are at the first GIF.")

    def find_and_go_to_next_unlabeled(self):
        """
        Performs a circular search starting from the current position to find
        the next GIF that has no label.
        """
        start_search_index = self.current_gif_index
        num_gifs = len(self.all_gifs)

        # Iterate through the list, wrapping around if we reach the end.
        for i in range(1, num_gifs):
            check_index = (start_search_index + i) % num_gifs
            filename = self.all_gifs[check_index]
            if filename not in self.labels:
                self.load_gif_at_index(check_index)
                return  # Found one, so we are done.

        # If the loop completes, all GIFs have been labeled.
        messagebox.showinfo("Complete!", "All GIFs are now labeled. You can continue to review them with the arrow keys.")
        self.go_to_next_gif() # Fallback to sequential navigation.

    def load_gif_at_index(self, index):
        """
        The core function for loading and displaying a GIF at a given index.
        This handles loading frames, resetting state, and showing saved labels.
        """
        if not (0 <= index < len(self.all_gifs)):
            return

        self.current_gif_index = index
        filename = self.all_gifs[self.current_gif_index]
        
        # Reset the state for the new GIF.
        if self.animation_job: self.root.after_cancel(self.animation_job)
        self.selected_angle = None
        
        # Load GIF frames using Pillow and resize each one to fit the canvas.
        filepath = os.path.join(self.gif_folder, filename)
        self.gif_frames = []
        try:
            with Image.open(filepath) as img:
                for frame in ImageSequence.Iterator(img):
                    resized_frame = frame.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(resized_frame.convert("RGBA")))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load {filename}.\nError: {e}")
            self.go_to_next_gif() # Automatically skip corrupted files.
            return

        self.current_frame_index = 0
        self.animate_gif()
        self.update_progress()
        self.filename_label.config(text=f"Filename: {filename}")

        # If a label already exists for this GIF, display it.
        if filename in self.labels:
            self.selected_angle = self.labels[filename]
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)
            self.angle_value_label.config(text=f"Saved: {self.selected_angle:.1f}° (Click to change)")
        else:
            # Otherwise, prepare for a new label.
            self.canvas.itemconfig(self.selected_line, state=tk.HIDDEN)
            self.angle_value_label.config(text="Move mouse to select angle")
    
    def save_and_next(self):
        """
        Saves the current selected angle and navigates to the next unlabeled GIF.
        """
        if self.selected_angle is None:
            messagebox.showwarning("No Angle Selected", "Please click on the image to select an angle before saving.")
            return

        # Update the in-memory dictionary.
        filename = self.all_gifs[self.current_gif_index]
        self.labels[filename] = self.selected_angle

        # Rewrite the entire CSV file to ensure data integrity and handle overwrites.
        try:
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'angle'])
                # Write rows in their original sorted order for consistency.
                for fname in self.all_gifs:
                    if fname in self.labels:
                        writer.writerow([fname, f"{self.labels[fname]:.2f}"])
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not write to {self.csv_path}.\nError: {e}")
            return
        
        # Intelligently find the next piece of work.
        self.find_and_go_to_next_unlabeled()
    
    def update_progress(self):
        """Updates the progress label (e.g., "Progress: 5/1000")."""
        total = len(self.all_gifs)
        current_num = self.current_gif_index + 1
        self.progress_label.config(text=f"Progress: {current_num}/{total}")

    def animate_gif(self):
        """Cycles through the loaded GIF frames to create animation."""
        if not self.gif_frames: return
        frame = self.gif_frames[self.current_frame_index]
        self.canvas.itemconfig(self.image_on_canvas, image=frame)
        self.current_frame_index = (self.current_frame_index + 1) % len(self.gif_frames)
        # Schedule the next frame update (100ms delay).
        self.animation_job = self.root.after(100, self.animate_gif)

    def _get_canvas_coords(self, event):
        """Translates absolute screen coordinates into coordinates relative to the canvas."""
        canvas_x = event.x_root - self.canvas.winfo_rootx()
        canvas_y = event.y_root - self.canvas.winfo_rooty()
        return canvas_x, canvas_y

    def calculate_angle_from_coords(self, x, y):
        """Calculates a 0-180 degree angle based on mouse coordinates."""
        origin_x = CANVAS_WIDTH / 2
        origin_y = 0  # The line is anchored at the top-center.
        
        # Use atan2 to get the angle in radians from the origin.
        rads = math.atan2(y - origin_y, x - origin_x)
        degs = math.degrees(rads)

        # Convert the mathematical angle to our desired 0-180 range.
        angle = 180 - degs
        return max(0, min(180, angle)) # Clamp the value between 0 and 180.

    def on_mouse_move(self, event):
        """Event handler for mouse movement. Updates the hover line and label text."""
        x, y = self._get_canvas_coords(event)
        hover_angle = self.calculate_angle_from_coords(x, y)
        
        # Provide rich feedback on the label, showing both hover and selected angles.
        if self.selected_angle is not None:
            self.angle_value_label.config(text=f"Hover: {hover_angle:.1f}° | Selected: {self.selected_angle:.1f}°")
        else:
            self.angle_value_label.config(text=f"Angle: {hover_angle:.1f}°")
            
        self.draw_angle_line(hover_angle, self.hover_line)
    
    def on_mouse_click(self, event):
        """Event handler for mouse clicks. Selects the angle."""
        x, y = self._get_canvas_coords(event)
        # Only register clicks that happen inside the canvas area.
        if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
            angle = self.calculate_angle_from_coords(x, y)
            self.selected_angle = angle
            self.angle_value_label.config(text=f"Hover: {angle:.1f}° | Selected: {self.selected_angle:.1f}°")
            
            # Draw the solid line to confirm selection.
            self.draw_angle_line(self.selected_angle, self.selected_line)
            self.canvas.itemconfig(self.selected_line, state=tk.NORMAL)

    def draw_angle_line(self, angle, line_widget):
        """Helper function to draw an angle line on the canvas."""
        origin_x = CANVAS_WIDTH / 2
        origin_y = 0
        line_length = CANVAS_HEIGHT * 0.95
        
        # Convert our display angle back to radians for trigonometric functions.
        angle_rad = math.radians(180 - angle)
        
        end_x = origin_x + line_length * math.cos(angle_rad)
        end_y = origin_y + line_length * math.sin(angle_rad)
        
        self.canvas.coords(line_widget, origin_x, origin_y, end_x, end_y)

if __name__ == "__main__":
    # Entry point of the application.
    root = tk.Tk()
    app = AngleLabeler(root, GIF_DIRECTORY, CSV_FILE)
    root.mainloop()