import os
import sys

# Add scripts directory to path to import llms_constants
sys.path.append(os.path.dirname(__file__))
try:
    from llms_constants import CLIENT_CATEGORY_ORDER
    from llms_constants import CLIENT_PATH_KEYWORDS
    from llms_constants import DEFAULT_CATEGORY
    from llms_constants import TEST_PATTERNS
except ImportError:
    # Fallback if run from a context where relative import fails
    CLIENT_CATEGORY_ORDER = [
        "Core Architecture",
        "AG-UI Protocol",
        "Services & State",
        "Models & Data",
        "Network & API",
        "Authentication",
        "UI Components",
        "Utilities & Misc",
    ]
    CLIENT_PATH_KEYWORDS = {}
    DEFAULT_CATEGORY = "Utilities & Misc"
    TEST_PATTERNS = ["_test", "test/", "Test"]


def categorize_path(path):
    """
    Maps a directory path to a semantic category.
    """
    for keyword, category in CLIENT_PATH_KEYWORDS.items():
        if keyword in path:
            return category
    return DEFAULT_CATEGORY


def generate_index():
    base_dir = "docs/reference/client_api"
    index_file = os.path.join(base_dir, "index.md")

    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return

    libraries = []
    for item in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, item)) and not item.startswith(
            "."
        ):
            # Exclude test files
            if any(test in item for test in TEST_PATTERNS):
                continue
            libraries.append(item)

    libraries.sort()

    # Bucketize libraries by category
    categories = {cat: [] for cat in CLIENT_CATEGORY_ORDER}
    if DEFAULT_CATEGORY not in categories:
        categories[DEFAULT_CATEGORY] = []

    for lib in libraries:
        cat = categorize_path(lib)
        if cat not in categories:
            cat = DEFAULT_CATEGORY

        lib_path = os.path.join(base_dir, lib)

        # Find the first subdirectory (ClassName)
        found_overview = False
        for item in os.listdir(lib_path):
            sub_path = os.path.join(lib_path, item)
            if os.path.isdir(sub_path):
                overview_path = os.path.join(sub_path, "overview.md")
                if os.path.exists(overview_path):
                    categories[cat].append(
                        f"- [{lib}]({lib}/{item}/overview.md)"
                    )
                    found_overview = True
                    break

        if not found_overview:
            if os.path.exists(os.path.join(lib_path, "overview.md")):
                categories[cat].append(f"- [{lib}]({lib}/overview.md)")
            else:
                categories[cat].append(f"- {lib} (No overview found)")

    # Write Structured Markdown for Website (index.md)
    with open(index_file, "w") as f:
        f.write("# Client API Reference\n\n")
        f.write(
            "Navigate to modules below. "
            "For full docs, see `llms-client-full.txt`.\n\n"
        )

        for cat in CLIENT_CATEGORY_ORDER:
            if categories[cat]:
                f.write(f"## {cat}\n")
                for entry in sorted(categories[cat]):
                    f.write(f"{entry}\n")
                f.write("\n")

        # Catch any categories not in the sorted order
        for cat in sorted(categories.keys()):
            if cat not in CLIENT_CATEGORY_ORDER and categories[cat]:
                f.write(f"## {cat}\n")
                for entry in sorted(categories[cat]):
                    f.write(f"{entry}\n")
                f.write("\n")

    print(f"Generated {index_file}")

    # Write Map File for LLMs (llms-client-map.txt)
    # This avoids parsing markdown later. We generate the exact map we want.
    map_file = os.path.join(base_dir, "llms-client-map.txt")
    with open(map_file, "w") as f:
        # No H1 header - it's added by federate script or template.
        # Content only; federator might overwrite.
        f.write(
            "Navigate to modules below. "
            "For full docs, see `llms-client-full.txt`.\n\n"
        )

        for cat in CLIENT_CATEGORY_ORDER:
            if categories[cat]:
                f.write(f"## {cat}\n")
                for entry in sorted(categories[cat]):
                    # Keep links consistent with index.md; federator localizes.
                    f.write(f"{entry}\n")
                f.write("\n")

        for cat in sorted(categories.keys()):
            if cat not in CLIENT_CATEGORY_ORDER and categories[cat]:
                f.write(f"## {cat}\n")
                for entry in sorted(categories[cat]):
                    f.write(f"{entry}\n")
                f.write("\n")

    print(f"Generated {map_file}")


if __name__ == "__main__":
    generate_index()
