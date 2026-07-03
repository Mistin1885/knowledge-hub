"""Pure-domain tests: parser, chunking, y_markdown, wire protocol."""

from pycrdt import Doc, XmlFragment

from app.modules.collab.domain import protocol
from app.modules.collab.domain.y_markdown import fragment_to_md, md_to_fragment
from app.modules.links.domain import parser
from app.modules.search.domain.chunking import chunk_markdown
from app.shared.constants import LinkKind


class TestParser:
    def test_frontmatter(self):
        meta, tags, body = parser.parse_frontmatter(
            "---\nproject: km\ntags: [a, b]\nowner: alice\n---\n# Hi\n"
        )
        assert meta == {"project": "km", "owner": "alice"}
        assert tags == ["a", "b"]
        assert body.startswith("# Hi")

    def test_no_frontmatter(self):
        meta, tags, body = parser.parse_frontmatter("# Just content")
        assert meta == {} and tags == [] and body == "# Just content"

    def test_wikilinks(self):
        links = parser.extract_links("See [[Page One]] and [[Page Two|alias]] and [[Page Three#sec]].")
        titles = {link.target_title for link in links}
        assert titles == {"Page One", "Page Two", "Page Three"}
        assert all(link.kind == LinkKind.WIKI for link in links)

    def test_links_skip_code(self):
        md = "```\n[[NotALink]]\n```\nreal [[Link]] and `[[inline no]]`"
        links = parser.extract_links(md)
        assert [link.target_title for link in links] == ["Link"]

    def test_md_link_as_title(self):
        links = parser.extract_links("see [spec](API-Design.md) and [ext](https://x.com)")
        assert [(link.target_title, link.kind) for link in links] == [
            ("API Design", LinkKind.MARKDOWN)
        ]

    def test_strip_markdown(self):
        text = parser.strip_markdown("# T\n**bold** [[Link|show]] `code`\n")
        assert "bold" in text and "Link" in text
        assert "#" not in text and "*" not in text and "`" not in text

    def test_unlinked_context(self):
        assert parser.find_unlinked_context("mention of Roadmap here", "Roadmap")
        assert parser.find_unlinked_context("only [[Roadmap]] linked", "Roadmap") is None


class TestChunking:
    def test_split_by_heading(self):
        chunks = chunk_markdown("intro text here padded out to minimum length ok\n\n## A\nbody a\n\n## B\nbody b", "T")
        headings = [c.heading for c in chunks]
        assert None in headings and "A" in headings and "B" in headings

    def test_long_section_split(self):
        md = "## Long\n" + "\n\n".join(["paragraph " + "x" * 300] * 10)
        chunks = chunk_markdown(md, "T")
        assert len(chunks) > 1
        assert all(len(c.text) <= 1700 for c in chunks)


class TestYMarkdown:
    def roundtrip(self, md: str) -> str:
        doc = Doc()
        frag = doc.get("default", type=XmlFragment)
        md_to_fragment(md, frag)
        return fragment_to_md(frag)

    def test_roundtrip_stable(self):
        md = (
            "# 標題\n\n中文 **粗體** *斜體* `code` [[維基連結]] [外部](https://x.com)\n\n"
            "- 清單一\n- 清單二\n  - 巢狀\n\n1. 第一\n2. 第二\n\n"
            "- [ ] 待辦\n- [x] 完成\n\n> 引用\n\n```python\nx = 1\n```\n\n---\n"
        )
        once = self.roundtrip(md)
        twice = self.roundtrip(once)
        assert once == twice
        for token in ["# 標題", "**粗體**", "[[維基連結]]", "- [x] 完成", "```python", "---"]:
            assert token in once

    def test_cjk_marks_order(self):
        out = self.roundtrip("這是 **粗體** 和後面")
        assert out.strip() == "這是 **粗體** 和後面"

    def test_empty(self):
        assert self.roundtrip("") == ""


class TestProtocol:
    def test_varuint(self):
        for n in (0, 1, 127, 128, 300, 2**20):
            data = protocol.write_varuint(n)
            value, pos = protocol.read_varuint(data, 0)
            assert value == n and pos == len(data)

    def test_awareness_roundtrip(self):
        entries = [
            protocol.AwarenessEntry(1, 2, '{"user": {"name": "a"}}'),
            protocol.AwarenessEntry(99, 5, "null"),
        ]
        decoded = protocol.decode_awareness_update(protocol.encode_awareness_update(entries))
        assert decoded == entries


class TestFrontmatterStripping:
    def test_editor_doc_excludes_frontmatter(self):
        from pycrdt import Doc, XmlFragment

        doc = Doc()
        frag = doc.get("default", type=XmlFragment)
        md_to_fragment("---\nproject: km\ntags: [a]\n---\n# 標題\n\n內文", frag)
        out = fragment_to_md(frag)
        assert "project" not in out and out.startswith("# 標題")
