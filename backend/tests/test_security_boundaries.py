from app.security import validate_upload


def test_upload_rejects_path_traversal():
    try:
        validate_upload('../secret.pdf', 'application/pdf', 10, 100)
    except ValueError:
        return
    raise AssertionError('path traversal filename must be rejected')


def test_upload_rejects_mismatched_extension():
    try:
        validate_upload('document.png', 'application/pdf', 10, 100)
    except ValueError:
        return
    raise AssertionError('mismatched content type must be rejected')
