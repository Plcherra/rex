import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/accountability/data/accountability_models.dart';

final accountabilityApiProvider = Provider<AccountabilityApi>(
  (ref) => AccountabilityApi(),
);

class AccountabilityApi {
  AccountabilityApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = (baseUrl ?? AppConfig.backendBaseUrl).replaceAll(
        RegExp(r'/$'),
        '',
      );

  final http.Client _client;
  final String _baseUrl;

  Future<AccountabilityOverview> getOverview({int limit = 25}) async {
    final response = await _client.get(
      _uri('/accountability/overview', {'limit': limit.toString()}),
    );
    final data = _decodeResponse(response);

    if (data is! Map<String, dynamic>) {
      throw const AccountabilityApiException(
        'Backend returned an invalid accountability response.',
      );
    }

    return AccountabilityOverview.fromJson(data);
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
      throw AccountabilityApiException(_errorMessage(response.body));
    }

    try {
      return jsonDecode(response.body);
    } on FormatException {
      throw const AccountabilityApiException(
        'Backend returned an unreadable accountability response.',
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
          return 'Accountability request could not be processed.';
        }
      }
    } on FormatException {
      return 'Backend returned an unreadable accountability error.';
    }

    return 'Rex backend returned an accountability error.';
  }
}

class AccountabilityApiException implements Exception {
  const AccountabilityApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
