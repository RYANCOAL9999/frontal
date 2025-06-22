import base64
from typing import List, Dict, Any

def _points_to_svg_path(points_list: List[Dict[str, float]]):

    if not points_list:
        return ""
    
    path_commands = []
    path_commands.append(f"M {points_list[0]['x']} {points_list[0]['y']}")
    for point in points_list[1:]:
        path_commands.append(f"L {point['x']} {point['y']}")
    
    path_commands.append("Z")
    return " ".join(path_commands)

def process_image_data_intensive(
    landmarks_data: Dict[str, Any],
    original_image_base64: str,
    image_width: int,
    image_height: int
):
    
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

    for i, contour_group in enumerate(landmarks_list_of_lists):
        if not contour_group:
            continue
        
        path_d_string = _points_to_svg_path(contour_group)
        raw_points = [[p['x'], p['y']] for p in contour_group if isinstance(p, dict) and 'x' in p and 'y' in p]

        region_name = region_names.get(i, f"region_{i+1}")
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        clip_path_defs.append(f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>')
        
        image_clips.append(f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{original_image_base64}" />')

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