
String appendUrl(String base, String path) {
  // Check if the base URL ends with a slash
  final bool baseEndsWithSlash = base.endsWith('/');

  // Check if the path starts with a slash
  final bool pathStartsWithSlash = path.startsWith('/');

  if (baseEndsWithSlash && pathStartsWithSlash) {
    // If both have slashes, remove one from the path
    return base + path.substring(1);
  } else if ((baseEndsWithSlash && !pathStartsWithSlash) ||
      (!baseEndsWithSlash && pathStartsWithSlash)) {
    // If one has a slash and the other doesn't, just join them
    return base + path;
  } else {
    // if (!baseEndsWithSlash && !pathStartsWithSlash)
    // If neither has a slash, add one in between
    return '$base/$path';
  }
}