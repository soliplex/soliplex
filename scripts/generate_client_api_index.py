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
            # Check if library has overview.md or similar
            lib_path = os.path.join(base_dir, lib)
            if os.path.exists(os.path.join(lib_path, "overview.md")):
                f.write(f"- [{lib}]({lib}/overview.md)\n")
            else:
                # If overview.md doesn't exist, link to the directory itself
                f.write(f"- [{lib}]({lib}/)\n")

    print(f"Generated {index_file}")

if __name__ == "__main__":
    generate_index()