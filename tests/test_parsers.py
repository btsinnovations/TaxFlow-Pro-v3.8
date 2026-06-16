def test_alias_normalization_with_fixture():
<<<<<<< HEAD
=======
    from pathlib import Path
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    from phase3_pipeline.categorizer import PriorityCategorizer
    import tempfile
    import shutil
    # Use test_aliases.yaml from the same directory
    fixture_path = Path(__file__).parent / "test_aliases.yaml"
    if not fixture_path.exists():
        pytest.skip("test_aliases.yaml not found")
    cat = PriorityCategorizer(str(fixture_path))
    result = cat._apply_aliases("WAL-MART #123")
    assert result == "WALMART"