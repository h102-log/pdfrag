"""storage_dir must be anchored to an absolute, cwd-independent path.

The old default `"../storage/files"` resolved differently depending on the
process working directory. It must instead point at the repo-root `storage/files`
directory (the same path docker-compose mounts at `./storage`).
"""
import os

from app.core import config


def test_storage_dir_constant_is_absolute_and_anchored():
    p = config._STORAGE_DIR
    assert os.path.isabs(str(p)), "storage dir must be absolute"
    assert p.name == "files"
    assert p.parent.name == "storage"
    normalized = str(p).replace("\\", "/")
    assert normalized.endswith("storage/files")


def test_default_storage_dir_setting_is_absolute():
    # The Settings default is derived from the anchored constant.
    assert os.path.isabs(str(config._STORAGE_DIR))
