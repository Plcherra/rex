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

  Future<List<PersonMemoryItem>> getPeople({
    bool? active,
    int limit = 50,
  }) async {
    final data = await _getList('/entities', {
      'entity_type': 'person',
      'limit': limit.toString(),
      if (active != null) 'active': active.toString(),
    });
    return data.map(PersonMemoryItem.fromJson).toList(growable: false);
  }

  Future<PersonMemoryItem> updatePerson(
    String personId, {
    String? displayName,
    String? relationship,
    String? summary,
    List<String>? aliases,
    int? importance,
    String? status,
    bool? active,
  }) async {
    final data = await _patchJson(
      '/entities/$personId',
      _withoutNulls({
        'display_name': displayName,
        'normalized_name': displayName?.toLowerCase(),
        'relationship': relationship,
        'summary': summary,
        'aliases': aliases,
        'importance': importance,
        'status': status,
        'active': active,
      }),
    );
    return PersonMemoryItem.fromJson(data);
  }

  Future<void> deactivatePerson(String personId) async {
    await _delete('/entities/$personId');
  }

  Future<List<RuleMemoryItem>> getRules({bool? active, int limit = 50}) async {
    final data = await _getList('/rules', {
      'limit': limit.toString(),
      if (active != null) 'active': active.toString(),
    });
    return data.map(RuleMemoryItem.fromJson).toList(growable: false);
  }

  Future<RuleMemoryItem> updateRule(
    String ruleId, {
    String? title,
    String? ruleText,
    List<String>? triggerKeywords,
    int? priority,
    String? status,
    bool? active,
  }) async {
    final data = await _patchJson(
      '/rules/$ruleId',
      _withoutNulls({
        'title': title,
        'rule_text': ruleText,
        'trigger_keywords': triggerKeywords,
        'priority': priority,
        'status': status,
        'active': active,
      }),
    );
    return RuleMemoryItem.fromJson(data);
  }

  Future<void> deactivateRule(String ruleId) async {
    await _delete('/rules/$ruleId');
  }

  Future<List<PlanMemoryItem>> getPlans({bool? active, int limit = 50}) async {
    final data = await _getList('/plans', {
      'limit': limit.toString(),
      if (active != null) 'active': active.toString(),
    });
    return data.map(PlanMemoryItem.fromJson).toList(growable: false);
  }

  Future<PlanMemoryItem> updatePlan(
    String planId, {
    String? title,
    String? description,
    String? desiredOutcome,
    int? priority,
    String? status,
    bool? active,
    DateTime? targetDate,
  }) async {
    final data = await _patchJson(
      '/plans/$planId',
      _withoutNulls({
        'title': title,
        'description': description,
        'desired_outcome': desiredOutcome,
        'priority': priority,
        'status': status,
        'active': active,
        'target_date': targetDate == null ? null : _dateOnly(targetDate),
      }),
    );
    return PlanMemoryItem.fromJson(data);
  }

  Future<void> deactivatePlan(String planId) async {
    await _delete('/plans/$planId');
  }

  Future<List<CommitmentMemoryItem>> getCommitments({
    bool? active,
    int limit = 50,
  }) async {
    final data = await _getList('/commitments', {
      'limit': limit.toString(),
      if (active != null) 'active': active.toString(),
    });
    return data.map(CommitmentMemoryItem.fromJson).toList(growable: false);
  }

  Future<CommitmentMemoryItem> updateCommitment(
    String commitmentId, {
    String? title,
    String? commitmentText,
    int? priority,
    String? status,
    bool? active,
    DateTime? dueAt,
  }) async {
    final data = await _patchJson(
      '/commitments/$commitmentId',
      _withoutNulls({
        'title': title,
        'commitment_text': commitmentText,
        'priority': priority,
        'status': status,
        'active': active,
        'due_at': dueAt?.toIso8601String(),
      }),
    );
    return CommitmentMemoryItem.fromJson(data);
  }

  Future<void> deactivateCommitment(String commitmentId) async {
    await _delete('/commitments/$commitmentId');
  }

  Future<void> deactivateMemory(String memoryId) async {
    await _delete('/memory/$memoryId');
  }

  Future<Map<String, dynamic>> _patchJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await _client.patch(
      _uri(path),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    final data = _decodeResponse(response);
    if (data is! Map<String, dynamic>) {
      throw const MemoryApiException('Backend returned an invalid response.');
    }
    return data;
  }

  Future<void> _delete(String path) async {
    final response = await _client.delete(_uri(path));
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

  Future<List<Map<String, dynamic>>> _getList(
    String path,
    Map<String, String> query,
  ) async {
    final response = await _client.get(_uri(path, query));
    final data = _decodeResponse(response);

    if (data is! List) {
      throw const MemoryApiException('Backend returned an invalid response.');
    }

    return data.whereType<Map<String, dynamic>>().toList(growable: false);
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

  String _dateOnly(DateTime value) {
    final local = value.toLocal();
    final month = local.month.toString().padLeft(2, '0');
    final day = local.day.toString().padLeft(2, '0');
    return '${local.year}-$month-$day';
  }

  Map<String, dynamic> _withoutNulls(Map<String, dynamic> values) {
    final body = <String, dynamic>{};
    for (final entry in values.entries) {
      final value = entry.value;
      if (value != null) {
        body[entry.key] = value;
      }
    }
    return body;
  }
}

class MemoryApiException implements Exception {
  const MemoryApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
