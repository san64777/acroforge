from acroforge.engine.base import Writer, default_writer


def test_default_writer_satisfies_protocol():
    w = default_writer()
    assert isinstance(w, Writer)
    for meth in ("create_fields", "fill", "flatten"):
        assert callable(getattr(w, meth))
