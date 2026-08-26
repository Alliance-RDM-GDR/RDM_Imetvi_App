# tests/test_thumbnail.py

from PIL import Image

from utils.thumbnail import supports_thumbnail, generate_thumbnail_bytes


def test_supports_thumbnail_true_for_jpg_png_tiff():
    assert supports_thumbnail("image.jpg")
    assert supports_thumbnail("image.jpeg")
    assert supports_thumbnail("image.png")
    assert supports_thumbnail("image.tif")
    assert supports_thumbnail("image.tiff")


def test_supports_thumbnail_false_for_non_raster_formats():
    assert not supports_thumbnail("scan.dcm")
    assert not supports_thumbnail("sky.fits")
    assert not supports_thumbnail("data.h5")
    assert not supports_thumbnail("data.nc")
    assert not supports_thumbnail("sample.lif")
    assert not supports_thumbnail("sample.czi")


def test_supports_thumbnail_case_insensitive():
    assert supports_thumbnail("IMAGE.JPG")
    assert supports_thumbnail("Image.PNG")


def test_generate_thumbnail_bytes_for_png(tmp_path):
    img_path = str(tmp_path / "sample.png")
    Image.new("RGB", (400, 300), color=(255, 0, 0)).save(img_path)

    thumb_bytes = generate_thumbnail_bytes(img_path)

    assert thumb_bytes is not None
    assert thumb_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # PNG file signature


def test_generate_thumbnail_bytes_respects_size_bound(tmp_path):
    img_path = str(tmp_path / "large.jpg")
    Image.new("RGB", (2000, 1000), color=(0, 255, 0)).save(img_path)

    thumb_bytes = generate_thumbnail_bytes(img_path, size=(100, 100))
    thumb_img = Image.open(__import__("io").BytesIO(thumb_bytes))

    assert thumb_img.width <= 100
    assert thumb_img.height <= 100


def test_generate_thumbnail_bytes_multipage_tiff_uses_first_frame(tmp_path):
    img_path = str(tmp_path / "multi.tif")
    frame1 = Image.new("RGB", (50, 50), color=(255, 0, 0))
    frame2 = Image.new("RGB", (50, 50), color=(0, 0, 255))
    frame1.save(img_path, save_all=True, append_images=[frame2])

    thumb_bytes = generate_thumbnail_bytes(img_path)

    assert thumb_bytes is not None


def test_generate_thumbnail_bytes_none_for_unsupported_extension(tmp_path):
    dcm_path = str(tmp_path / "scan.dcm")
    with open(dcm_path, "wb") as f:
        f.write(b"not a real dicom file")

    assert generate_thumbnail_bytes(dcm_path) is None


def test_generate_thumbnail_bytes_none_for_corrupt_file(tmp_path):
    fake_jpg = str(tmp_path / "broken.jpg")
    with open(fake_jpg, "wb") as f:
        f.write(b"this is not actually a jpeg")

    assert generate_thumbnail_bytes(fake_jpg) is None


def test_generate_thumbnail_bytes_none_for_missing_file(tmp_path):
    assert generate_thumbnail_bytes(str(tmp_path / "ghost.png")) is None
