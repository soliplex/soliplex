import os
import re

# All section names from mkdocs.yml llmstxt config
# (used for boundary detection when extracting sections)
ALL_SECTIONS = [
    "Getting Started",
    "User Guide",
    "Admin Guide - Configuration",
    "Admin Guide - Authentication",
    "Admin Guide - Deployment",
    "Developer Guide - Architecture",
    "Developer Guide - Agents",
    "Developer Guide - RAG",
    "Developer Guide - MCP",
    "Developer Guide - API",
    "Developer Guide - Flutter",
    "Reference",
    "Troubleshooting",
    "Contributing"
]

# Map output filename -> (display_name, [source_section_names])
SECTION_GROUPS = {
    "llms-getting-started.txt": ("Getting Started", ["Getting Started"]),
    "llms-user-guide.txt": ("User Guide", ["User Guide"]),
    "llms-admin-guide.txt": ("Admin Guide", [
        "Admin Guide - Configuration",
        "Admin Guide - Authentication",
        "Admin Guide - Deployment"
    ]),
    "llms-developer-guide.txt": ("Developer Guide", [
        "Developer Guide - Architecture",
        "Developer Guide - Agents",
        "Developer Guide - RAG",
        "Developer Guide - MCP",
        "Developer Guide - API",
        "Developer Guide - Flutter"
    ]),
    "llms-reference.txt": ("Reference", ["Reference"]),
    "llms-extras.txt": (
        "Troubleshooting & Contributing",
        ["Troubleshooting", "Contributing"]
    )
}


def on_post_build(config, **kwargs):
    """Hook called by MkDocs after build."""
    site_dir = config['site_dir']

    mode = os.environ.get('DOCS_MODE')

    if mode == 'local':
        # Use absolute filesystem paths (Best for local agents)
        site_url = config['site_dir']
        if not site_url.endswith('/'):
            site_url += '/'
        print(f"--- Federation: LOCAL MODE (Absolute Paths: {site_url}) ---")
    elif mode == 'relative':
        # Use relative paths (Portable)
        site_url = ""
        print("--- Federation: RELATIVE MODE (Relative Paths) ---")
    else:
        # Default: Use configured site_url (Remote/Hosted)
        site_url = config.get('site_url', '/')

    federate(site_dir, site_url)


def clean_map_content(content):
    """Filter out noisy lines from map content (e.g., API details)."""
    lines = content.splitlines()
    filtered_lines = []
    noisy_markers = ("Method:", "Property:", "Constructor:",
                     "Operator:", "Static Method:")
    for line in lines:
        if line.strip().startswith("- ["):
            # Filter out granular API details
            if any(marker in line for marker in noisy_markers):
                continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def extract_section(content, section_name):
    """
    Extract a single section's content from the full document.

    Returns content between this section's header and the next header.
    """
    # Pattern to find this section's header
    header_pattern = r"(^|\n)#+ " + re.escape(section_name)
    start_match = re.search(header_pattern, content)

    if not start_match:
        print(f"Warning: Section '{section_name}' not found")
        return None

    start_index = start_match.end()

    # Find the next section (any section from ALL_SECTIONS except current)
    other_sections = [s for s in ALL_SECTIONS if s != section_name]
    escaped_sections = [re.escape(s) for s in other_sections]
    next_section_pattern = r"\n#+ (" + "|".join(escaped_sections) + ")"

    remaining_content = content[start_index:]
    end_match = re.search(next_section_pattern, remaining_content)

    if end_match:
        return remaining_content[:end_match.start()].strip()
    else:
        return remaining_content.strip()


def split_file(source_path, is_map=False):
    """
    Split a source file into federated files based on SECTION_GROUPS.

    Args:
        source_path: Path to llms.txt or llms-full.txt
        is_map: True for llms.txt (map), False for llms-full.txt (content)

    Returns:
        List of (display_name, filename) tuples for generated files
    """
    if not os.path.exists(source_path):
        print(f"File not found: {source_path}")
        return []

    with open(source_path) as f:
        content = f.read()

    found_files = []
    site_dir = os.path.dirname(source_path)
    suffix = "" if is_map else "-full"

    for base_filename, (display_name, section_names) in SECTION_GROUPS.items():
        # Build output filename (add -full suffix for content files)
        if suffix:
            filename = base_filename.replace(".txt", f"{suffix}.txt")
        else:
            filename = base_filename

        # Extract content for all sections in this group
        combined_content = []
        for section_name in section_names:
            section_content = extract_section(content, section_name)
            if section_content:
                # Add section header for multi-section groups
                if len(section_names) > 1:
                    combined_content.append(f"## {section_name}\n")
                combined_content.append(section_content)
                combined_content.append("")  # blank line between sections

        if not combined_content:
            print(f"Warning: No content found for {filename}")
            continue

        final_content = "\n".join(combined_content).strip()

        # Clean up map content (filter noisy API details)
        if is_map:
            final_content = clean_map_content(final_content)

        # Write the federated file
        dest_path = os.path.join(site_dir, filename)
        with open(dest_path, "w") as f:
            f.write(f"# Soliplex - {display_name}\n\n")
            f.write(final_content)

        print(f"Generated {dest_path}")
        found_files.append((display_name, filename))

    return found_files


def federate(site_dir, site_url):
    """Split llms.txt and llms-full.txt into domain-specific files."""
    map_file = os.path.join(site_dir, "llms.txt")
    full_file = os.path.join(site_dir, "llms-full.txt")

    # Ensure site_url ends with / to safely append filenames
    if not site_url.endswith('/'):
        site_url += '/'

    # Pass 1: Split the Map (llms.txt) -> llms-{domain}.txt
    print("--- Splitting Map ---")
    domain_maps = split_file(map_file, is_map=True)

    # Pass 2: Split the Content (llms-full.txt) -> llms-{domain}-full.txt
    print("--- Splitting Content ---")
    split_file(full_file, is_map=False)

    # Finalize: Rewrite root llms.txt to point to the Domain Maps
    if domain_maps:
        with open(map_file, "w") as f:
            f.write("# Soliplex - AI Discovery Map\n\n")
            f.write(
                "This file points to domain-specific documentation maps. "
                "Select a domain to see available topics.\n\n"
            )
            f.write("## Domains\n\n")
            for display_name, filename in domain_maps:
                f.write(f"- [{display_name}]({site_url}{filename})\n")
        print(f"Updated root discovery map at {map_file}")


if __name__ == "__main__":
    # For testing manually
    federate("site", "https://soliplex.github.io/soliplex/")
