from pathlib import Path

from PIL import Image

from VGS_KI.backend.media_manager import ImageProcessor


def test_process_image_from_path_creates_pdf_ready_jpeg(tmp_path, monkeypatch) -> None:
    processor = ImageProcessor()
    processor.TEMP_DIR = tmp_path / "processed"
    processor._ensure_temp_dir()

    source = tmp_path / "generated.png"
    Image.new("RGBA", (320, 200), (30, 120, 210, 180)).save(source)

    result = processor.process_image_from_path(str(source))

    assert result is not None
    output = Path(result)
    assert output.exists()
    assert source.exists(), "The caller owns and removes the generated source image"
    with Image.open(output) as processed:
        assert processed.format == "JPEG"
        assert processed.mode == "RGB"
        assert processed.size == (320, 200)


def test_process_image_from_path_fails_safely_for_missing_file(tmp_path) -> None:
    processor = ImageProcessor()

    assert processor.process_image_from_path(str(tmp_path / "missing.png")) is None
