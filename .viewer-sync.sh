cd "$(dirname "$0")/viewer" && npm run build &&
  (cd ../loom && uv run python scripts/vendor_viewer.py ../viewer/build)
