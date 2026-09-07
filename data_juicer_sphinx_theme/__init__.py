"""Data-Juicer Sphinx Theme - A modern documentation theme."""

import json
from pathlib import Path

from docutils import nodes
from sphinx import addnodes
from sphinx.environment.adapters.toctree import TocTree

__version__ = "1.0.0"


def get_html_theme_path():
    return str(Path(__file__).parent)


def _update_context(app, pagename, templatename, context, doctree):
    """Add nav_links to template context."""
    nav_links_raw = app.config.html_theme_options.get("nav_links", [])
    if isinstance(nav_links_raw, str):
        try:
            nav_links_raw = json.loads(nav_links_raw) if nav_links_raw else []
        except (json.JSONDecodeError, TypeError):
            nav_links_raw = []
    context["theme_nav_links"] = nav_links_raw
    _section_context(app, pagename, context)


def _descendants(env, root):
    """Follow document relationships, including generated and nested API pages."""
    seen = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending.extend(env.toctree_includes.get(name, ()))
    return seen


def _section_context(app, pagename, context):
    env = app.env
    options = app.config.html_theme_options
    api_root = options.get("api_root", "api")
    if not api_root or api_root not in env.found_docs:
        context["theme_sections"] = []
        return

    api_pages = _descendants(env, api_root)
    is_api = pagename in api_pages
    root = app.config.root_doc
    legacy_root = "docs_index_ZH" if app.config.language == "zh_CN" else "docs_index"
    docs_root = legacy_root if legacy_root in _descendants(env, root) else root
    context["theme_sections"] = [
        {"name": "Doc", "doc": docs_root, "active": not is_api},
        {"name": "API", "doc": api_root, "active": is_api},
    ]
    context["theme_section_root"] = api_root if is_api else docs_root
    context["theme_section_label"] = "API" if is_api else (
        "文档" if app.config.language == "zh_CN" else "Documentation"
    )

    # Resolve copies of the selected section's trees, leaving Sphinx's global
    # graph intact for search, cross references and other builders.
    adapter = TocTree(env)
    excluded = {app.builder.get_relative_uri(pagename, name) for name in api_pages}
    # Previous/next navigation should not silently cross section boundaries.
    for direction in ("prev", "next"):
        link = context.get(direction)
        if link and (link["link"].split("#")[0] in excluded) != is_api:
            context[direction] = None
    fragments = []
    for tree in env.get_doctree(context["theme_section_root"]).findall(addnodes.toctree):
        resolved = adapter.resolve(
            pagename, app.builder, tree.deepcopy(), maxdepth=3,
            titles_only=True, collapse=False, includehidden=True,
        )
        if resolved is None:
            continue
        if not is_api:
            for item in list(resolved.findall(nodes.list_item)):
                ref = next(item.findall(nodes.reference), None)
                if ref is not None and ref.get("refuri", "").split("#")[0] in excluded:
                    item.parent.remove(item)
            # Drop empty nested lists and captions belonging to an API-only tree.
            for listing in reversed(list(resolved.findall(nodes.bullet_list))):
                if not listing.children:
                    listing.parent.remove(listing)
        if any(resolved.findall(nodes.reference)):
            fragments.append(app.builder.render_partial(resolved)["fragment"])
    context["theme_section_toctree"] = "".join(fragments)


def setup(app):
    app.add_html_theme("data_juicer_theme", str(Path(__file__).parent))
    app.connect("html-page-context", _update_context)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
