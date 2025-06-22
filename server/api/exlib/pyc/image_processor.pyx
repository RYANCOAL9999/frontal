import base64
from typing import List, Dict, Any

cdef float _points_to_svg_path_helper(list points_list, list path_commands):

    cdef dict point
    cdef float x, y
    
    if not points_list:
        return 0.0
    
    point = points_list[0]
    x = point['x']
    y = point['y']
    path_commands.append(f"M {x} {y}")

    for i in range(1, len(points_list)):
        point = points_list[i]
        x = point['x']
        y = point['y']
        path_commands.append(f"L {x} {y}")
    
    path_commands.append("Z")
    return 1.0 


cpdef tuple process_image_data_intensive(
    dict landmarks_data,
    bytes original_image_base64_bytes,
    int image_width,
    int image_height
):
    # Declare C types for variables
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

    dummy_calculation_result = 0
    for i in range(100): 
        for j in range(1000): 
            dummy_calculation_result += (i * j) % 12345 

    landmarks_list_of_lists = landmarks_data.get('landmarks', [])

    clip_path_defs = []
    image_clips = []
    generated_mask_contours_list = []

    region_names = {
        0: "right_cheek", 1: "right_undereye", 2: "left_cheek", 3: "nose"
    }

    for i in range(len(landmarks_list_of_lists)):
        contour_group = landmarks_list_of_lists[i]
        if not contour_group:
            continue
        
        # Use helper for path generation
        cdef list current_path_commands = []
        _points_to_svg_path_helper(contour_group, current_path_commands)
        path_d_string = " ".join(current_path_commands)
        
        raw_points = []
        for p_item in contour_group:
            if isinstance(p_item, dict) and 'x' in p_item and 'y' in p_item:
                raw_points.append([<float>p_item['x'], <float>p_item['y']]) # Type cast for clarity

        region_name = region_names.get(i, f"region_{i+1}")
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        clip_path_defs.append(f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>')
        
        image_clips.append(f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{original_image_base64_bytes.decode("utf-8")}" />')

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
    
    generated_svg_base64 = base64.b64encode(final_svg_content.encode('utf-8')).decode('utf-8')

    return generated_svg_base64, generated_mask_contours_list