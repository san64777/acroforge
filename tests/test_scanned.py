from acroforge.detect.scanned import is_scanned_pdf

def test_vector_form_is_not_scanned():
    assert is_scanned_pdf("tests/fixtures/fw9.pdf") is False

def test_image_only_pdf_is_scanned():
    assert is_scanned_pdf("tests/fixtures/scanned_sample.pdf") is True
