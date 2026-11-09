import pytest

from spokecut.audio import _display_size


@pytest.mark.parametrize(
    ("stream", "size"),
    [
        ({"width": 1920, "height": 1080}, (1920, 1080)),
        ({"width": 1920, "height": 1080, "side_data_list": [{"rotation": -90}]}, (1080, 1920)),
        ({"width": 1920, "height": 1080, "side_data_list": [{"rotation": 180}]}, (1920, 1080)),
        ({"width": 1920, "height": 1080, "side_data_list": [{"side_data_type": "Other"}]}, (1920, 1080)),
        ({"width": 1920, "height": 1080, "tags": {"rotate": "270"}}, (1080, 1920)),
        ({"width": 1920, "height": 1080, "tags": {"rotate": "junk"}}, (1920, 1080)),
    ],
)
def test_display_size_follows_the_rotation_flag(stream, size):
    assert _display_size(stream) == size
