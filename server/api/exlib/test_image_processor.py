import base64
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
    from pyc import image_processor
    
    console.log(
        "[bold green]Successfully imported Cythonized image_processor from pyc.[/bold green]"
    )
except ImportError:
    # Fallback to pure Python version if Cython module is not found.
    from py import image_processor

    console.log(
        "[bold yellow]Cythonized image_processor not found. Using pure Python version from py.[/bold yellow]"
    )

def create_test_image(width=100, height=100, color=(255, 0, 0)):
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def encode_image_to_base64_bytes(img_bytes):
    return base64.b64encode(img_bytes)

def test__cropped_img_save_jpeg(tmp_path):
    img = Image.new("RGB", (10, 10), (123, 222, 111))
    buf = BytesIO()
    image_processor._cropped_img_save(img, buf, "JPEG")
    buf.seek(0)
    loaded = Image.open(buf)
    assert loaded.size == (10, 10)

def test__cropped_img_save_fallback_to_jpeg(tmp_path):
    img = Image.new("RGB", (10, 10), (123, 222, 111))
    buf = BytesIO()
    # Use an invalid format to trigger fallback
    image_processor._cropped_img_save(img, buf, "INVALID_FORMAT")
    buf.seek(0)
    loaded = Image.open(buf)
    assert loaded.size == (10, 10)

def test__dummy_calculation_runs():
    # Just ensure it runs without error
    image_processor._dummy_calculation()

@pytest.mark.parametrize(
    "points,exclude,expected_start",
    [
        ([{"x": 0, "y": 0}], None, "M 0 0 Z"),
        ([{"x": 0, "y": 0}, {"x": 10, "y": 10}], None, "M 0 0 L 10 10"),
        (
            [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}],
            None,
            "M 0 0 Q 0 0, 5.0 0.0 T 10.0 5.0 T 5.0 5.0 Z",
        ),
    ],
)
def test__points_to_smooth_svg_path_basic(points, exclude, expected_start):
    result = image_processor._points_to_smooth_svg_path(points, exclude)
    assert result.startswith(expected_start.split()[0])

def test__points_to_smooth_svg_path_with_exclusion():
    points = [{"x": 50, "y": 50}, {"x": 60, "y": 50}, {"x": 60, "y": 60}]
    exclude = [{"x": 55, "y": 55}]
    result = image_processor._points_to_smooth_svg_path(points, exclude)
    # Should adjust points away from exclusion center
    assert "M" in result and "Q" in result

def test__process_image_decoding_and_cropping_basic():
    img_bytes = create_test_image(100, 100)
    img_b64 = encode_image_to_base64_bytes(img_bytes)
    landmarks = {
        "landmarks": [
            [{"x": 10, "y": 10}, {"x": 90, "y": 10}, {"x": 90, "y": 90}, {"x": 10, "y": 90}]
        ]
    }
    result = image_processor._process_image_decoding_and_cropping(img_b64, landmarks)
    b64_str, w, h, off_x, off_y = result
    assert isinstance(b64_str, str)
    assert w > 0 and h > 0
    assert off_x >= 0 and off_y >= 0

def test__process_image_decoding_and_cropping_error(monkeypatch):
    # Pass invalid image data to trigger exception
    bad_img_b64 = b"not_base64"
    landmarks = {"dimensions": [123, 456]}
    result = image_processor._process_image_decoding_and_cropping(bad_img_b64, landmarks)
    b64_str, w, h, off_x, off_y = result
    assert w == 123 and h == 456
    assert off_x == 0 and off_y == 0

def test__generate_final_svg_content():
    svg = image_processor._generate_final_svg_content(
        100, 200, ['<clipPath id="a"></clipPath>'], ['<image width="100" height="200"/>']
    )
    assert svg.startswith('<svg')
    assert 'clipPath' in svg
    assert 'image' in svg
    assert 'width="100"' in svg
    assert 'height="200"' in svg

def test__extract_raw_points():
    contour = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    points = image_processor._extract_raw_points(contour)
    assert points == [[1, 2], [3, 4]]

def test_process_image_data_intensive_basic():
    img_bytes = create_test_image(100, 100)
    img_b64 = encode_image_to_base64_bytes(img_bytes)
    landmarks = {
        "landmarks": [
            [{"x": 10, "y": 10}, {"x": 90, "y": 10}, {"x": 90, "y": 90}, {"x": 10, "y": 90}],
            [{"x": 20, "y": 20}, {"x": 80, "y": 20}, {"x": 80, "y": 80}, {"x": 20, "y": 80}],
            [{"x": 30, "y": 30}, {"x": 70, "y": 30}, {"x": 70, "y": 70}, {"x": 30, "y": 70}],
            [{"x": 40, "y": 40}, {"x": 60, "y": 40}, {"x": 60, "y": 60}, {"x": 40, "y": 60}],
        ]
    }
    svg_b64, mask_contours = image_processor.process_image_data_intensive(
        loadtest_mode_enabled=True,
        landmarks_data=landmarks,
        original_image_base64_bytes=img_b64,
    )
    assert isinstance(svg_b64, str)
    assert isinstance(mask_contours, list)
    assert mask_contours and "name" in mask_contours[0] and "path_d" in mask_contours[0]