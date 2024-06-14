from rpoisel import ElispVisitor, cli, visit_click_app


def test_elisp_current() -> None:
    visitor = ElispVisitor()
    visit_click_app(cli, visitor)
    assert visitor.spit(), "at least something must be generated (for now)"
