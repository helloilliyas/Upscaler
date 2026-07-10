import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_saver/file_saver.dart';
import 'package:path_provider/path_provider.dart';

class HistoryEntry {
  final String id;
  final DateTime date;
  final String preset;
  final String format;
  final String inputPath;
  final String outputPath;
  final int pathCount;

  HistoryEntry({
    required this.id,
    required this.date,
    required this.preset,
    required this.format,
    required this.inputPath,
    required this.outputPath,
    required this.pathCount,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date.toIso8601String(),
        'preset': preset,
        'format': format,
        'inputPath': inputPath,
        'outputPath': outputPath,
        'pathCount': pathCount,
      };

  static HistoryEntry fromJson(Map<String, dynamic> j) => HistoryEntry(
        id: j['id'],
        date: DateTime.parse(j['date']),
        preset: j['preset'],
        format: j['format'],
        inputPath: j['inputPath'],
        outputPath: j['outputPath'],
        pathCount: j['pathCount'] ?? 0,
      );
}

class HistoryStore {
  static Future<Directory> _dir() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/vectorizer');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  static Future<File> _indexFile() async =>
      File('${(await _dir()).path}/history.json');

  static Future<List<HistoryEntry>> load() async {
    final f = await _indexFile();
    if (!await f.exists()) return [];
    try {
      final list = jsonDecode(await f.readAsString()) as List;
      final entries = list
          .map((e) => HistoryEntry.fromJson(e as Map<String, dynamic>))
          .where((e) => File(e.outputPath).existsSync())
          .toList();
      entries.sort((a, b) => b.date.compareTo(a.date));
      return entries;
    } catch (_) {
      return [];
    }
  }

  static Future<void> _save(List<HistoryEntry> entries) async {
    final f = await _indexFile();
    await f.writeAsString(jsonEncode(entries.map((e) => e.toJson()).toList()));
  }

  /// Copies the input image and writes the output bytes into app storage,
  /// then records the entry. Returns the created entry.
  static Future<HistoryEntry> add({
    required File input,
    required Uint8List output,
    required String preset,
    required String format,
    required int pathCount,
  }) async {
    final dir = await _dir();
    final id = DateTime.now().millisecondsSinceEpoch.toString();
    final inputCopy = File('${dir.path}/$id-input.jpg');
    await input.copy(inputCopy.path);
    final outFile = File('${dir.path}/$id.$format');
    await outFile.writeAsBytes(output);

    // Also drop a visible copy into the phone's Downloads folder.
    // Best-effort: a failure here must not fail the conversion.
    try {
      await FileSaver.instance.saveFile(
        name: 'vectorizer_$id',
        bytes: output,
        ext: format,
        mimeType: switch (format) {
          'pdf' => MimeType.pdf,
          'png' => MimeType.png,
          _ => MimeType.custom,
        },
        customMimeType: format == 'svg' ? 'image/svg+xml' : null,
      );
    } catch (_) {}

    final entry = HistoryEntry(
      id: id,
      date: DateTime.now(),
      preset: preset,
      format: format,
      inputPath: inputCopy.path,
      outputPath: outFile.path,
      pathCount: pathCount,
    );
    final entries = await load();
    entries.insert(0, entry);
    await _save(entries);
    return entry;
  }

  static Future<void> remove(HistoryEntry entry) async {
    final entries = await load();
    entries.removeWhere((e) => e.id == entry.id);
    await _save(entries);
    for (final p in [entry.inputPath, entry.outputPath]) {
      final f = File(p);
      if (await f.exists()) await f.delete();
    }
  }
}
