import base64
import math
import pytest
from PIL import Image
from io import BytesIO
from services.logger import console

# Import the image processing function
# This block attempts to import the compiled Cython module first from the new path.
# If the Cython module (image_processor.so/.pyd within exlib/pyc) is found and successfully imported,
# it will use that for performance.
# If an ImportError occurs, it will fall back to importing the
# pure Python version of image_processor.py from exlib/py.
#
# IMPORTANT: Ensure your project structure includes:
# - exlib/
# - exlib/__init__.py (empty file)
# - exlib/pyc/
# - exlib/pyc/__init__.py (empty file)
# - exlib/pyc/image_processor.pyx (your Cython source)
# - exlib/py/
# - exlib/py/__init__.py (empty file)
# - exlib/py/image_processor.py (your pure Python source)
#
# After compiling image_processor.pyx, the compiled .so/.pyd file will appear
# alongside image_processor.pyx in exlib/pyc.
try:
    from pyc.image_processor import image_processor

    console.log(
        "[bold green]Successfully imported Cythonized image_processor from pyc.[/bold green]"
    )
except ImportError:
    # Fallback to pure Python version if Cython module is not found.
    from py.image_processor import image_processor

    console.log(
        "[bold yellow]Cythonized image_processor not found. Using pure Python version from py.[/bold yellow]"
    )


def test_points_to_smooth_svg_path_empty():
    assert image_processor._points_to_smooth_svg_path([]) == ""

def test_points_to_smooth_svg_path_single_point():
    points = [{"x": 10, "y": 20}]
    expected = "M 10 20 Z"
    assert image_processor._points_to_smooth_svg_path(points) == expected

def test_points_to_smooth_svg_path_two_points():
    points = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
    expected = "M 10 20 L 30 40"
    assert image_processor._points_to_smooth_svg_path(points) == expected

def test_points_to_smooth_svg_path_three_points():
    points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]
    result = image_processor._points_to_smooth_svg_path(points)
    assert result.startswith("M 0 0 Q 0 0, 5.0 0.0 T 10.0 5.0 T 5.0 5.0 Z")

def test_points_to_smooth_svg_path_exclude_region():
    points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]
    exclude = [{"x": 5, "y": 5}]
    result = image_processor._points_to_smooth_svg_path(points, exclude)
    assert isinstance(result, str)
    assert result.startswith("M ")

def test_cropped_img_save_jpeg(tmp_path):
    img = Image.new("RGB", (10, 10), color="red")
    buf = BytesIO()
    image_processor._cropped_img_save(img, buf, "JPEG")
    buf.seek(0)
    loaded = Image.open(buf)
    assert loaded.format == "JPEG"

def test_cropped_img_save_fallback(tmp_path):
    img = Image.new("RGB", (10, 10), color="blue")
    buf = BytesIO()
    # Pass an invalid format to trigger fallback
    image_processor._cropped_img_save(img, buf, "INVALID_FORMAT")
    buf.seek(0)
    loaded = Image.open(buf)
    assert loaded.format == "JPEG"

def test_dummy_calculation_runs():
    # Just ensure it runs without error
    image_processor._dummy_calculation()

def create_test_image_base64():
    img = Image.new("RGB", (100, 100), color="white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue())

def test_process_image_data_intensive_basic():
    img_b64 = create_test_image_base64()
    landmarks = {
        "landmarks": [
            [{"x": 10, "y": 10}, {"x": 20, "y": 10}, {"x": 20, "y": 20}],
            [{"x": 30, "y": 30}, {"x": 40, "y": 30}, {"x": 40, "y": 40}],
            [{"x": 50, "y": 50}, {"x": 60, "y": 50}, {"x": 60, "y": 60}],
            [{"x": 70, "y": 70}, {"x": 80, "y": 70}, {"x": 80, "y": 80}],
        ],
        "dimensions": [100, 100]
    }
    svg_b64, mask_contours = image_processor.process_image_data_intensive(
        loadtest_mode_enabled=True,
        landmarks_data=landmarks,
        original_image_base64_bytes=img_b64,
    )
    assert isinstance(svg_b64, str)
    assert isinstance(mask_contours, list)
    assert len(mask_contours) == 4
    # SVG should decode to valid XML
    svg_xml = base64.b64decode(svg_b64).decode("utf-8")
    assert svg_xml.startswith("<svg")
    assert "clipPath" in svg_xml

def test_process_image_data_intensive_no_landmarks():
    img_b64 = create_test_image_base64()
    landmarks = {"landmarks": [], "dimensions": [100, 100]}
    svg_b64, mask_contours = image_processor.process_image_data_intensive(
        loadtest_mode_enabled=True,
        landmarks_data=landmarks,
        original_image_base64_bytes=img_b64,
    )
    assert isinstance(svg_b64, str)
    assert isinstance(mask_contours, list)
    svg_xml = base64.b64decode(svg_b64).decode("utf-8")
    assert svg_xml.startswith("<svg")