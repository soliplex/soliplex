#!/bin/bash
set -e

echo "Generating Dart docs..."
cd src/flutter
dart doc .

echo "✅ Dart docs generated successfully in src/flutter/doc/api"

