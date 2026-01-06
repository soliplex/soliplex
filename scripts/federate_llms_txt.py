import os
import re

def on_post_build(config, **kwargs):
    """
    Hook called by MkDocs after build.
    """
    site_dir = config['site_dir']
    
    mode = os.environ.get('DOCS_MODE')
    
    if mode == 'local':
        # Use absolute filesystem paths (Best for local agents)
        # config['site_dir'] provides the absolute path to the build output
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

def categorize_path(path):
    """
    Maps a directory path to a semantic category.
    Modify this function to curate the Client API map structure.
    """
    # 1. High-priority explicit mappings
    if "agui_events" in path: return "AG-UI Protocol"
    if "widget_registry" in path: return "Core Architecture"
    
    # 2. Keyword heuristics
    if "service" in path or "notifier" in path or "manager" in path:
        return "Services & State"
    if "model" in path or "entity" in path or "types" in path:
        return "Models & Data"
    if "network" in path or "transport" in path or "client" in path or "api" in path:
        return "Network & API"
    if "widget" in path or "screen" in path or "dialog" in path or "view" in path or "layout" in path or "card" in path or "chip" in path or "drawer" in path:
        return "UI Components"
    if "auth" in path or "oidc" in path:
        return "Authentication"
        
    # 3. Default fallback
    return "Utilities & Misc"

def restructure_client_map(content):
    """
    Parses the flat list of Client API links, filters tests, and categorizes them semantically.
    """
    lines = content.splitlines()
    categories = {}
    other_lines = []

    # Regex to extract directory from URL
    # Matches: .../reference/client_api/{directory}/{class}/...
    url_pattern = re.compile(r"\(.*?/reference/client_api/([^/]+)/")

    for line in lines:
        if line.strip().startswith("- ["):
            # Check for noise first
            if "Method:" in line or "Property:" in line or "Constructor:" in line or "Operator:" in line or "Static Method:" in line:
                continue
            
            # EXCLUDE TESTS
            if "_test" in line or "test/" in line or "Test" in line:
                continue
            
            # Simplify link text: "Overview for ClassName" -> "ClassName"
            line = line.replace("Overview for ", "")

            match = url_pattern.search(line)
            if match:
                directory = match.group(1)
                
                # Apply Semantic Categorization
                category = categorize_path(directory)
                
                if category not in categories:
                    categories[category] = []
                categories[category].append(line)
            else:
                other_lines.append(line)
        else:
            other_lines.append(line)

    # Build new content
    output = []
    
    # Add non-categorized lines first (like the header and index link)
    for line in other_lines:
        if line.strip() == "": continue
        output.append(line)
    
    output.append("") 

    # Define Sort Order for Categories
    sort_order = [
        "Core Architecture",
        "AG-UI Protocol",
        "Services & State",
        "Models & Data",
        "Network & API",
        "Authentication",
        "UI Components",
        "Utilities & Misc"
    ]
    
    # Add categorized sections in specific order
    for category in sort_order:
        if category in categories and categories[category]:
            output.append(f"## {category}")
            output.extend(sorted(categories[category]))
            output.append("")
            
    # Add any remaining categories that weren't in the sort list (fallback)
    for category in sorted(categories.keys()):
        if category not in sort_order:
            output.append(f"## {category}")
            output.extend(sorted(categories[category]))
            output.append("")

    return "\n".join(output)

def clean_map_content(content, section_name):
    """
    Filters out noisy lines from the map content.
    For Client API, it applies structural grouping.
    """
    if section_name == "Client API Reference":
        return restructure_client_map(content)

    lines = content.splitlines()
    filtered_lines = []
    for line in lines:
        # Check if line is a list item
        if line.strip().startswith("- ["):
            # Filter out granular API details
            if "Method:" in line or "Property:" in line or "Constructor:" in line or "Operator:" in line or "Static Method:" in line:
                continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)

def split_file(source_path, sections, suffix=""):
    """
    Splits a source file into multiple files based on section headers.
    """
    if not os.path.exists(source_path):
        print(f"File not found: {source_path}")
        return []

    with open(source_path, "r") as f:
        content = f.read()

    found_files = []
    site_dir = os.path.dirname(source_path)

    for section_name, filename_base in sections.items():
        # The output filename depends on whether we are splitting the map or the full content
        filename = f"{filename_base}{suffix}"
        
        # Pattern: look for the header (allowing # or ##) and capture until the next header or EOF
        # We need to match the specific section name provided
        # Escape the section name but allow for variable whitespace
        header_pattern = r"(^|\n)#+ " + re.escape(section_name)
        
        # Find start of this section
        start_match = re.search(header_pattern, content)
        if not start_match:
            print(f"Warning: Section '{section_name}' not found in {source_path}")
            continue
            
        start_index = start_match.end()
        
        # Find the start of the NEXT section (excluding the current one to prevent early stopping)
        other_sections = [s for s in sections.keys() if s != section_name]
        
        if other_sections:
            next_section_pattern = r"\n#+ (" + "|".join([re.escape(s) for s in other_sections]) + ")"
            
            # We need to search *from* the start_index
            remaining_content = content[start_index:]
            end_match = re.search(next_section_pattern, remaining_content)
            
            if end_match:
                section_content = remaining_content[:end_match.start()].strip()
            else:
                section_content = remaining_content.strip()
        else:
            # If no other sections, just take everything
            section_content = content[start_index:].strip()

        # Clean up map content if this is a map (empty suffix)
        if suffix == "":
            section_content = clean_map_content(section_content, section_name)

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
    if not site_url.endswith('/'):
        site_url += '/'
    
    # Define sections we want to extract and their base filenames
    # These must match section names in mkdocs.yml llmstxt plugin config
    sections = {
        "Getting Started": "llms-getting-started.txt",
        "Reference": "llms-server.txt",
        "Client API Reference": "llms-client.txt"
    }

    # Pass 1: Split the Map (llms.txt) -> llms-domain.txt
    print("--- Splitting Map ---")
    domain_maps = split_file(map_file, sections, suffix="")

    # Pass 2: Split the Content (llms-full.txt) -> llms-domain-full.txt
    print("--- Splitting Content ---")
    
    full_sections = {
        name: base.replace(".txt", "-full.txt") 
        for name, base in sections.items()
    }
    split_file(full_file, full_sections, suffix="")

    # Finalize: Rewrite root llms.txt to point to the Domain Maps
    if domain_maps:
        with open(map_file, "w") as f:
            f.write("# Soliplex - AI Discovery Map\n\n")
            f.write("This file points to domain-specific documentation maps. Select a domain to see available topics.\n\n")
            f.write("## Domains\n\n")
            for name, filename in domain_maps:
                # Link to the Map file using absolute URL
                f.write(f"- [{name}]({site_url}{filename})\n")
        print(f"Updated root discovery map at {map_file}")

if __name__ == "__main__":
    # For testing manually
    federate("site", "https://soliplex.github.io/soliplex/")
