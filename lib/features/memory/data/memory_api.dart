import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/memory/data/memory_models.dart';

final memoryApiProvider = Provider<MemoryApi>((ref) => MemoryApi());

class MemoryApi {
  MemoryApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = (baseUrl ?? AppConfig.backendBaseUrl).replaceAll(
        RegExp(r'/$'),
        '',
      );

  final http.Client _client;
  final String _baseUrl;

  Future<List<MemoryItem>> getMemories({
    MemoryType? memoryType,
    bool? active,
    int limit = 50,
  }) async {
    final query = <String, String>{'limit': limit.toString()};
    if (memoryType != null) {
      query['memory_type'] = memoryType.apiValue;
    }
    if (active != null) {
      query['active'] = active.toString();
    }

    final response = await _client.get(_uri('/memory', query));
    final data = _decodeResponse(response);

    if (data is! List) {
      throw const MemoryApiException('Backend returned an invalid response.');
    }

    return data
        .whereType<Map<String, dynamic>>()
        .map(MemoryItem.fromJson)
        .toList(growable: false);
  }

  Future<MemoryItem> updateMemory(
    String memoryId, {
    MemoryType? memoryType,
    String? content,
    int? importance,
    bool? active,
  }) async {
    final body = <String, dynamic>{};
    if (memoryType != null) {
      body['memory_type'] = memoryType.apiValue;
    }
    if (content != null) {
      body['content'] = content;
    }
    if (importance != null) {
      body['importance'] = importance;
    }
    if (active != null) {
      body['active'] = active;
    }

    final response = await _client.patch(
      _uri('/memory/$memoryId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    final data = _decodeResponse(response);

    if (data is! Map<String, dynamic>) {
      throw const MemoryApiException('Backend returned an invalid response.');
    }

    return MemoryItem.fromJson(data);
  }

  Future<void> deactivateMemory(String memoryId) async {
    final response = await _client.delete(_uri('/memory/$memoryId'));

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw MemoryApiException(_errorMessage(response.body));
    }
  }

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse('$_baseUrl$path');
    if (query == null || query.isEmpty) {
      return base;
    }

    return base.replace(queryParameters: query);
  }

  dynamic _decodeResponse(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw MemoryApiException(_errorMessage(response.body));
    }

    try {
      return jsonDecode(response.body);
    } on FormatException {
      throw const MemoryApiException(
        'Backend returned an unreadable response.',
      );
    }
  }

  String _errorMessage(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }
        if (detail is List && detail.isNotEmpty) {
          return 'Request could not be processed.';
        }
      }
    } on FormatException {
      return 'Backend returned an unreadable error.';
    }

    return 'Rex backend returned an error.';
  }
}

class MemoryApiException implements Exception {
  const MemoryApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
