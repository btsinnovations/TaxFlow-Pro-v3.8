"""Version constant verification for release tags."""


def test_version_is_3_11_5():
    from backend.version import version

    assert version == "3.11.5"
