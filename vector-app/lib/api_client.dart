import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'config.dart';

class VectorResult {
  final String format; // svg | pdf | png
  final Uint8List bytes; // file contents (svg is utf8-encoded text)
  final int width;
  final int height;
  final int pathCount;
  final int durationMs;

  VectorResult({
    required this.format,
    required this.bytes,
    required this.width,
    required this.height,
    required this.pathCount,
    required this.durationMs,
  });

  String get svgText => utf8.decode(bytes);
}

class RefineResult {
  final Uint8List svgBytes;
  final int pathCount;
  final String? aiNotes;
  final int aiEditsApplied;
  final double scoreBaseline;
  final double scoreFinal;

  RefineResult({
    required this.svgBytes,
    required this.pathCount,
    required this.aiNotes,
    required this.aiEditsApplied,
    required this.scoreBaseline,
    required this.scoreFinal,
  });
}

class VectorApi {
  final Dio _dio = Dio(BaseOptions(
    baseUrl: Config.backendUrl,
    headers: {'x-api-key': Config.apiKey},
    connectTimeout: const Duration(seconds: 20),
    receiveTimeout: const Duration(minutes: 6),
    sendTimeout: const Duration(minutes: 2),
  ));

  Future<VectorResult> vectorize(
    File image, {
    required String preset,
    required int colors,
    required int detail,
    required String format,
    bool enhance = false,
    void Function(double progress)? onUploadProgress,
  }) async {
    final form = FormData.fromMap({
      'preset': preset,
      'colors': colors,
      'detail': detail,
      'format': format,
      'enhance': enhance ? 1 : 0,
      'file': await MultipartFile.fromFile(image.path,
          filename: image.uri.pathSegments.last),
    });

    final Response res;
    try {
      res = await _dio.post('/vectorize',
          data: form,
          onSendProgress: (sent, total) {
            if (total > 0) onUploadProgress?.call(sent / total);
          });
    } on DioException catch (e) {
      final detailMsg = e.response?.data is Map
          ? (e.response!.data['detail']?.toString() ?? e.message)
          : e.message;
      throw Exception('Conversion failed: $detailMsg');
    }

    final data = res.data as Map<String, dynamic>;
    final fmt = data['format'] as String;
    final bytes = fmt == 'svg'
        ? Uint8List.fromList(utf8.encode(data['svg'] as String))
        : base64Decode(data['data_base64'] as String);

    return VectorResult(
      format: fmt,
      bytes: bytes,
      width: data['width'] as int,
      height: data['height'] as int,
      pathCount: data['path_count'] as int,
      durationMs: data['duration_ms'] as int,
    );
  }

  Future<RefineResult> refine(
    File image, {
    required String preset,
    String? anthropicKey,
  }) async {
    final form = FormData.fromMap({
      'preset': preset,
      'colors': 0,
      'detail': 60,
      'anthropic_key': anthropicKey ?? '',
      'file': await MultipartFile.fromFile(image.path,
          filename: image.uri.pathSegments.last),
    });

    final Response res;
    try {
      res = await _dio.post('/refine', data: form);
    } on DioException catch (e) {
      final detailMsg = e.response?.data is Map
          ? (e.response!.data['detail']?.toString() ?? e.message)
          : e.message;
      throw Exception('Refine failed: $detailMsg');
    }

    final data = res.data as Map<String, dynamic>;
    return RefineResult(
      svgBytes: Uint8List.fromList(utf8.encode(data['svg'] as String)),
      pathCount: data['path_count'] as int,
      aiNotes: data['ai_notes'] as String?,
      aiEditsApplied: (data['ai_edits_applied'] ?? 0) as int,
      scoreBaseline: (data['score_baseline'] as num).toDouble(),
      scoreFinal: (data['score_final'] as num).toDouble(),
    );
  }
}
