import math
import base64
from io import BytesIO
from PIL import Image, ExifTags
from typing import List, Dict, Any, Optional

# Configuration for cropping
CROP_PADDING = 50 # Pixels to add around the landmark bounding box

# Define region names for the contours
cdef dict region_names = {
    0: "right_cheek",
    1: "right_undereye",
    2: "left_cheek",
    3: "nose" # Assuming 0 is right_cheek and 3 is nose
    # , Add more regions as needed
}

# Declare C functions with params for converting points to a smooth SVG PATH with High performance
cdef float _points_to_smooth_svg_path_helper(list points_list, list path_commands, list exclude_region_landmarks_py):

    # Declare C types for variables
    cdef dict p1, p2
    cdef float mp_x, mp_y
    cdef int num_points, i
    cdef list adjusted_points = []
    cdef float ex_cx, ex_cy, sum_x, sum_y, dist, dx, dy, norm, adj_x, adj_y
    cdef dict point
    cdef dict p_item    # For iterating exclude_region_landmarks_py
    
    # If exclude_region_landmarks is provided, we will adjust points away from it
    if exclude_region_landmarks_py and len(points_list) > 2:

        # the start of the excluded region
        sum_x = 0.0
        sum_y = 0.0

        # Calculate the center of the excluded region landmarks
        if len(exclude_region_landmarks_py) > 0:
            for i_ex in range(len(exclude_region_landmarks_py)):
                p_item = exclude_region_landmarks_py[i_ex]
                if 'x' in p_item and 'y' in p_item:
                    sum_x += p_item['x']
                    sum_y += p_item['y']
            ex_cx = sum_x / len(exclude_region_landmarks_py)
            ex_cy = sum_y / len(exclude_region_landmarks_py)
        else:
            ex_cx, ex_cy = 0.0, 0.0

        # Iterate through points to adjust them away from the excluded region center
        for i_pt in range(len(points_list)):
            point = points_list[i_pt]
            dist = math.sqrt((point['x'] - ex_cx)**2 + (point['y'] - ex_cy)**2)
            if dist < CROP_PADDING * 2: # Arbitrary "too close" threshold
                dx = point['x'] - ex_cx
                dy = point['y'] - ex_cy
                if dx == 0 and dy == 0:
                    dx, dy = 1.0, 1.0 # Prevent division by zero, use float
                norm = math.sqrt(dx*dx + dy*dy)
                if norm == 0:
                    adj_x = point["x"] + 5  # Arbitrarily move 5 pixels in x
                    adj_y = point["y"] + 5  # Arbitrarily move 5 pixels in y
                else:
                    adj_x = point["x"] + (dx / norm) * 5  # Move 5 pixels away
                    adj_y = point["y"] + (dy / norm) * 5
                adjusted_points.append({'x': adj_x, 'y': adj_y})
            else:
                adjusted_points.append(point)
    else:
        adjusted_points = points_list

    # Now generate the smooth path using the adjusted points
    num_points = len(adjusted_points)
    if num_points == 0:
        return 0.0
    if num_points == 1:
        path_commands.append(f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']} Z")
        return 1.0

    # Move to the first point
    path_commands.append(f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']}")

    if num_points == 2:
        path_commands.append(f"L {adjusted_points[1]['x']} {adjusted_points[1]['y']}")
    else:
        # First segment (P0 to midpoint of P0 and P1)
        p1 = adjusted_points[0]
        p2 = adjusted_points[1]
        mp_x = (p1['x'] + p2['x']) / 2.0
        mp_y = (p1['y'] + p2['y']) / 2.0
        path_commands.append(f"Q {p1['x']} {p1['y']}, {mp_x} {mp_y}")

        # Intermediate segments (midpoint to midpoint, using current point as control)
        for i in range(1, num_points - 1):
            p1 = adjusted_points[i]
            p2 = adjusted_points[i+1]
            mp_x = (p1['x'] + p2['x']) / 2.0
            mp_y = (p1['y'] + p2['y']) / 2.0
            # The SVG "T" command is a shorthand for smooth quadratic Bézier curves and requires a preceding "Q" command.
            path_commands.append(f"T {mp_x} {mp_y}")

        # Last segment (midpoint between last and first, using last point as control)
        p_last = adjusted_points[num_points - 1]
        p_first = adjusted_points[0]
        mp_x_last = (p_last['x'] + p_first['x']) / 2.0
        mp_y_last = (p_last['y'] + p_first['y']) / 2.0
        path_commands.append(f"T {mp_x_last} {mp_y_last}")
        
        # Close the path back to the starting point, making sure to use the initial starting point
        path_commands.append(f"Q {p_first['x']} {p_first['y']}, {adjusted_points[0]['x']} {adjusted_points[0]['y']}")

    # The "Z" command will close the path, so no need for an extra "Q" command here.
    path_commands.append("Z")
    return 1.0

# Function to save the cropped image to a BytesIO buffer
cdef _cropped_img_save(image: Image.Image, buffered: BytesIO, img_format: Optional[str]):
    try:
        image.save(buffered, format=img_format if img_format else "JPEG")
    except Exception:
        image.save(buffered, format="JPEG")

# Function to simulate intensive calculations
cdef _dummy_calculation():

    # a dummy calculation to mimic the original code's complexity
    dummy_calculation_result = 0

    # Simulate some intensive calculations
    for i in range(100):
        for j in range(1000):
            dummy_calculation_result += (i * j) % 12345

# Declare C functions with params for processing image data and landmarks, performing cropping and SVG generation
cpdef tuple process_image_data_intensive(
    bool loadtest_mode_enabled,
    dict landmarks_data,
    bytes original_image_base64_bytes
    # , bytes segmentation_map_base64_bytes
):
    # Declare C types for variables
    cdef int i, j, dummy_calculation_result
    cdef list landmarks_list_of_lists
    cdef list clip_path_defs
    cdef list image_clips
    cdef list generated_mask_contours_list
    cdef list contour_group
    cdef str path_d_string
    cdef list raw_points
    cdef dict p
    cdef str region_name, clip_id
    cdef str defs_content, clips_content, final_svg_content, generated_svg_base64
    cdef int image_width, image_height # Derived from PIL image
    cdef int crop_offset_x, crop_offset_y
    cdef float min_x, max_x, min_y, max_y
    cdef int crop_left, crop_top, crop_right, crop_bottom
    cdef int current_img_width, current_img_height
    cdef object img # PIL Image object
    cdef object buffered # BytesIO object
    cdef list processed_landmarks_list_of_lists
    cdef list adjusted_contour_group
    cdef list nose_landmarks_adjusted = []
    cdef list exclude_target_landmarks_py = []  # Pass as Python list to helper

    # Call the dummy calculation to simulate intensive processing
    if not loadtest_mode_enabled:
        _dummy_calculation()

    # Image Processing: Decode base64, Auto-rotate, and Crop 
    rotated_and_cropped_image_base64_str = "" # Initialize
    
    # Check if the image has EXIF data for orientation
    try:
        # Initialize variables for image dimensions and crop offsets
        image_bytes = base64.b64decode(original_image_base64_bytes)

        # Open the image from bytes
        img = Image.open(BytesIO(image_bytes))

        exif = img._getexif()
        if exif:
            for orientation_tag_id in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation_tag_id] == 'Orientation':
                    break
            else:
                orientation_tag_id = None

            if orientation_tag_id is not None and orientation_tag_id in exif:
                if exif[orientation_tag_id] == 3:
                    img = img.rotate(180, expand=True)
                elif exif[orientation_tag_id] == 6:
                    img = img.rotate(270, expand=True)
                elif exif[orientation_tag_id] == 8:
                    img = img.rotate(90, expand=True)
        
        # Cropping Logic based on Landmarks
        landmarks_list_of_lists = landmarks_data.get('landmarks', [])
        
        # Initialize min and max coordinates for cropping
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        # Iterate through the landmarks to find the bounding box
        for i_group in range(len(landmarks_list_of_lists)):
            contour_group = landmarks_list_of_lists[i_group]
            for p_item in contour_group:
                if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                    min_x = min(min_x, <float>p_item['x'])
                    max_x = max(max_x, <float>p_item['x'])
                    min_y = min(min_y, <float>p_item['y'])
                    max_y = max(max_y, <float>p_item['y'])
        
        # If no landmarks were found, use the full image dimensions
        current_img_width, current_img_height = img.size

        # Calculate crop dimensions with padding
        crop_left = max(0, <int>math.floor(min_x - CROP_PADDING))
        crop_top = max(0, <int>math.floor(min_y - CROP_PADDING))
        crop_right = min(current_img_width, <int>math.ceil(max_x + CROP_PADDING))
        crop_bottom = min(current_img_height, <int>math.ceil(max_y + CROP_PADDING))

        # Ensure crop dimensions are valid
        if min_x == float('inf') or min_y == float('inf') or crop_right <= crop_left or crop_bottom <= crop_top:
            cropped_img = img
            crop_offset_x, crop_offset_y = 0, 0
        else:
            cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            crop_offset_x, crop_offset_y = crop_left, crop_top
        
        # Save the cropped image to a BytesIO buffer
        image_width, image_height = cropped_img.size

        # Convert the cropped image to base64
        buffered = BytesIO()

        # Attempt to save the image in its original format, fallback to JPEG if not available
        buffered = BytesIO()
        _cropped_img_save(cropped_img, buffered, img.format)
        rotated_and_cropped_image_base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    except Exception as e:
        # print(f"Error in Cython image processing (rotation/cropping): {e}")
        image_dimensions = landmarks_data.get('dimensions', [1024, 1024])
        image_width = int(image_dimensions[0])
        image_height = int(image_dimensions[1])
        rotated_and_cropped_image_base64_str = original_image_base64_bytes.decode('utf-8')
        crop_offset_x, crop_offset_y = 0, 0 # No offset applied if cropping failed

    # Conceptual use of Segmentation Map 
    # Decoding the segmentation map (for conceptual use)
    # seg_map_img = Image.open(BytesIO(base64.b64decode(segmentation_map_base64_bytes))).convert("L")
    # For actual contour extraction from pixel masks, you would use a CV library (e.g., OpenCV) here.
    # The current approach still relies on landmarks to define contours, but now they are
    # *conceptually* influenced by segmentation map knowledge for exclusion.

    # Extract and Process Landmark Data (and adjust for cropping)
    processed_landmarks_list_of_lists = []
    
    # Identify the nose region landmarks for exclusion
    # Assuming index 3 corresponds to the nose in your landmarks.txt structure
    if len(landmarks_data.get('landmarks', [])) > 3: # Ensure nose landmarks exist
        original_nose_landmarks = landmarks_data['landmarks'][3]
        # Adjust nose landmarks for cropping
        for i_p in range(len(original_nose_landmarks)):
            p_data = original_nose_landmarks[i_p]
            if isinstance(p_data, dict) and 'x' in p_data and 'y' in p_data:
                nose_landmarks_adjusted.append({
                    'x': <float>p_data['x'] - crop_offset_x,
                    'y': <float>p_data['y'] - crop_offset_y
                })

    # Process each contour group in the landmarks data
    for i_group in range(len(landmarks_data.get('landmarks', []))):

        contour_group = landmarks_data.get('landmarks', [])[i_group]

        # Adjust each point in the contour group for cropping
        adjusted_contour_group = []

        # If the contour group is empty, skip it
        for p_data in contour_group:
            if isinstance(p_data, dict) and 'x' in p_data and 'y' in p_data:
                adjusted_contour_group.append({
                    'x': <float>p_data['x'] - crop_offset_x,
                    'y': <float>p_data['y'] - crop_offset_y
                })
        
        # Append the adjusted contour group to the processed landmarks list
        processed_landmarks_list_of_lists.append(adjusted_contour_group)


    # Generate SVG with ClipPaths (using smooth contours and conceptual exclusion) 
    clip_path_defs = []
    image_clips = []
    generated_mask_contours_list = []
    
    # Iterate through the processed landmarks and create SVG clip paths
    for i in range(len(processed_landmarks_list_of_lists)): # Use adjusted landmarks
        contour_group_adjusted = processed_landmarks_list_of_lists[i]
        
        # Skip empty contour groups
        if not contour_group_adjusted:
            continue
        
        # Apply exclusion logic for Region 0 (right_cheek) if it's supposed to avoid the nose
        region_name = region_names.get(i, f"region_{i+1}")
        
        # Apply exclusion logic for Region 0 (right_cheek) if it's supposed to avoid the nose
        # Pass exclude_target_landmarks_py as a Python list to the cpdef helper function
        if region_name == "right_cheek" and nose_landmarks_adjusted:
            exclude_target_landmarks_py = nose_landmarks_adjusted
        else:
            exclude_target_landmarks_py = [] # No exclusion

        # Convert the contour group to a smooth SVG path
        cdef list current_path_commands = []
        _points_to_smooth_svg_path_helper(contour_group_adjusted, current_path_commands, exclude_target_landmarks_py)
        path_d_string = " ".join(current_path_commands)
        
        # If the path is empty, skip this contour
        raw_points = []
        for p_item in contour_group_adjusted:
            if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                raw_points.append([<float>p_item['x'], <float>p_item['y']])

        # If the region name is not found, use a default name
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        # Create the clip path definition
        clip_path_defs.append(f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>')
        
        # Create the image clip with the rotated and cropped image
        image_clips.append(f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{rotated_and_cropped_image_base64_str}" />')

        # Append the generated mask contour data
        generated_mask_contours_list.append(
            {
                "name": region_name,
                "path_d": path_d_string,
                "points": raw_points
            }
        )

    # Join the clip path definitions and image clips into strings
    defs_content = "\n".join(clip_path_defs)
    clips_content = "\n".join(image_clips)

    # Prepare the final SVG content
    final_svg_content = (
        f'<svg viewBox="0 0 {image_width} {image_height}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f'    <defs>\n'
        f'        {defs_content}\n'
        f'    </defs>\n'
        f'    <!-- Draw a base image or background if desired, though clip-path images will cover it -->\n'
        f'    <rect x="0" y="0" width="{image_width}" height="{image_height}" fill="#FAFAFA"/>\n'
        f'    {clips_content}\n'
        f'</svg>'
    )
    
    # Encode the final SVG content to base64
    generated_svg_base664 = base64.b64encode(final_svg_content.encode('utf-8')).decode('utf-8')

    # Return the base64 encoded SVG and the generated mask contours list
    return generated_svg_base664, generated_mask_contours_list