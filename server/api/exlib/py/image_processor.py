import math
import base64
from io import BytesIO
from PIL import Image, ExifTags
from typing import List, Dict, Any

CROP_PADDING = 50


def _points_to_smooth_svg_path(points_list: List[Dict[str, float]]):

    if not points_list:
        return ""

    path_commands = []

    path_commands.append(f"M {points_list[0]['x']} {points_list[0]['y']}")

    num_points = len(points_list)
    for i in range(num_points):
        p1 = points_list[i]
        p2 = points_list[(i + 1) % num_points]

        if num_points == 1:
            return ""

        start_x = points_list[0]["x"]
        start_y = points_list[0]["y"]
        path_commands.append(f"M {start_x} {start_y}")

        if num_points == 2:
            path_commands.append(f"L {points_list[1]['x']} {points_list[1]['y']}")
        else:
            mp_x = (points_list[0]["x"] + points_list[1]["x"]) / 2
            mp_y = (points_list[0]["y"] + points_list[1]["y"]) / 2
            path_commands.append(
                f"Q {points_list[0]['x']} {points_list[0]['y']}, {mp_x} {mp_y}"
            )

            for i in range(1, num_points - 1):
                p_current = points_list[i]
                p_next = points_list[i + 1]

                mp_x = (p_current["x"] + p_next["x"]) / 2
                mp_y = (p_current["y"] + p_next["y"]) / 2
                path_commands.append(f"T {mp_x} {mp_y}")

            p_last = points_list[num_points - 1]
            p_first = points_list[0]
            mp_x_last = (p_last["x"] + p_first["x"]) / 2
            mp_y_last = (p_last["y"] + p_first["y"]) / 2
            path_commands.append(f"T {mp_x_last} {mp_y_last}")

            path_commands.append(
                f"Q {p_first['x']} {p_first['y']}, {start_x} {start_y}"
            )

    path_commands.append("Z")
    return " ".join(path_commands)


def process_image_data_intensive(
    landmarks_data: Dict[str, Any], original_image_base64_bytes: bytes
):

    dummy_calculation_result = 0

    for i in range(100):
        for j in range(1000):
            dummy_calculation_result += (i * j) % 12345

    rotated_and_cropped_image_base64_str = ""
    image_width, image_height = 0, 0
    crop_offset_x, crop_offset_y = 0, 0

    try:
        image_bytes = base64.b64decode(original_image_base64_bytes)
        img = Image.open(BytesIO(image_bytes))

        exif = img._getexif()
        if exif:
            for orientation_tag_id in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation_tag_id] == "Orientation":
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

        landmarks_list_of_lists = landmarks_data.get("landmarks", [])

        min_x, max_x = float("inf"), float("-inf")
        min_y, max_y = float("inf"), float("-inf")

        for contour_group in landmarks_list_of_lists:
            for point_data in contour_group:
                if (
                    isinstance(point_data, dict)
                    and "x" in point_data
                    and "y" in point_data
                ):
                    min_x = min(min_x, point_data["x"])
                    max_x = max(max_x, point_data["x"])
                    min_y = min(min_y, point_data["y"])
                    max_y = max(max_y, point_data["y"])

        current_img_width, current_img_height = img.size

        crop_left = math.floor(max(0, min_x - CROP_PADDING))
        crop_top = math.floor(max(0, min_y - CROP_PADDING))
        crop_right = math.ceil(min(current_img_width, max_x + CROP_PADDING))
        crop_bottom = math.ceil(min(current_img_height, max_y + CROP_PADDING))

        if (
            min_x == float("inf")
            or min_y == float("inf")
            or crop_right <= crop_left
            or crop_bottom <= crop_top
        ):
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
        rotated_and_cropped_image_base64_str = base64.b64encode(
            buffered.getvalue()
        ).decode("utf-8")

    except Exception as e:
        # print(f"Error during image processing (rotation or cropping): {e}. Using original image data and dimensions.")
        image_dimensions_from_landmarks = landmarks_data.get("dimensions", [1024, 1024])
        image_width, image_height = int(image_dimensions_from_landmarks[0]), int(
            image_dimensions_from_landmarks[1]
        )
        rotated_and_cropped_image_base64_str = original_image_base64_bytes.decode(
            "utf-8"
        )
        crop_offset_x, crop_offset_y = 0, 0

    processed_landmarks_list_of_lists = []
    for contour_group in landmarks_data.get("landmarks", []):
        adjusted_contour_group = []
        for point_data in contour_group:
            if isinstance(point_data, dict) and "x" in point_data and "y" in point_data:
                adjusted_contour_group.append(
                    {
                        "x": point_data["x"] - crop_offset_x,
                        "y": point_data["y"] - crop_offset_y,
                    }
                )
        processed_landmarks_list_of_lists.append(adjusted_contour_group)

    clip_path_defs = []
    image_clips = []
    generated_mask_contours_list = []

    region_names = {0: "right_cheek", 1: "right_undereye", 2: "left_cheek", 3: "nose"}

    for i, contour_group in enumerate(processed_landmarks_list_of_lists):
        if not contour_group:
            continue

        path_d_string = _points_to_smooth_svg_path(contour_group)
        raw_points = [
            [p["x"], p["y"]]
            for p in contour_group
            if isinstance(p, dict) and "x" in p and "y" in p
        ]

        region_name = region_names.get(i, f"region_{i+1}")
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        clip_path_defs.append(
            f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>'
        )

        image_clips.append(
            f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{rotated_and_cropped_image_base64_str}" />'
        )

        generated_mask_contours_list.append(
            {"name": region_name, "path_d": path_d_string, "points": raw_points}
        )

    defs_content = "\n".join(clip_path_defs)
    clips_content = "\n".join(image_clips)

    final_svg_content = (
        f'<svg viewBox="0 0 {image_width} {image_height}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f"    <defs>\n"
        f"        {defs_content}\n"
        f"    </defs>\n"
        f"    <!-- Draw a base image or background if desired, though clip-path images will cover it -->\n"
        f'    <rect x="0" y="0" width="{image_width}" height="{image_height}" fill="#FAFAFA"/>\n'
        f"    {clips_content}\n"
        f"</svg>"
    )

    generated_svg_base64 = base64.b64encode(final_svg_content.encode("utf-8")).decode(
        "utf-8"
    )

    return generated_svg_base64, generated_mask_contours_list
