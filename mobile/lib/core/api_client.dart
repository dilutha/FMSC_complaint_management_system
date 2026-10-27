import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../integration/auth_session.dart';

/// Error raised for any failed API call. Mirrors the backend envelope:
/// {"error": {"code", "message", "details"}}.
class ApiException implements Exception {
  ApiException({required this.statusCode, required this.code, required this.message, this.details = const {}});

  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;

  bool get isNetwork => statusCode == 0;
  bool get isUnauthorised => statusCode == 401;

  /// First error message for a form field, if the server reported one.
  String? fieldError(String field) {
    final value = details[field];
    if (value is List && value.isNotEmpty) return value.first.toString();
    if (value is String) return value;
    return null;
  }

  @override
  String toString() => 'ApiException($statusCode, $code): $message';
}

/// A file chosen by the user, ready to upload.
class UploadFile {
  UploadFile({required this.name, required this.bytes});
  final String name;
  final List<int> bytes;
  int get size => bytes.length;
}

class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.session,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 30),
  }) : _http = httpClient ?? http.Client();

  final String baseUrl;
  final AuthSession session;
  final Duration timeout;
  final http.Client _http;

  Uri uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse(baseUrl.endsWith('/') ? baseUrl : '$baseUrl/');
    final resolved = base.resolve(path.startsWith('/') ? path.substring(1) : path);
    return query == null || query.isEmpty ? resolved : resolved.replace(queryParameters: query);
  }

  Map<String, String> get _headers => {
    'Accept': 'application/json',
    if (session.token != null) 'Authorization': '${session.scheme} ${session.token}',
  };

  Future<dynamic> get(String path, {Map<String, String>? query}) =>
      _send(() => _http.get(uri(path, query), headers: _headers));

  /// GET an absolute URL (e.g. an attachment download_url) with auth headers.
  Future<List<int>> getBytes(String absoluteUrl) async {
    final response = await _guard(() => _http.get(Uri.parse(absoluteUrl), headers: _headers));
    _throwIfError(response);
    return response.bodyBytes;
  }

  Future<dynamic> post(String path, Map<String, dynamic> body) => _send(
    () => _http.post(uri(path), headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(body)),
  );

  Future<dynamic> patch(String path, Map<String, dynamic> body) => _send(
    () => _http.patch(uri(path), headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(body)),
  );

  /// Multipart POST. Repeated [fileField] parts carry the files.
  Future<dynamic> postMultipart(String path, Map<String, String> fields, String fileField, List<UploadFile> files) {
    return _send(() async {
      final request = http.MultipartRequest('POST', uri(path))
        ..headers.addAll(_headers)
        ..fields.addAll(fields);
      for (final f in files) {
        request.files.add(http.MultipartFile.fromBytes(fileField, f.bytes, filename: f.name));
      }
      return http.Response.fromStream(await _http.send(request));
    });
  }

  Future<dynamic> _send(Future<http.Response> Function() call) async {
    final response = await _guard(call);
    _throwIfError(response);
    if (response.statusCode == 204 || response.bodyBytes.isEmpty) return null;
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  Future<http.Response> _guard(Future<http.Response> Function() call) async {
    try {
      return await call().timeout(timeout);
    } on TimeoutException {
      throw ApiException(
        statusCode: 0,
        code: 'timeout',
        message: 'The server took too long to respond. Please try again.',
      );
    } on http.ClientException {
      // package:http wraps socket/DNS failures in ClientException on every platform.
      throw ApiException(
        statusCode: 0,
        code: 'network',
        message: 'No connection to the server. Check your internet and try again.',
      );
    }
  }

  void _throwIfError(http.Response response) {
    if (response.statusCode < 400) return;
    if (response.statusCode == 401) session.onUnauthorised();
    String code = 'http_${response.statusCode}';
    String message = _fallbackMessage(response.statusCode);
    Map<String, dynamic> details = const {};
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      final error = decoded is Map<String, dynamic> ? decoded['error'] : null;
      if (error is Map<String, dynamic>) {
        code = (error['code'] as String?) ?? code;
        message = (error['message'] as String?) ?? message;
        details = (error['details'] as Map?)?.cast<String, dynamic>() ?? const {};
      }
    } catch (_) {
      // Non-JSON error page: keep the safe fallback message.
    }
    throw ApiException(statusCode: response.statusCode, code: code, message: message, details: details);
  }

  static String _fallbackMessage(int status) => switch (status) {
    401 => 'Your session has expired. Please sign in again.',
    403 => 'You do not have permission to do that.',
    404 => 'This item could not be found.',
    409 => 'This action is no longer possible. Refresh and try again.',
    413 => 'The upload is too large.',
    429 => 'Too many requests. Please wait a moment and try again.',
    >= 500 => 'The server had a problem. Please try again later.',
    _ => 'The request could not be completed.',
  };
}
