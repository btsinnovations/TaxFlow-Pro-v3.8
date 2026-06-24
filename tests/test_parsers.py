def test_alias_normalization_with_fixture():
    from pathlib import Path
    from phase3_pipeline.categorizer import PriorityCategorizer
    import tempfile
    import shutil
    # Use test_aliases.yaml from the same directory
    fixture_path = Path(__file__).parent / "test_aliases.yaml"
    if not fixture_path.exists():
        pytest.skip("test_aliases.yaml not found")
    cat = PriorityCategorizer(str(fixture_path))
    # Strict mode truncates trailing store/location tokens.
    assert cat._apply_aliases("WAL-MART #123") == "WALMART"
    # Substring override keeps replacement anywhere in the string.
    assert cat._apply_aliases("PAYPAL *XYZ") == "PAYPAL"
    assert cat._apply_aliases("XYZ PAYPAL TRANSFER") == "XYZ PAYPAL"
