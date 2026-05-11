import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/memory/application/memory_controller.dart';
import 'package:rex/features/memory/data/memory_api.dart';
import 'package:rex/features/memory/data/memory_models.dart';

void main() {
  test('MemoryController loads memories', () async {
    final memoryApi = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.queryParameters['active'], 'true');
        return http.Response(_memoryListJson(), 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [memoryApiProvider.overrideWithValue(memoryApi)],
    );
    addTearDown(container.dispose);

    await container.read(memoryProvider.notifier).loadMemories();

    final state = container.read(memoryProvider);
    expect(state.isLoading, false);
    expect(state.errorMessage, isNull);
    expect(state.memories, hasLength(1));
    expect(state.memories.single.memoryType, MemoryType.preference);
  });

  test('MemoryController updates a memory in place', () async {
    final memoryApi = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        if (request.method == 'GET') {
          return http.Response(_memoryListJson(), 200);
        }

        expect(request.method, 'PATCH');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['content'], 'I prefer blunt advice.');
        return http.Response(
          _memoryJson(content: 'I prefer blunt advice.'),
          200,
        );
      }),
    );
    final container = ProviderContainer(
      overrides: [memoryApiProvider.overrideWithValue(memoryApi)],
    );
    addTearDown(container.dispose);

    await container.read(memoryProvider.notifier).loadMemories();
    final saved = await container
        .read(memoryProvider.notifier)
        .updateMemory('memory-1', content: 'I prefer blunt advice.');

    final state = container.read(memoryProvider);
    expect(saved, true);
    expect(state.isSaving, false);
    expect(state.memories.single.content, 'I prefer blunt advice.');
  });

  test('MemoryController removes active memory after deactivate', () async {
    final memoryApi = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        if (request.method == 'GET') {
          return http.Response(_memoryListJson(), 200);
        }

        expect(request.method, 'DELETE');
        return http.Response('', 204);
      }),
    );
    final container = ProviderContainer(
      overrides: [memoryApiProvider.overrideWithValue(memoryApi)],
    );
    addTearDown(container.dispose);

    await container.read(memoryProvider.notifier).loadMemories();
    final deactivated = await container
        .read(memoryProvider.notifier)
        .deactivateMemory('memory-1');

    final state = container.read(memoryProvider);
    expect(deactivated, true);
    expect(state.isSaving, false);
    expect(state.memories, isEmpty);
  });
}

String _memoryListJson() => '[${_memoryJson()}]';

String _memoryJson({String content = 'I prefer direct advice.'}) {
  return '''
    {
      "id": "memory-1",
      "memory_type": "preference",
      "content": "$content",
      "source_conversation_id": "conversation-1",
      "source_message_id": "message-1",
      "importance": 4,
      "active": true,
      "created_at": "2026-05-11T10:00:00Z",
      "updated_at": "2026-05-11T10:00:00Z",
      "last_accessed_at": "2026-05-11T10:00:00Z"
    }
  ''';
}
