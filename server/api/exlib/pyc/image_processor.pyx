import math
import base64
from io import BytesIO
from PIL import Image, ExifTags
from typing import List, Optional, Tuple

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

# Function to save the cropped image to a BytesIO buffer
cdef void _cropped_img_save(
    image: Image.Image, 
    buffered: BytesIO, 
    img_format: Optional[str]
):
    # Declare C types for variables
    cdef str format_to_use

    # Determine the format to use for saving the image
    if format_str_or_none is None:
        format_to_use = "JPEG"
    else:
        format_to_use = format_str_or_none

    try:
        image.save(buffered, format=format_to_use)
    except Exception:
        # Fallback to JPEG if the preferred format fails
        image.save(buffered, format="JPEG")

# Function to simulate intensive calculations
cdef void _dummy_calculation():

    # a dummy calculation to mimic the original code's complexity
    dummy_calculation_result = 0
    # Declare C types for variables
    cdef int i, j

    # Simulate some intensive calculations
    for i in range(100):
        for j in range(1000):
            dummy_calculation_result += (i * j) % 12345

# Declare C functions with params for converting points to a smooth SVG PATH with High performance
cdef str _points_to_smooth_svg_path(
    list points_list, 
    list exclude_region_landmarks_py
):
    # Declare C types for variables
    cdef dict p1, p2
    cdef float mp_x, mp_y
    cdef int num_points, i_loop
    cdef list adjusted_points = [] # Python list
    cdef float ex_cx, ex_cy, sum_x, sum_y, dist, dx, dy, norm, adj_x, adj_y
    cdef dict point_item, p_ex_item # Python dicts
    cdef list internal_path_commands = [] # Python list of strings
    cdef dict point_item, p_ex_item # Python dicts
    cdef list internal_path_commands = [] # Python list of strings

    # If exclude_region_landmarks is provided, we will adjust points away from it
    if exclude_region_landmarks_py and len(points_list) > 2:
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
                    dx, dy = 1.0, 1.0 # Prevent division by zero if point is exactly at centroid
                norm = math.sqrt(dx*dx + dy*dy)
                # The 'if norm == 0' block is now unreachable because dx, dy are set to 1.0, 1.0 if they were 0,0.
                # So norm will always be sqrt(1.0*1.0 + 1.0*1.0) = sqrt(2.0) != 0 in that specific case.
                adj_x = point["x"] + (dx / norm) * 5  # Move 5 pixels away
                adj_y = point["y"] + (dy / norm) * 5
                # Append the adjusted point
                adjusted_points.append({'x': adj_x, 'y': adj_y})
            else:
                adjusted_points.append(point)
    else:
        adjusted_points = points_list

    # Now generate the smooth path using the adjusted points
    num_points = len(adjusted_points)
    if num_points == 0:
        return ""
    if num_points == 1:
        return f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']} Z"

    # Start the path with the first point
    internal_path_commands.append(f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']}")
    
    # If there are only two points, we can just draw a line to the second point
    if num_points == 2:
        internal_path_commands.append(f"L {adjusted_points[1]['x']} {adjusted_points[1]['y']}")
    else:
        # First segment (P0 to midpoint of P0 and P1)
        p1 = adjusted_points[0]
        p2 = adjusted_points[1]
        mp_x = (p1['x'] + p2['x']) / 2.0
        mp_y = (p1['y'] + p2['y']) / 2.0
        # Use the first point as control for the first segment
        internal_path_commands.append(f"Q {p1['x']} {p1['y']}, {mp_x} {mp_y}")

        # Intermediate segments (midpoint to midpoint, using current point as control)
        for i in range(1, num_points - 1):
            p1 = adjusted_points[i]
            p2 = adjusted_points[i+1]
            mp_x = (<float>p1['x'] + <float>p2['x']) / 2.0
            mp_y = (<float>p1['y'] + <float>p2['y']) / 2.0
            internal_path_commands.append(f"T {mp_x} {mp_y}")

        # Last segment (midpoint between last and first, using last point as control)
        p_last = adjusted_points[num_points - 1]
        p_first = adjusted_points[0] # Use the original first adjusted point for closure
        mp_x_last = (p_last['x'] + p_first['x']) / 2.0
        mp_x_last = (p_last['y'] + p_first['y']) / 2.0
        # Use the last point as control for the final segment
        internal_path_commands.append(f"T {mp_x_last} {mp_y_last}")
        # Close the path back to the starting point.
        internal_path_commands.append(f"Q {p_first['x']} {p_first['y']}, {adjusted_points[0]['x']} {adjusted_points[0]['y']}")

    # The "Z" command will close the path.
    internal_path_commands.append("Z")

    return " ".join(internal_path_commands)

cpdef tuple _process_image_decoding_and_cropping(
    bytes original_image_base64_bytes, 
    dict landmarks_data
):
    # Declare C types for variables
    cdef int image_width, image_height
    cdef int crop_offset_x, crop_offset_y
    cdef str rotated_and_cropped_image_base64_str = ""
    cdef bytes image_bytes
    cdef object img # PIL Image object
    cdef object exif_data # Dictionary from img._getexif()
    cdef object orientation_tag_id_obj # Can be int or None
    cdef int orientation_tag_id_val # For casting orientation_tag_id_obj
    cdef list landmarks_list_of_lists # Python list
    cdef float min_x, max_x, min_y, max_y
    cdef int current_img_width, current_img_height
    cdef int crop_left, crop_top, crop_right, crop_bottom
    cdef object cropped_img # PIL Image object
    cdef object buffered # BytesIO object
    cdef dict point_data_item # For iterating through landmarks

    image_width, image_height = 0, 0
    crop_offset_x, crop_offset_y = 0, 0
    rotated_and_cropped_image_base64_str = ""

    try:
        # Decode the base64 image bytes
        image_bytes = base64.b64decode(original_image_base64_bytes)
        img = Image.open(BytesIO(image_bytes))

        exif_data = img._getexif()
        if exif_data:
            # Need to iterate Python dict in Cython
            for orientation_tag_id_obj in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation_tag_id_obj] == "Orientation":
                    break
            else: # Executed if loop completes without break
                orientation_tag_id_obj = None

            if orientation_tag_id_obj is not None and orientation_tag_id_obj in exif_data:
                orientation_tag_id_val = <int>orientation_tag_id_obj # Cast to int
                if exif_data[orientation_tag_id_val] == 3:
                    img = img.rotate(180, expand=True)
                elif exif_data[orientation_tag_id_val] == 6:
                    img = img.rotate(270, expand=True)
                elif exif_data[orientation_tag_id_val] == 8:
                    img = img.rotate(90, expand=True)

        landmarks_list_of_lists = landmarks_data.get("landmarks", [])

        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')

        # Iterate through the landmarks to find the bounding box
        for i_group in range(len(landmarks_list_of_lists)):
            for point_data_item in landmarks_list_of_lists[i_group]: # Nested iteration
                if isinstance(point_data_item, dict) and 'x' in point_data_item and 'y' in point_data_item:
                    min_x = min(min_x, <float>point_data_item['x'])
                    max_x = max(max_x, <float>point_data_item['x'])
                    min_y = min(min_y, <float>point_data_item['y'])
                    max_y = max(max_y, <float>point_data_item['y'])

        current_img_width, current_img_height = img.size

        crop_left = max(0, <int>math.floor(min_x - CROP_PADDING))
        crop_top = max(0, <int>math.floor(min_y - CROP_PADDING))
        crop_right = min(current_img_width, <int>math.ceil(max_x + CROP_PADDING))
        crop_bottom = min(current_img_height, <int>math.ceil(max_y + CROP_PADDING))

        if (min_x == float('inf') or min_y == float('inf') or crop_right <= crop_left or crop_bottom <= crop_top):
            cropped_img = img
            crop_offset_x, crop_offset_y = 0, 0
        else:
            cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            crop_offset_x, crop_offset_y = crop_left, crop_top

        image_width, image_height = cropped_img.size
        buffered = BytesIO()
        _cropped_img_save(cropped_img, buffered, img.format) # Call existing helper
        rotated_and_cropped_image_base64_str = base64.b64encode(
            buffered.getvalue()
        ).decode('utf-8')

    except Exception as e:
        # Fallback in case of error
        image_dimensions_from_landmarks = landmarks_data.get("dimensions", [1024, 1024])
        image_width = int(image_dimensions_from_landmarks[0])
        image_height = int(image_dimensions_from_landmarks[1])
        rotated_and_cropped_image_base64_str = original_image_base64_bytes.decode('utf-8')
        crop_offset_x, crop_offset_y = 0, 0
        # print(f"Error during image processing (rotation or cropping): {e}")

    return (
        rotated_and_cropped_image_base64_str,
        image_width,
        image_height,
        crop_offset_x,
        crop_offset_y,
    )

cpdef str _generate_final_svg_content(
    int image_width,
    int image_height,
    str rotated_and_cropped_image_base64_str,
    list clip_path_defs, # List of Python strings
    list image_clips # List of Python strings
):
    # Declare C types for local variables
    cdef str defs_content, clips_content, final_svg_content

    defs_content = "\n".join(clip_path_defs)
    clips_content = "\n".join(image_clips)

    final_svg_content_py = (
        f'<svg viewBox="0 0 {image_width} {image_height}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f'    <defs>\n'
        f'        {defs_content_py}\n'
        f'    </defs>\n'
        f'    <rect x="0" y="0" width="{image_width}" height="{image_height}" fill="#FAFAFA"/>\n'
        f'    {clips_content_py}\n'
        f'</svg>'
    )

    return c_final_svg_content

cpdef list _extract_raw_points(
    list contour_group
):
    # Declare C types for local variables
    cdef list raw_points = []
    cdef dict p_item

    for p_item in contour_group:
        if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
            raw_points.append([<float>p_item['x'], <float>p_item['y']])
    return raw_points

cpdef tuple process_image_data_intensive(
    bool loadtest_mode_enabled,
    dict landmarks_data,
    bytes original_image_base64_bytes
):
    # Declare C types for variables
    cdef int i, i_group
    cdef list clip_path_defs = []
    cdef list image_clips = []
    cdef list generated_mask_contours_list = []
    cdef list contour_group_py
    cdef str path_d_string # Python string for path
    cdef list raw_points
    cdef str region_name, clip_id
    cdef list processed_landmarks_list_of_lists = []
    cdef list adjusted_contour_group
    cdef list nose_landmarks_adjusted = []
    cdef list exclude_target_landmarks
    cdef str final_svg_content # Python string for final SVG
    cdef str generated_svg_base64 # Final base64 encoded SVG

    # Call the dummy calculation to simulate intensive processing
    if not loadtest_mode_enabled:
        _dummy_calculation()

    # Image Processing: Decode base64, Auto-rotate, and Crop
    (
        rotated_and_cropped_image_base64_str,
        image_width,
        image_height,
        crop_offset_x,
        crop_offset_y,
    ) = _process_image_decoding_and_cropping(
        original_image_base64_bytes, landmarks_data
    )

    # Extract and Process Landmark Data (and adjust for cropping)
    if len(landmarks_data.get('landmarks', [])) > 3:
        original_nose_landmarks = landmarks_data['landmarks'][3]
        for i in range(len(original_nose_landmarks)):
            p_data = original_nose_landmarks[i]
            if isinstance(p_data, dict) and 'x' in p_data and 'y' in p_data:
                nose_landmarks_adjusted.append({
                    'x': <float>p_data['x'] - crop_offset_x,
                    'y': <float>p_data['y'] - crop_offset_y
                })

    # Process each group of landmarks
    landmarks_list_of_lists = landmarks_data.get('landmarks', [])

    # Adjust each contour group based on the crop offsets
    for i_group in range(len(landmarks_list_of_lists)):
        
        contour_group_py = landmarks_list_of_lists[i_group]
        adjusted_contour_group = []

        # check isinstance of contour_group_py
        for p_data in contour_group_py:
            if isinstance(p_data, dict) and 'x' in p_data and 'y' in p_data:
                adjusted_contour_group.append({
                    'x': <float>p_data['x'] - crop_offset_x,
                    'y': <float>p_data['y'] - crop_offset_y
                })
        # append the adjusted contour group to the processed list
        processed_landmarks_list_of_lists.append(adjusted_contour_group)

    # Generate SVG with ClipPaths
    for i in range(len(processed_landmarks_list_of_lists)):
        contour_group_adjusted = processed_landmarks_list_of_lists[i]
        
        if not contour_group_adjusted:
            continue
        
        region_name = region_names.get(i, f"region_{i+1}")
        
        if region_name == "right_cheek" and nose_landmarks_adjusted:
            exclude_target_landmarks = nose_landmarks_adjusted
        else:
            exclude_target_landmarks = []

        # Call _points_to_smooth_svg_path, which now returns Python str
        path_d_string = _points_to_smooth_svg_path(
            contour_group_adjusted, exclude_target_landmarks
        )
        
        # Extract raw points for the contour group
        raw_points = _extract_raw_points(contour_group_adjusted)
        
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        clip_path_defs.append(f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>')
        
        image_clips.append(f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{rotated_and_cropped_image_base64_str}" />')

        generated_mask_contours_list.append(
            {
                "name": region_name,
                "path_d": path_d_string,
                "points": raw_points
            }
        )

    # Prepare the final SVG content
    final_svg_content = _generate_final_svg_content(
        image_width,
        image_height,
        rotated_and_cropped_image_base64_str,
        clip_path_defs,
        image_clips
    )
    
    # Encode the final SVG content to base64
    generated_svg_base64 = base64.b64encode(final_svg_content.encode('utf-8')).decode('utf-8')

    # Return the base64 encoded SVG and the generated mask contours list
    return generated_svg_base64, generated_mask_contours_list