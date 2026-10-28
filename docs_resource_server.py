"""Tiny MCP server that exposes the files in lab/docs/ as read-only MCP resources.

The reference filesystem and git servers only expose tools, so this server covers
the "Access MCP Resources" step of the lab.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

DOCS_DIR = Path(__file__).parent / "docs"

mcp = FastMCP("docs")


def _make_reader(path: Path):
    def read() -> str:
        return path.read_text(encoding="utf-8")

    return read


for doc in sorted(DOCS_DIR.glob("*.md")):
    mcp.resource(
        f"docs://{doc.name}",
        name=doc.stem,
        description=f"Lab source document {doc.name}",
        mime_type="text/markdown",
    )(_make_reader(doc))


if __name__ == "__main__":
    mcp.run(transport="stdio")
