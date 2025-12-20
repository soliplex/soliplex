import os
import re

from llms_constants import DEFAULT_CATEGORY
from llms_constants import MAP_NOISE_PATTERNS
from llms_constants import PATTERNS
from llms_constants import SECTIONS
from llms_constants import SERVER_CATEGORY_ORDER
from llms_constants import SERVER_SOURCE_CATEGORIES


def on_post_build(config, **kwargs):
    """
    Hook called by MkDocs after build.

    DOCS_MODE controls URL format in generated llms*.txt files:
      - absolute: Filesystem paths (/Users/you/project/site/...)
      - local: Localhost URLs (http://localhost:PORT/...)
      - relative: Relative paths (llms-client.txt)
      - remote (default): Hosted URLs from mkdocs.yml site_url

    LOCAL_PORT controls the port for 'local' mode (default: 8000).
    """
    site_dir = config["site_dir"]

    mode = os.environ.get("DOCS_MODE")

    if mode == "absolute":
        # Use absolute filesystem paths (Best for local agents with file access)
        site_url = config["site_dir"]
        if not site_url.endswith("/"):
            site_url += "/"
        print(f"--- Federation: ABSOLUTE MODE (Filesystem Paths: {site_url}) ---")
    elif mode == "local":
        # Use localhost URLs (Best for local dev server)
        port = os.environ.get("LOCAL_PORT", "8000")
        site_url = f"http://localhost:{port}/"
        print(f"--- Federation: LOCAL MODE (Localhost: {site_url}) ---")
    elif mode == "relative":
        # Use relative paths (Portable archives)
        site_url = ""
        print("--- Federation: RELATIVE MODE (Relative Paths) ---")
    else:
        # Default: Use configured site_url (Remote/Hosted)
        site_url = config.get("site_url", "/")

    federate(site_dir, site_url)


def categorize_server_item(name, source_file):
    """
    Categorizes server API items by their source file and name patterns.
    """
    if not source_file:
        return DEFAULT_CATEGORY

    # Check source file against category mappings
    for pattern, category in SERVER_SOURCE_CATEGORIES.items():
        if pattern in source_file:
            return category

    return DEFAULT_CATEGORY


def restructure_server_map(content):
    """
    Parses the server API content and creates a categorized map.
    Extracts class/function names and organizes by source module.
    """
    lines = content.splitlines()
    categories = {}
    current_item = None
    current_source = None

    # Patterns from constants
    item_pattern = re.compile(PATTERNS["item_header"])
    source_pattern = re.compile(PATTERNS["source_file"])

    items_with_sources = []

    for line in lines:
        # Check for new item header
        item_match = item_pattern.match(line)
        if item_match:
            # Save previous item if exists
            if current_item:
                items_with_sources.append((current_item, current_source))
            current_item = item_match.group(1).strip()
            current_source = None
            continue

        # Check for source file
        source_match = source_pattern.search(line)
        if source_match and current_item:
            current_source = source_match.group(1)

    # Don't forget the last item
    if current_item:
        items_with_sources.append((current_item, current_source))

    # Categorize items
    for item_name, source_file in items_with_sources:
        category = categorize_server_item(item_name, source_file)
        if category not in categories:
            categories[category] = []

        # Create a simple entry (no URL since server map doesn't have per-item URLs)
        categories[category].append(f"- `{item_name}`")

    # Build output (header is added by split_file, so start with intro)
    output = []
    output.append(
        "Navigate to specific modules below. For full documentation, see `llms-server-full.txt`."
    )
    output.append("")

    # Add categorized sections using defined sort order
    for category in SERVER_CATEGORY_ORDER:
        if category in categories and categories[category]:
            output.append(f"## {category}")
            output.extend(sorted(categories[category]))
            output.append("")

    # Add remaining categories not in the defined order
    for category in sorted(categories.keys()):
        if category not in SERVER_CATEGORY_ORDER and categories[category]:
            output.append(f"## {category}")
            output.extend(sorted(categories[category]))
            output.append("")

    return "\n".join(output)


def clean_map_content(content, section_name, site_dir=None, site_url=None):
    """
    Filters out noisy lines from the map content.
    For Server API, generates a categorized map from the full content.
    For Client API, reads the pre-generated structured map.
    """
    if section_name == "Client API Reference":
        # Read the pre-generated map file
        project_root = os.path.dirname(site_dir)
        map_path = os.path.join(project_root, "docs/reference/client_api/llms-client-map.txt")
        
        if os.path.exists(map_path):
            with open(map_path) as f:
                map_content = f.read()
            
            # Determine the base path for links
            is_remote = site_url and (site_url.startswith("http://") or site_url.startswith("https://"))
            is_relative = site_url == ""

            if is_remote:
                docs_api_base = f"{site_url}reference/client_api/"
            elif is_relative:
                docs_api_base = "reference/client_api/"
            else:
                # Local absolute path mode - link to source docs
                docs_api_base = os.path.join(project_root, "docs/reference/client_api/")

            def replace_link(match):
                text = match.group(1)
                rel_path = match.group(2)
                if rel_path.startswith("http://") or rel_path.startswith("https://") or rel_path.startswith("/"):
                    return f"[{text}]({rel_path})"
                
                if is_remote:
                    # Strip .md for clean URLs on live sites
                    clean_path = rel_path.replace(".md", "")
                    if clean_path.endswith("/index"):
                        clean_path = clean_path[:-6]
                    return f"[{text}]({docs_api_base}{clean_path})"
                elif is_relative:
                    return f"[{text}]({docs_api_base}{rel_path})"
                else:
                    full_path = os.path.join(docs_api_base, rel_path)
                    return f"[{text}]({full_path})"
            
            return re.sub(PATTERNS["markdown_link"], replace_link, map_content)

    if section_name == "Server API Reference" and site_dir:
        # Server map is sparse in llms.txt, so we generate from the full content
        full_file = os.path.join(site_dir, "llms-full.txt")
        if os.path.exists(full_file):
            with open(full_file) as f:
                full_content = f.read()
            # Extract server section from full content (skip code blocks)
            code_blocks = find_code_block_ranges(full_content)
            server_start = None
            for match in re.finditer(r"^# Server API\s*$", full_content, re.M):
                if not is_inside_code_block(match.start(), code_blocks):
                    server_start = match.start()
                    break
            if server_start is not None:
                # Find end of server section (next major section or EOF)
                next_sections = ["# Client API", "# Project Documentation"]
                server_end = len(full_content)
                for next_section in next_sections:
                    pos = full_content.find(next_section, server_start + 1)
                    if pos != -1 and pos < server_end:
                        server_end = pos
                server_content = full_content[server_start:server_end]
                return restructure_server_map(server_content)

    lines = content.splitlines()
    filtered_lines = []
    for line in lines:
        # Check if line is a list item
        if line.strip().startswith("- ["):
            # Filter out granular API details using noise patterns
            if any(noise in line for noise in MAP_NOISE_PATTERNS):
                continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def localize_urls(content, site_dir, site_url):
    """
    Replace remote URLs with local file paths when in local mode.
    """
    if not site_url.startswith("/"):
        # Remote URL mode - no changes needed
        return content

    # Local mode: replace remote URLs with local paths
    content = re.sub(PATTERNS["remote_url"], site_url, content)
    return content


def find_code_block_ranges(content):
    """
    Find all code block ranges in markdown content.

    Returns list of (start, end) tuples for each code block.
    Handles both fenced (```) and indented code blocks.
    """
    ranges = []
    # Match fenced code blocks: ```...```
    for match in re.finditer(r"```[^\n]*\n.*?```", content, re.DOTALL):
        ranges.append((match.start(), match.end()))
    return ranges


def is_inside_code_block(position, code_block_ranges):
    """Check if a position is inside any code block."""
    for start, end in code_block_ranges:
        if start <= position < end:
            return True
    return False


def find_section_header(content, section_name, code_block_ranges):
    """
    Find a section header that is NOT inside a code block.

    Returns the match object or None if not found.
    """
    header_pattern = r"(^|\n)#+ " + re.escape(section_name)
    for match in re.finditer(header_pattern, content):
        if not is_inside_code_block(match.start(), code_block_ranges):
            return match
    return None


def split_file(source_path, sections, is_map=True, site_url=None):
    """
    Splits a source file into multiple files based on section headers.

    Args:
        source_path: Path to the source file
        sections: Dict mapping section names to output filenames
        is_map: If True, apply map restructuring (filtering, categorization)
        site_url: URL prefix for local mode URL replacement
    """
    if not os.path.exists(source_path):
        print(f"File not found: {source_path}")
        return []

    with open(source_path) as f:
        content = f.read()

    found_files = []
    site_dir = os.path.dirname(source_path)

    # Pre-compute code block ranges to avoid matching headers inside code blocks
    code_block_ranges = find_code_block_ranges(content)

    for section_name, filename_base in sections.items():
        # The output filename comes directly from the sections dict
        filename = filename_base

        # Find start of this section (skipping headers inside code blocks)
        start_match = find_section_header(
            content, section_name, code_block_ranges
        )
        if not start_match:
            print(
                f"Warning: Section '{section_name}' not found in {source_path}"
            )
            continue

        start_index = start_match.end()

        # Find the start of the NEXT section (excluding the current one to prevent early stopping)
        other_sections = [s for s in sections.keys() if s != section_name]

        if other_sections:
            next_section_pattern = (
                r"\n#+ ("
                + "|".join([re.escape(s) for s in other_sections])
                + ")"
            )

            # We need to search *from* the start_index
            remaining_content = content[start_index:]
            end_match = re.search(next_section_pattern, remaining_content)

            if end_match:
                section_content = remaining_content[
                    : end_match.start()
                ].strip()
            else:
                section_content = remaining_content.strip()
        else:
            # If no other sections, just take everything
            section_content = content[start_index:].strip()

        # Clean up map content if this is a map pass
        if is_map:
            section_content = clean_map_content(
                section_content, section_name, site_dir, site_url
            )
        
        if site_url:
            # Localize URLs if in local mode (or if site_url is set)
            section_content = localize_urls(
                section_content, site_dir, site_url
            )

        dest_path = os.path.join(site_dir, filename)
        with open(dest_path, "w") as f:
            f.write(f"# Soliplex - {section_name}\n\n")
            f.write(section_content)
        print(f"Generated {dest_path}")
        found_files.append((section_name, filename))

    return found_files


def federate(site_dir, site_url):
    map_file = os.path.join(site_dir, "llms.txt")
    full_file = os.path.join(site_dir, "llms-full.txt")

    # Ensure site_url ends with / to safely append filenames
    if not site_url.endswith("/"):
        site_url += "/"

    # Pass 1: Split the Map (llms.txt) -> llms-domain.txt
    print("--- Splitting Map ---")
    # Pass site_url so that maps can be localized (e.g. Client API map)
    domain_maps = split_file(map_file, SECTIONS, is_map=True, site_url=site_url)

    # Pass 2: Split the Content (llms-full.txt) -> llms-domain-full.txt
    # Use is_map=False to skip map restructuring, pass site_url for URL localization
    print("--- Splitting Content ---")

    full_sections = {
        name: base.replace(".txt", "-full.txt")
        for name, base in SECTIONS.items()
    }
    split_file(full_file, full_sections, is_map=False, site_url=site_url)

    # Finalize: Rewrite root llms.txt to point to the Domain Maps
    if domain_maps:
        with open(map_file, "w") as f:
            f.write("# Soliplex - AI Discovery Map\n\n")
            f.write(
                "This file points to domain-specific documentation maps. Select a domain to see available topics.\n\n"
            )
            f.write("## Domains\n\n")
            for name, filename in domain_maps:
                # Link to the Map file using absolute URL
                f.write(f"- [{name}]({site_url}{filename})\n")
        print(f"Updated root discovery map at {map_file}")


if __name__ == "__main__":
    # For testing manually
    federate("site", "https://soliplex.github.io/soliplex/")
