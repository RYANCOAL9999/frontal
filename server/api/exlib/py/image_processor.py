import math
import base64
from io import BytesIO
from PIL import Image, ExifTags
from typing import List, Dict, Any, Optional, Tuple

# Constants for cropping
CROP_PADDING = 50  # Padding around the detected landmarks for cropping

# Define region names for the contours
region_names = {
    0: "right_cheek",
    1: "right_undereye",
    2: "left_cheek",
    3: "nose",  # Assuming 0 is right_cheek and 3 is nose
    # , Add more regions as needed
}


# Function to save the cropped image to a BytesIO buffer
def _cropped_img_save(
    image: Image.Image, 
    buffered: BytesIO, 
    format: Optional[str]
) -> None:
    try:
        image.save(buffered, format=format if format else "JPEG")
    except Exception:
        image.save(buffered, format="JPEG")


# Function to simulate intensive calculations
def _dummy_calculation(
        
) -> None:
    # dummy calculation to mimic the original code's complexity
    dummy_calculation_result = 0

    # Simulate some intensive calculations
    for i in range(100):
        for j in range(1000):
            dummy_calculation_result += (i * j) % 12345


# Helper function to convert points to a smooth SVG path
def _points_to_smooth_svg_path(
    points_list: List[Dict[str, float]],
    exclude_region_landmarks: Optional[List[Dict[str, float]]] = None,
) -> str:

    # Ensure points_list is not empty
    if not points_list:
        return ""

    # Ensure exclude_region_landmarks is a list, default to empty if None
    path_commands = []

    # If exclude_region_landmarks is None, we treat it as an empty list
    adjusted_points = []

    # If exclude_region_landmarks is provided, we will adjust points away from it
    if exclude_region_landmarks and len(points_list) > 2:

        # the start of the excluded region
        ex_cx, ex_cy = 0.0, 0.0

        # Calculate the center of the excluded region landmarks
        if exclude_region_landmarks:
            sum_x = sum(p["x"] for p in exclude_region_landmarks)
            sum_y = sum(p["y"] for p in exclude_region_landmarks)
            ex_cx = (
                sum_x / len(exclude_region_landmarks) if exclude_region_landmarks else 0
            )
            ex_cy = (
                sum_y / len(exclude_region_landmarks) if exclude_region_landmarks else 0
            )

        # Iterate through points to adjust them away from the excluded region center
        for point in points_list:
            dist = math.sqrt((point["x"] - ex_cx) ** 2 + (point["y"] - ex_cy) ** 2)
            if dist < CROP_PADDING * 2:  # Arbitrary "too close" threshold
                # Move point slightly away from the center of the excluded region
                dx, dy = point["x"] - ex_cx, point["y"] - ex_cy
                if dx == 0 and dy == 0:
                    dx, dy = 1, 1  # Prevent division by zero
                norm = math.sqrt(dx * dx + dy * dy)
                if norm == 0:
                    adj_x = point["x"] + 5  # Arbitrarily move 5 pixels in x
                    adj_y = point["y"] + 5  # Arbitrarily move 5 pixels in y
                else:
                    adj_x = point["x"] + (dx / norm) * 5  # Move 5 pixels away
                    adj_y = point["y"] + (dy / norm) * 5
                adjusted_points.append({"x": adj_x, "y": adj_y})
            else:
                adjusted_points.append(point)
    else:
        adjusted_points = points_list

    # Now generate the smooth path using the adjusted points
    num_points = len(adjusted_points)
    if num_points == 0:
        return ""
    if num_points == 1:
        return f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']} Z"  # Single point as a path

    # Move to the first point
    path_commands.append(f"M {adjusted_points[0]['x']} {adjusted_points[0]['y']}")

    if num_points == 2:
        path_commands.append(f"L {adjusted_points[1]['x']} {adjusted_points[1]['y']}")
    else:
        # First segment (P0 to midpoint of P0 and P1)
        p1 = adjusted_points[0]
        p2 = adjusted_points[1]
        mp_x = (p1["x"] + p2["x"]) / 2.0
        mp_y = (p1["y"] + p2["y"]) / 2.0
        path_commands.append(f"Q {p1['x']} {p1['y']}, {mp_x} {mp_y}")

        # Intermediate segments (midpoint to midpoint, using current point as control)
        for i in range(1, num_points - 1):
            p1 = adjusted_points[i]
            p2 = adjusted_points[i + 1]
            mp_x = (p1["x"] + p2["x"]) / 2.0
            mp_y = (p1["y"] + p2["y"]) / 2.0
            # The SVG "T" command is a shorthand for smooth quadratic Bézier curves and requires a preceding "Q" command.
            path_commands.append(f"T {mp_x} {mp_y}")

        # Last segment (midpoint between last and first, using last point as control)
        p_last = adjusted_points[num_points - 1]
        p_first = adjusted_points[0]
        mp_x_last = (p_last["x"] + p_first["x"]) / 2.0
        mp_y_last = (p_last["y"] + p_first["y"]) / 2.0
        path_commands.append(f"T {mp_x_last} {mp_y_last}")

    # The "Z" command will close the path, so no need for an extra "Q" command here.
    path_commands.append("Z")
    return " ".join(path_commands)


# New function to encapsulate image decoding and cropping logic
def _process_image_decoding_and_cropping(
    original_image_base64_bytes: bytes, 
    landmarks_data: Dict[str, Any]
) -> Tuple[str, int, int, int, int]:

    image_width, image_height = 0, 0
    crop_offset_x, crop_offset_y = 0, 0
    rotated_and_cropped_image_base64_str = ""

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
        _cropped_img_save(cropped_img, buffered, img.format)
        rotated_and_cropped_image_base64_str = base64.b64encode(
            buffered.getvalue()
        ).decode("utf-8")

    except Exception as e:
        # print(f"Error during image processing (rotation or cropping): {e}. Using original image data and dimensions.")

        # If any error occurs, we will use the original image data and dimensions
        image_dimensions_from_landmarks = landmarks_data.get("dimensions", [1024, 1024])
        image_width, image_height = int(image_dimensions_from_landmarks[0]), int(
            image_dimensions_from_landmarks[1]
        )
        rotated_and_cropped_image_base64_str = original_image_base64_bytes.decode(
            "utf-8"
        )
        crop_offset_x, crop_offset_y = 0, 0
        # You might want to log the error here: print(f"Error: {e}")

    return (
        rotated_and_cropped_image_base64_str,
        image_width,
        image_height,
        crop_offset_x,
        crop_offset_y,
    )


def _generate_final_svg_content(
    image_width: int,
    image_height: int,
    clip_path_defs: List[str],
    image_clips: List[str],
) -> str:

    defs_content = "\n".join(clip_path_defs)
    clips_content = "\n".join(image_clips)

    final_svg_content = (
        f'<svg viewBox="0 0 {image_width} {image_height}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f"    <defs>\n"
        f"        {defs_content}\n"
        f"    </defs>\n"
        f'    <rect x="0" y="0" width="{image_width}" height="{image_height}" fill="#FAFAFA"/>\n'
        f"    {clips_content}\n"
        f"</svg>"
    )
    return final_svg_content


def _extract_raw_points(
    contour_group: List[Dict[str, float]]
) -> List[List[float]]:
    raw_points = [
        [p["x"], p["y"]]
        for p in contour_group
        if isinstance(p, dict) and "x" in p and "y" in p
    ]
    return raw_points


# Function to process image data and landmarks, performing cropping and SVG generation
def process_image_data_intensive(
    loadtest_mode_enabled: bool,
    landmarks_data: Dict[str, Any],
    original_image_base64_bytes: bytes,
    # , segmentation_map_base64_bytes: bytes
) -> Tuple[str, List[Dict[str, Any]]]:
    # Calling the dummy calculation to simulate intensive processing
    if not loadtest_mode_enabled:
        _dummy_calculation()

    # Call the new helper function to handle image decoding and cropping
    (
        rotated_and_cropped_image_base64_str,
        image_width,
        image_height,
        crop_offset_x,
        crop_offset_y,
    ) = _process_image_decoding_and_cropping(
        original_image_base64_bytes, landmarks_data
    )

    # --- Conceptual use of Segmentation Map ---
    # In a real scenario, you would parse the segmentation_map_base64_bytes here.
    # This would involve:
    # 1. Decoding the segmentation map:
    #    seg_map_img = Image.open(BytesIO(base64.b64decode(segmentation_map_base64_bytes)))
    # 2. Potentially resizing/cropping the segmentation map to match the processed image.
    # 3. Extracting pixel regions for each semantic area (e.g., 'skin', 'nose', 'right_cheek').
    #    This often involves checking pixel values.
    # 4. Converting these pixel masks into vector contours (e.g., using OpenCV's findContours).
    #    This is the most complex part and is beyond basic Pillow capabilities.
    #
    # For now, we will proceed with landmark-based contouring but indicate where
    # segmentation map logic would ideally be integrated for superior mask quality.

    # Placeholder for segmentation map processing
    # print(f"Segmentation map bytes length: {len(segmentation_map_base64_bytes)}")
    # If we had pixel values, we could define masks here.
    # Example:
    # seg_img_pil = Image.open(BytesIO(base64.b64decode(segmentation_map_base64_bytes))).convert("L") # Convert to grayscale
    # Example: mask for skin where pixel_value == X
    # skin_mask = seg_img_pil.point(lambda p: 255 if p == SKIN_PIXEL_VALUE else 0)
    # Then use skin_mask to derive contours for the whole face.

    # --- Extract and Process Landmark Data (and adjust for cropping) ---
    processed_landmarks_list_of_lists = []
    # Identify the nose region landmarks for exclusion
    nose_landmarks_adjusted = []

    # Assuming index 3 corresponds to the nose in your landmarks.txt structure
    if len(landmarks_data.get("landmarks", [])) > 3:
        # Original nose landmarks
        original_nose_landmarks = landmarks_data["landmarks"][3]
        # Adjust nose landmarks for cropping
        for point_data in original_nose_landmarks:
            if isinstance(point_data, dict) and "x" in point_data and "y" in point_data:
                nose_landmarks_adjusted.append(
                    {
                        "x": point_data["x"] - crop_offset_x,
                        "y": point_data["y"] - crop_offset_y,
                    }
                )

    # Process each contour group in the landmarks data
    for i, contour_group in enumerate(landmarks_data.get("landmarks", [])):

        # Adjust each point in the contour group for cropping
        adjusted_contour_group = []

        # If the contour group is empty, skip it
        for point_data in contour_group:
            if isinstance(point_data, dict) and "x" in point_data and "y" in point_data:
                # Adjust the point coordinates based on the crop offsets
                adjusted_contour_group.append(
                    {
                        "x": point_data["x"] - crop_offset_x,
                        "y": point_data["y"] - crop_offset_y,
                    }
                )

        # Append the adjusted contour group to the processed landmarks list
        processed_landmarks_list_of_lists.append(adjusted_contour_group)

    # Prepare the SVG content with clip paths for each region
    clip_path_defs = []
    image_clips = []
    generated_mask_contours_list = []

    # Iterate through the processed landmarks and create SVG clip paths
    for i, contour_group in enumerate(processed_landmarks_list_of_lists):

        # Skip empty contour groups
        if not contour_group:
            continue

        region_name = region_names.get(i, f"region_{i+1}")

        # Apply exclusion logic for Region 0 (right_cheek) if it's supposed to avoid the nose
        exclude_target_landmarks = None

        # This is the conceptual part for "Region No.4 (right_cheek assuming index 0) should not intersect the nose"
        if (
            region_name == "right_cheek" and nose_landmarks_adjusted
        ):  # Check if it's the right cheek and nose landmarks exist
            exclude_target_landmarks = nose_landmarks_adjusted

        # Convert the contour group to a smooth SVG path
        path_d_string = _points_to_smooth_svg_path(
            contour_group, exclude_target_landmarks
        )

        # If the region name is not found, use a default name
        clip_id = f"mask_{region_name.replace(' ', '_')}"

        # Create the clip path definition
        clip_path_defs.append(
            f'<clipPath id="{clip_id}"><path d="{path_d_string}" /></clipPath>'
        )

        # Create the image clip with the rotated and cropped image
        image_clips.append(
            f'<image width="{image_width}" height="{image_height}" clip-path="url(#{clip_id})" xlink:href="data:image/jpeg;base64,{rotated_and_cropped_image_base64_str}" />'
        )

        # Append the generated mask contour data
        generated_mask_contours_list.append(
            {
                "name": region_name,
                "path_d": path_d_string,
                "points": _extract_raw_points(
                    contour_group
                ),  # If the path is empty, skip this contour
            }
        )

    # Prepare the final SVG content
    final_svg_content = _generate_final_svg_content(
        image_width,
        image_height,
        rotated_and_cropped_image_base64_str,
        clip_path_defs,
        image_clips,
    )

    # Encode the final SVG content to base64
    generated_svg_base64 = base64.b64encode(final_svg_content.encode("utf-8")).decode(
        "utf-8"
    )

    # Return the base64 encoded SVG and the generated mask contours list
    return generated_svg_base64, generated_mask_contours_list
