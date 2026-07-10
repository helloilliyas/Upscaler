import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

class HistoryEntry {
  final String id;
  final DateTime date;
  final String preset;
  final String format;
  final String inputPath;
  final String outputPath;
  final int pathCount;
  final String? downloadsName; // null = Downloads copy failed/unavailable

  HistoryEntry({
    required this.id,
    required this.date,
    required this.preset,
    required this.format,
    required this.inputPath,
    required this.outputPath,
    required this.pathCount,
    this.downloadsName,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date.toIso8601String(),
        'preset': preset,
        'format': format,
        'inputPath': inputPath,
        'outputPath': outputPath,
        'pathCount': pathCount,
        'downloadsName': downloadsName,
      };

  static HistoryEntry fromJson(Map<String, dynamic> j) => HistoryEntry(
        id: j['id'],
        date: DateTime.parse(j['date']),
        preset: j['preset'],
        format: j['format'],
        inputPath: j['inputPath'],
        outputPath: j['outputPath'],
        pathCount: j['pathCount'] ?? 0,
        downloadsName: j['downloadsName'],
      );
}

class HistoryStore {
  static const _downloadsChannel = MethodChannel('vectorizer/downloads');

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

    // Also drop a visible copy into the phone's Downloads folder via the
    // native MediaStore channel. Best-effort: a failure must not fail the
    // conversion, but it is recorded so the UI never claims a save that
    // didn't happen.
    String? downloadsName;
    try {
      final name = 'vectorizer_$id.$format';
      await _downloadsChannel.invokeMethod('save', {
        'name': name,
        'mime': switch (format) {
          'pdf' => 'application/pdf',
          'png' => 'image/png',
          _ => 'image/svg+xml',
        },
        'bytes': output,
      });
      downloadsName = name;
    } catch (_) {}

    final entry = HistoryEntry(
      id: id,
      date: DateTime.now(),
      preset: preset,
      format: format,
      inputPath: inputCopy.path,
      outputPath: outFile.path,
      pathCount: pathCount,
      downloadsName: downloadsName,
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
