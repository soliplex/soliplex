import 'dart:collection';

/// A simple LRU (Least Recently Used) cache implementation.
///
/// Used for caching frequently accessed data to improve performance.
class LruCache<K, V> {
  LruCache({this.maxSize = 100});
  final int maxSize;
  final LinkedHashMap<K, V> _cache = LinkedHashMap<K, V>();

  // Metrics
  int _hits = 0;
  int _misses = 0;

  /// Get a value from the cache.
  /// Returns null if not found.
  V? get(K key) {
    final value = _cache.remove(key);
    if (value != null) {
      // Move to end (most recently used)
      _cache[key] = value;
      _hits++;
      return value;
    }
    _misses++;
    return null;
  }

  /// Put a value in the cache.
  void put(K key, V value) {
    // Remove if exists (to update position)
    _cache.remove(key);

    // Evict oldest if at capacity
    while (_cache.length >= maxSize) {
      _cache.remove(_cache.keys.first);
    }

    _cache[key] = value;
  }

  /// Check if a key exists in the cache.
  bool containsKey(K key) {
    return _cache.containsKey(key);
  }

  /// Remove a key from the cache.
  V? remove(K key) {
    return _cache.remove(key);
  }

  /// Clear the entire cache.
  void clear() {
    _cache.clear();
    _hits = 0;
    _misses = 0;
  }

  /// Current number of items in cache.
  int get length => _cache.length;

  /// Cache hit count.
  int get hits => _hits;

  /// Cache miss count.
  int get misses => _misses;

  /// Cache hit ratio.
  double get hitRatio {
    final total = _hits + _misses;
    if (total == 0) return 0;
    return _hits / total;
  }

  /// Get all keys in cache (oldest to newest).
  Iterable<K> get keys => _cache.keys;

  /// Get all values in cache (oldest to newest).
  Iterable<V> get values => _cache.values;
}

/// Extension for typed library caching.
extension LibraryCacheExtension on LruCache<String, dynamic> {
  /// Get cache metrics as a map.
  Map<String, dynamic> get metrics => {
    'size': length,
    'maxSize': maxSize,
    'hits': hits,
    'misses': misses,
    'hitRatio': hitRatio,
  };
}
