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

class VectorApi {
  final Dio _dio = Dio(BaseOptions(
    baseUrl: Config.backendUrl,
    headers: {'x-api-key': Config.apiKey},
    connectTimeout: const Duration(seconds: 20),
    receiveTimeout: const Duration(minutes: 3),
    sendTimeout: const Duration(minutes: 2),
  ));

  Future<VectorResult> vectorize(
    File image, {
    required String preset,
    required int colors,
    required int detail,
    required String format,
    void Function(double progress)? onUploadProgress,
  }) async {
    final form = FormData.fromMap({
      'preset': preset,
      'colors': colors,
      'detail': detail,
      'format': format,
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
}
