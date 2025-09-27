#!/usr/bin/env python3
#
#   Convert a generated 'pylock.toml' file to a 'requirements.txt'
#   compatible file on stdout, skipping editable packages.
#
import pathlib
import tomllib

def main():
    locked_toml = pathlib.Path("pylock.toml").read_text()
    locked = tomllib.loads(locked_toml)

    for package in locked["packages"]:

        # Skip development packages
        if package.get("version") is not None:
            print(f"{package['name']}=={package['version']}")


if __name__ == "__main__":
    main()
