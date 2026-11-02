from newsgenie.responder import general_reply, numbered_sources_md


def test_sources_are_one_per_line_and_clipped():
    results = [
        {"title": "A" * 300, "url": "https://example.org/1", "snippet": ""},
        {"title": "Second [source]", "url": "https://example.org/2", "snippet": ""},
    ]
    md = numbered_sources_md(results)
    lines = md.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("1. [") and lines[1].startswith("2. [")
    assert len(lines[0]) < 160 and "..." in lines[0]
    assert "[Second (source)]" in lines[1]  # brackets can't break the link


def test_general_reply_sources_render_as_list():
    class LLM:
        def invoke(self, _):
            return type("M", (), {"content": "Answer [1][2]."})()

    results = [{"title": f"T{i}", "url": f"https://e.org/{i}", "snippet": "s"} for i in range(1, 4)]
    text, used = general_reply(LLM(), "q", [], results)
    assert used
    assert "**Sources**\n\n1. [T1](https://e.org/1)\n2. [T2]" in text
