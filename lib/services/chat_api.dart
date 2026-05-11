import 'dart:convert';

import 'package:cross_file/cross_file.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/chat/data/chat_models.dart';

class ChatApiException implements Exception {
  const ChatApiException(this.message, {this.type = ChatApiErrorType.unknown});

  final String message;
  final ChatApiErrorType type;

  @override
  String toString() => message;
}

enum ChatApiErrorType {
  backendValidation,
  network,
  upload,
  invalidResponse,
  unknown,
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
    XFile? attachment,
  }) async {
    final uri = Uri.parse('$_baseUrl/chat');
    try {
      final response = attachment == null
          ? await _sendJsonMessage(
              uri,
              message: message,
              conversationId: conversationId,
            )
          : await _sendMultipartMessage(
              uri,
              message: message,
              conversationId: conversationId,
              attachment: attachment,
            );

      return _chatResponseFromHttpResponse(response);
    } on ChatApiException {
      rethrow;
    } on http.ClientException {
      throw ChatApiException(
        attachment == null
            ? 'Could not reach Rex. Check your connection and try again.'
            : 'Could not upload the file. Check your connection and try again.',
        type: attachment == null
            ? ChatApiErrorType.network
            : ChatApiErrorType.upload,
      );
    } on Object {
      throw ChatApiException(
        attachment == null
            ? 'Something went wrong sending the message.'
            : 'Something went wrong uploading the file.',
        type: attachment == null
            ? ChatApiErrorType.unknown
            : ChatApiErrorType.upload,
      );
    }
  }

  Stream<ChatStreamEvent> streamMessage(
    String message, {
    String? conversationId,
    XFile? attachment,
  }) async* {
    final uri = Uri.parse('$_baseUrl/chat');
    try {
      final request = attachment == null
          ? _jsonStreamRequest(
              uri,
              message: message,
              conversationId: conversationId,
            )
          : await _multipartStreamRequest(
              uri,
              message: message,
              conversationId: conversationId,
              attachment: attachment,
            );
      final response = await _client.send(request);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final body = await response.stream.bytesToString();
        throw ChatApiException(
          _errorMessage(body),
          type: _errorTypeForStatusCode(response.statusCode),
        );
      }

      await for (final event in _eventsFromSse(response.stream)) {
        yield event;
      }
    } on ChatApiException {
      rethrow;
    } on http.ClientException {
      throw ChatApiException(
        attachment == null
            ? 'Could not reach Rex. Check your connection and try again.'
            : 'Could not upload the file. Check your connection and try again.',
        type: attachment == null
            ? ChatApiErrorType.network
            : ChatApiErrorType.upload,
      );
    } on FormatException {
      throw const ChatApiException(
        'Rex returned an unreadable streaming response.',
        type: ChatApiErrorType.invalidResponse,
      );
    } on Object {
      throw ChatApiException(
        attachment == null
            ? 'Something went wrong streaming the response.'
            : 'Something went wrong uploading the file.',
        type: attachment == null
            ? ChatApiErrorType.unknown
            : ChatApiErrorType.upload,
      );
    }
  }

  Future<http.Response> _sendJsonMessage(
    Uri uri, {
    required String message,
    String? conversationId,
  }) async {
    final payload = <String, String>{'message': message};
    if (conversationId != null) {
      payload['conversation_id'] = conversationId;
    }

    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    return response;
  }

  Future<http.Response> _sendMultipartMessage(
    Uri uri, {
    required String message,
    String? conversationId,
    required XFile attachment,
  }) async {
    final request = http.MultipartRequest('POST', uri)
      ..fields['message'] = message;
    if (conversationId != null) {
      request.fields['conversation_id'] = conversationId;
    }

    final fileName = attachment.name.trim().isNotEmpty
        ? attachment.name.trim()
        : p.basename(attachment.path);
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        await attachment.readAsBytes(),
        filename: fileName,
      ),
    );

    final streamedResponse = await _client.send(request);
    return http.Response.fromStream(streamedResponse);
  }

  http.BaseRequest _jsonStreamRequest(
    Uri uri, {
    required String message,
    String? conversationId,
  }) {
    final payload = <String, Object>{'message': message, 'stream': true};
    if (conversationId != null) {
      payload['conversation_id'] = conversationId;
    }

    return http.Request('POST', uri)
      ..headers['Content-Type'] = 'application/json'
      ..body = jsonEncode(payload);
  }

  Future<http.BaseRequest> _multipartStreamRequest(
    Uri uri, {
    required String message,
    String? conversationId,
    required XFile attachment,
  }) async {
    final request = http.MultipartRequest('POST', uri)
      ..fields['message'] = message
      ..fields['stream'] = 'true';
    if (conversationId != null) {
      request.fields['conversation_id'] = conversationId;
    }

    final fileName = attachment.name.trim().isNotEmpty
        ? attachment.name.trim()
        : p.basename(attachment.path);
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        await attachment.readAsBytes(),
        filename: fileName,
      ),
    );
    return request;
  }

  Stream<ChatStreamEvent> _eventsFromSse(Stream<List<int>> byteStream) async* {
    var eventName = 'message';
    final dataLines = <String>[];

    void reset() {
      eventName = 'message';
      dataLines.clear();
    }

    ChatStreamEvent? parseEvent() {
      if (dataLines.isEmpty) {
        reset();
        return null;
      }

      final currentEventName = eventName;
      final data = jsonDecode(dataLines.join('\n'));
      reset();
      if (data is! Map<String, dynamic>) {
        throw const FormatException('Invalid SSE payload.');
      }

      switch (currentEventName) {
        case 'conversation':
          final conversationId = data['conversation_id'];
          if (conversationId is String && conversationId.isNotEmpty) {
            return ChatStreamConversation(conversationId);
          }
          throw const FormatException('Missing streamed conversation id.');
        case 'token':
          final token = data['token'];
          return ChatStreamToken(token is String ? token : '');
        case 'done':
          return ChatStreamDone(ChatApiResponse.fromJson(data));
        case 'error':
          final detail = data['detail'];
          throw ChatApiException(
            detail is String && detail.trim().isNotEmpty
                ? detail
                : 'Rex streaming failed.',
            type: ChatApiErrorType.unknown,
          );
        default:
          return null;
      }
    }

    await for (final line
        in byteStream.transform(utf8.decoder).transform(const LineSplitter())) {
      if (line.isEmpty) {
        final parsed = parseEvent();
        if (parsed != null) {
          yield parsed;
        }
        continue;
      }

      if (line.startsWith('event:')) {
        eventName = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.add(line.substring(5).trimLeft());
      }
    }

    final parsed = parseEvent();
    if (parsed != null) {
      yield parsed;
    }
  }

  ChatApiResponse _chatResponseFromHttpResponse(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ChatApiException(
        _errorMessage(response.body),
        type: _errorTypeForStatusCode(response.statusCode),
      );
    }

    final dynamic data;
    try {
      data = jsonDecode(response.body);
    } on FormatException {
      throw const ChatApiException(
        'Rex returned an unreadable response.',
        type: ChatApiErrorType.invalidResponse,
      );
    }
    if (data is! Map<String, dynamic>) {
      throw const ChatApiException(
        'Rex returned an invalid response.',
        type: ChatApiErrorType.invalidResponse,
      );
    }

    return ChatApiResponse.fromJson(data);
  }

  ChatApiErrorType _errorTypeForStatusCode(int statusCode) {
    if (statusCode == 400 ||
        statusCode == 413 ||
        statusCode == 415 ||
        statusCode == 422) {
      return ChatApiErrorType.backendValidation;
    }

    return ChatApiErrorType.unknown;
  }

  String _errorMessage(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }
        if (detail is Map<String, dynamic>) {
          final message = detail['message'] ?? detail['msg'];
          if (message is String && message.trim().isNotEmpty) {
            return message;
          }
        }
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map<String, dynamic>) {
            final message = first['msg'] ?? first['message'];
            if (message is String && message.trim().isNotEmpty) {
              return message;
            }
          }
          return 'Request could not be processed.';
        }
      }
    } on FormatException {
      return 'Backend returned an unreadable error.';
    }

    return 'Rex backend returned an error.';
  }
}

sealed class ChatStreamEvent {
  const ChatStreamEvent();
}

class ChatStreamConversation extends ChatStreamEvent {
  const ChatStreamConversation(this.conversationId);

  final String conversationId;
}

class ChatStreamToken extends ChatStreamEvent {
  const ChatStreamToken(this.token);

  final String token;
}

class ChatStreamDone extends ChatStreamEvent {
  const ChatStreamDone(this.response);

  final ChatApiResponse response;
}
