import math
import base64
from io import BytesIO
from PIL import Image, ExifTags
from typing import List, Dict, Any

CROP_PADDING = 50

cdef float _points_to_smooth_svg_path_helper(list points_list, list path_commands):
    cdef dict p1, p2
    cdef float mp_x, mp_y
    cdef int num_points, i

    if not points_list:
        return 0.0

    num_points = len(points_list)
    if num_points == 0:
        return 0.0
    if num_points == 1:
        return 0.0

    path_commands.append(f"M {points_list[0]['x']} {points_list[0]['y']}")

    if num_points == 2:
        path_commands.append(f"L {points_list[1]['x']} {points_list[1]['y']}")
    else:
        p1 = points_list[0]
        p2 = points_list[1]
        mp_x = (p1['x'] + p2['x']) / 2.0
        mp_y = (p1['y'] + p2['y']) / 2.0
        path_commands.append(f"Q {p1['x']} {p1['y']}, {mp_x} {mp_y}")

        for i in range(1, num_points - 1):
            p1 = points_list[i]
            p2 = points_list[i+1]
            mp_x = (p1['x'] + p2['x']) / 2.0
            mp_y = (p1['y'] + p2['y']) / 2.0
            path_commands.append(f"T {mp_x} {mp_y}")

        p_last = points_list[num_points - 1]
        p_first = points_list[0]
        mp_x_last = (p_last['x'] + p_first['x']) / 2.0
        mp_y_last = (p_last['y'] + p_first['y']) / 2.0
        path_commands.append(f"T {mp_x_last} {mp_y_last}")
        
        path_commands.append(f"Q {p_first['x']} {p_first['y']}, {points_list[0]['x']} {points_list[0]['y']}")


    path_commands.append("Z")
    return 1.0

cpdef tuple process_image_data_intensive(
    dict landmarks_data, 
    bytes original_image_base64_bytes
    # ,
    # bytes segmentation_map_base64_bytes
):

    cdef int i, j, dummy_calculation_result
    cdef list landmarks_list_of_lists
    cdef list clip_path_defs
    cdef list image_clips
    cdef list generated_mask_contours_list
    cdef dict region_names
    cdef list contour_group
    cdef str path_d_string
    cdef list raw_points
    cdef dict p
    cdef str region_name, clip_id
    cdef str defs_content, clips_content, final_svg_content, generated_svg_base64
    cdef int image_width, image_height
    cdef int crop_offset_x, crop_offset_y
    cdef float min_x, max_x, min_y, max_y
    cdef int crop_left, crop_top, crop_right, crop_bottom
    cdef int current_img_width, current_img_height
    cdef object img
    cdef object buffered

    dummy_calculation_result = 0
    for i in range(100):
        for j in range(1000):
            dummy_calculation_result += (i * j) % 12345

    rotated_and_cropped_image_base64_str = ""
    
    try:
        image_bytes = base64.b64decode(original_image_base64_bytes)
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
        
        landmarks_list_of_lists = landmarks_data.get('landmarks', [])
        
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        for i_group in range(len(landmarks_list_of_lists)):
            contour_group = landmarks_list_of_lists[i_group]
            for p_item in contour_group:
                if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                    min_x = min(min_x, <float>p_item['x'])
                    max_x = max(max_x, <float>p_item['x'])
                    min_y = min(min_y, <float>p_item['y'])
                    max_y = max(max_y, <float>p_item['y'])
        
        current_img_width, current_img_height = img.size

        crop_left = max(0, <int>math.floor(min_x - CROP_PADDING))
        crop_top = max(0, <int>math.floor(min_y - CROP_PADDING))
        crop_right = min(current_img_width, <int>math.ceil(max_x + CROP_PADDING))
        crop_bottom = min(current_img_height, <int>math.ceil(max_y + CROP_PADDING))

        if min_x == float('inf') or min_y == float('inf') or crop_right <= crop_left or crop_bottom <= crop_top:
            cropped_img = img
            crop_offset_x, crop_offset_y = 0, 0
        else:
            cropped_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            crop_offset_x, crop_offset_y = crop_left, crop_top
        
        image_width, image_height = cropped_img.size

        buffered = BytesIO()
        try:
            cropped_img.save(buffered, format=img.format if img.format else "JPEG")
        except KeyError:
            cropped_img.save(buffered, format="JPEG")
        rotated_and_cropped_image_base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    except Exception as e:
        image_dimensions = landmarks_data.get('dimensions', [1024, 1024])
        image_width = int(image_dimensions[0])
        image_height = int(image_dimensions[1])
        rotated_and_cropped_image_base64_str = original_image_base64_bytes.decode('utf-8')
        crop_offset_x, crop_offset_y = 0, 0
        # print(f"Error in Cython image processing (rotation/cropping): {e}")

    # --- Conceptual use of Segmentation Map ---
    # Decoding the segmentation map (for conceptual use)
    # seg_map_img = Image.open(BytesIO(base64.b64decode(segmentation_map_base64_bytes))).convert("L")
    # For actual contour extraction from pixel masks, you would use a CV library (e.g., OpenCV) here.
    # The current approach still relies on landmarks to define contours, but now they are
    # *conceptually* influenced by segmentation map knowledge for exclusion.

    processed_landmarks_list_of_lists = []
    cdef list adjusted_contour_group
    for i_group in range(len(landmarks_data.get('landmarks', []))):
        contour_group = landmarks_data.get('landmarks', [])[i_group]
        adjusted_contour_group = []
        for p_item in contour_group:
            if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                adjusted_contour_group.append({
                    'x': <float>p_item['x'] - crop_offset_x,
                    'y': <float>p_item['y'] - crop_offset_y
                })
        processed_landmarks_list_of_lists.append(adjusted_contour_group)


    clip_path_defs = []
    image_clips = []
    generated_mask_contours_list = []

    region_names = {
        0: "right_cheek", 1: "right_undereye", 2: "left_cheek", 3: "nose"
    }

    for i in range(len(processed_landmarks_list_of_lists)):
        contour_group = processed_landmarks_list_of_lists[i]
        if not contour_group:
            continue
        
        cdef list current_path_commands = []

        _points_to_smooth_svg_path_helper(contour_group, current_path_commands)
        path_d_string = " ".join(current_path_commands)
        
        raw_points = []
        for p_item in contour_group:
            if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                raw_points.append([<float>p_item['x'], <float>p_item['y']])

        region_name = region_names.get(i, f"region_{i+1}")
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

    defs_content = "\n".join(clip_path_defs)
    clips_content = "\n".join(image_clips)

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
    
    generated_svg_base664 = base64.b64encode(final_svg_content.encode('utf-8')).decode('utf-8')

    return generated_svg_base664, generated_mask_contours_list
