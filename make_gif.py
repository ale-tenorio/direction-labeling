from PIL import Image, ImageDraw
import os
import glob
import math
from tqdm import tqdm
import json
from multiprocessing import Pool
import multiprocessing

def crop_to_half_circle(image, center, radius, direction=270):
    """
    Crop the image into a half-circle shape pointing in a specified direction.
    :param image: PIL Image object
    :param center: Tuple (x, y) for the center of the half-circle
    :param radius: Radius of the half-circle
    :param direction: Direction in degrees where the half-circle points (default is 270)
    :return: Cropped PIL Image object
    """
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    x, y = center

    # Calculate start and end angles based on the direction
    start_angle = direction - 90
    end_angle = direction + 90

    # Draw a half-circle mask
    draw.pieslice([x - radius, y - radius, x + radius, y + radius], start=start_angle, end=end_angle, fill=255)

    # Apply the mask to the image
    cropped_image = Image.new("RGBA", image.size)
    cropped_image.paste(image, mask=mask)
    # Crop the image using the mask

    return cropped_image, mask

def create_gif_semicircle(image_paths, center, radius, direction, output_path, fps=60):
    """
    Create a GIF from a list of images cropped to a half-circle, with lines every 30 degrees.
    :param image_paths: List of image file paths
    :param center: Tuple (x, y) for the center of the half-circle
    :param radius: Radius of the half-circle
    :param output_path: Path to save the output GIF
    :param fps: frames per second
    """
    frames = []
    for img_path in tqdm(image_paths, desc="Processing images"):
        image = Image.open(img_path).convert("RGBA")
        cropped_image, mask = crop_to_half_circle(image, center, radius, direction)

        start = direction - 90
        end = direction + 90
        draw = ImageDraw.Draw(cropped_image)

        for angle in range(start, end + 1, 10):  # 0 to 180 degrees, inclusive
            x_start = center[0] + 0.9 * radius * math.cos(math.radians(angle))
            y_start = center[1] + 0.9 * radius * math.sin(math.radians(angle))
            x_end = center[0] + radius * math.cos(math.radians(angle))
            y_end = center[1] + radius * math.sin(math.radians(angle))
            draw.line([(x_start, y_start), (x_end, y_end)], fill="white", width=1, joint="curve")
        #draw.line([center, (center[0], center[1] + radius)], fill="red", width=1, joint="curve")
        #draw.ellipse([center[0] - 3, center[1] - 3, center[0] + 3, center[1] + 3], fill="red", outline="red")

        cropped_image = cropped_image.crop(mask.getbbox())
        frames.append(cropped_image)

    # Save frames as a GIF
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=1000 // fps, loop=0)

def process_gif(args):
    """
    Process a single GIF creation task for multiprocessing.
    :param args: Tuple containing (i, data_list, image_paths_list, file_name)
    """
    idx, data_list, image_paths_list, file_name = args
    radius = 128
    direction = data_list[idx]['direction'] - 180
    center = data_list[idx]['point1']
    init_frame = data_list[idx]['batch_start_index']
    end_frame = data_list[idx]['batch_end_index']
    selected_image_paths = image_paths_list[init_frame:end_frame]
    output_path = f"gifs/{file_name}_output_{idx + 1}.gif"
    create_gif_semicircle(selected_image_paths, center, radius, direction, output_path, fps=24)

if __name__ == "__main__":
    parent_dir = r"C:\Users\axt5780\OneDrive - The Pennsylvania State University\Documents\USGS\Datasets\UAS Colorado 2023"
    specific_file = 'CRG'

    json_path = os.path.join(parent_dir, specific_file, 'stacked_STIs', 'merged_points.json')
    with open(json_path, 'r') as f:
        data_list = json.load(f)

    frames_dir = os.path.join(parent_dir, specific_file, 'frames')
    image_paths_list = glob.glob(os.path.join(frames_dir, "*.jpg"))

    args_list = [(i, data_list, image_paths_list, specific_file) for i in range(len(data_list))]
    print(f"Available CPU cores: {multiprocessing.cpu_count()}")
    with Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(process_gif, args_list)