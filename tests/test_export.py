from stylist.export import allowed_image_url, csv_value, image_extension


def test_image_export_only_accepts_known_cdn_and_real_raster_signatures():
    assert allowed_image_url("https://aicloset-domestic.aidacloset.com/image.png")
    assert not allowed_image_url("https://aicloset-domestic.aidacloset.com.attacker.test/image.png")
    assert not allowed_image_url("https://127.0.0.1/image.png")
    assert not allowed_image_url("https://user:secret@aicloset-domestic.aidacloset.com/image.png")
    assert image_extension(b"\x89PNG\r\n\x1a\nanything") == ".png"
    assert image_extension(b"<html>not an image</html>") is None
    assert image_extension(b"<svg>not a raster image</svg>") is None


def test_csv_titles_cannot_become_formulas_when_opened_in_excel():
    assert csv_value('=HYPERLINK("https://example.test")').startswith("'")
    assert csv_value("  +danger").startswith("'")
    assert csv_value("白色衬衫") == "白色衬衫"
