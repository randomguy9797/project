import pytest
from app.validators import validate_mobile, detect_file_type, MAX_FILE_SIZE

# Mobile number validation
@pytest.mark.parametrize("number", ["9876543210", "8123456789", "7000000000", "6999999999"])
def test_valid_mobile(number):
    assert validate_mobile(number) is True


@pytest.mark.parametrize("number", ["5876543210", "1234567890", "98765432", "98765432101", "abcdefghij", ""])
def test_invalid_mobile(number):
    assert validate_mobile(number) is False


# File type detection
def test_detect_pdf():
    assert detect_file_type(b"%PDF-1.4 rest of file") == "pdf"


def test_detect_jpg():
    assert detect_file_type(b"\xff\xd8\xff\xe0 rest") == "jpg"


def test_detect_unknown():
    assert detect_file_type(b"UNKNOWN BYTES") is None
