extension InterleavedListExtension<T> on List<T> {
  List<T> interleave(T infill, {bool trailing = false}) {
    if (isEmpty) {
      return [];
    }
    return List.generate(
      trailing ? (length + length) : (length + length - 1),
      (index) => index.isEven ? this[index ~/ 2] : infill,
    );
  }
}
