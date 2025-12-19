import os
import re

def on_post_build(config, **kwargs):
    """
    Hook called by MkDocs after build.
    """
    site_dir = config['site_dir']
    federate(site_dir)

def federate(site_dir):
    full_file = os.path.join(site_dir, "llms-full.txt")
    
    if not os.path.exists(full_file):
        print(f"File not found: {full_file}")
        return

    with open(full_file, "r") as f:
        content = f.read()

    # The mkdocs-llmstxt plugin uses "# Section Name" for our configured sections
    # based on my previous read_file output.
    
    # Define sections we want to extract
    sections = {
        "Project Documentation": "llms-project.txt",
        "Server API Reference": "llms-server.txt",
        "Client API Reference": "llms-client.txt"
    }

    # Regex to find sections. We look for "# Section Name" and capture everything 
    # until the next "# Section Name" or end of file.
    
    # First, let's get the intro (everything before the first matched section)
    intro_match = re.search(r"^(.*?)# (" + "|".join(sections.keys()) + ")", content, re.DOTALL)
    intro = intro_match.group(1) if intro_match else "# Soliplex\n\n"

    found_files = []

    for section_name, filename in sections.items():
        # Pattern: look for the header and capture until the next header or EOF
        pattern = r"# " + re.escape(section_name) + r"\n+(.*?)(?=\n# (?:Project Documentation|Server API Reference|Client API Reference)|$)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            section_content = match.group(1).strip()
            dest_path = os.path.join(site_dir, filename)
            with open(dest_path, "w") as f:
                f.write(f"# Soliplex - {section_name}\n\n")
                f.write(section_content)
            print(f"Generated {dest_path}")
            found_files.append((section_name, filename))
        else:
            print(f"Warning: Section '{section_name}' not found in {full_file}")

    # Generate a new discovery llms.txt at the root
    root_llms_path = os.path.join(site_dir, "llms.txt")
    with open(root_llms_path, "w") as f:
        f.write("# Soliplex - AI Discovery Map\n\n")
        f.write("This file points to domain-specific documentation optimized for LLMs.\n\n")
        f.write("## Domains\n\n")
        for name, filename in found_files:
            f.write(f"- [{name}](/{filename}): Full context for {name.lower()}.\n")
    
    print(f"Generated discovery map at {root_llms_path}")

if __name__ == "__main__":
    federate()
