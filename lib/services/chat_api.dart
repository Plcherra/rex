import 'dart:convert';

import 'package:http/http.dart' as http;

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/chat/data/chat_models.dart';

class ChatApiException implements Exception {
  const ChatApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class ChatApi {
  ChatApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = (baseUrl ?? AppConfig.backendBaseUrl).replaceAll(
        RegExp(r'/$'),
        '',
      );

  final http.Client _client;
  final String _baseUrl;

  Future<ChatApiResponse> sendMessage(
    String message, {
    String? conversationId,
  }) async {
    final uri = Uri.parse('$_baseUrl/chat');
    final payload = <String, String>{'message': message};
    if (conversationId != null) {
      payload['conversation_id'] = conversationId;
    }

    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ChatApiException(_errorMessage(response.body));
    }

    final data = jsonDecode(response.body);
    if (data is! Map<String, dynamic>) {
      throw const ChatApiException('Backend returned an invalid response.');
    }

    return ChatApiResponse.fromJson(data);
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
