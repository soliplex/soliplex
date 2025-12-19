import os

def generate_index():
    base_dir = "docs/reference/client_api"
    index_file = os.path.join(base_dir, "index.md")
    
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return

    libraries = []
    for item in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, item)) and not item.startswith("."):
            libraries.append(item)
    
    libraries.sort()    
    with open(index_file, "w") as f:
        f.write("# Client API Reference\n\n")
        f.write("## Libraries\n\n")
        for lib in libraries:
            lib_path = os.path.join(base_dir, lib)
            
            # Find the first subdirectory (ClassName)
            found_overview = False
            for item in os.listdir(lib_path):
                sub_path = os.path.join(lib_path, item)
                if os.path.isdir(sub_path):
                    overview_path = os.path.join(sub_path, "overview.md")
                    if os.path.exists(overview_path):
                        f.write(f"- [{lib}]({lib}/{item}/overview.md)\n")
                        found_overview = True
                        break
            
            if not found_overview:
                # Fallback: check if overview.md exists at root (unlikely given discovery) or just list it
                if os.path.exists(os.path.join(lib_path, "overview.md")):
                     f.write(f"- [{lib}]({lib}/overview.md)\n")
                else:
                     f.write(f"- {lib} (No overview found)\n")

    print(f"Generated {index_file}")

if __name__ == "__main__":
    generate_index()