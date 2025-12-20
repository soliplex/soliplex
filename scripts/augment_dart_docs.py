import os


def get_markdown_files(directory):
    """Return sorted list of .md files in directory."""
    if not os.path.exists(directory):
        return []
    files = [f for f in os.listdir(directory) if f.endswith(".md")]
    return sorted(files)


def augment_overview(overview_path, root_dir):
    """
    Checks for sibling directories (methods, properties) and appends links
    to overview.md if they exist.
    """
    with open(overview_path) as f:
        content = f.read()

    # Avoid duplicate augmentation
    if "## API Index" in content or "## Methods" in content:
        # Simple check: if we see our header, assume done.
        # But wait, what if new methods were added?
        # For simplicity in this build step, assume clean build or overwrite.
        # Ideally, we should strip the old section and rebuild.
        # Given we generated the docs fresh in build_docs.sh (rm -rf),
        # checking for existence is fine to prevent double-run in dev.
        # But actually, let's just append for now.
        pass

    append_lines = []

    # Check for methods
    methods_dir = os.path.join(root_dir, "methods")
    if os.path.exists(methods_dir):
        files = get_markdown_files(methods_dir)
        if files:
            append_lines.append("\n## Methods\n")
            for f in files:
                name = f.replace(".md", "")
                append_lines.append(f"- [{name}](methods/{f})")

    # Check for properties
    props_dir = os.path.join(root_dir, "properties")
    if os.path.exists(props_dir):
        files = get_markdown_files(props_dir)
        if files:
            append_lines.append("\n## Properties\n")
            for f in files:
                name = f.replace(".md", "")
                append_lines.append(f"- [{name}](properties/{f})")

    # Check for constructors
    ctors_dir = os.path.join(root_dir, "constructors")
    if os.path.exists(ctors_dir):
        files = get_markdown_files(ctors_dir)
        if files:
            append_lines.append("\n## Constructors\n")
            for f in files:
                name = f.replace(".md", "")
                append_lines.append(f"- [{name}](constructors/{f})")

    if append_lines:
        # Only write if we have something to add
        # And check idempotency for specific sections
        new_text = "\n".join(append_lines)

        # Super simple idempotency: check if the exact block exists
        # This is brittle but good enough for a generated artifact context
        if new_text.strip() not in content:
            with open(overview_path, "a") as f:
                f.write(new_text)
                f.write("\n")


def augment_docs(base_dir):
    """Recursively find overview.md files and augment them."""
    for root, _dirs, files in os.walk(base_dir):
        if "overview.md" in files:
            augment_overview(os.path.join(root, "overview.md"), root)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        # Default to the known location
        target_dir = "docs/reference/client_api"

    print(f"Augmenting Dart docs in {target_dir}...")
    augment_docs(target_dir)
    print("Done.")
