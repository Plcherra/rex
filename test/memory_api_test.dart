import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/memory/data/memory_api.dart';
import 'package:rex/features/memory/data/memory_models.dart';

void main() {
  test('MemoryApi gets memories with filters', () async {
    final api = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/memory');
        expect(request.url.queryParameters['limit'], '50');
        expect(request.url.queryParameters['memory_type'], 'preference');
        expect(request.url.queryParameters['active'], 'true');
        return http.Response('''
          [
            {
              "id": "memory-1",
              "memory_type": "preference",
              "content": "I prefer direct advice.",
              "source_conversation_id": "conversation-1",
              "source_message_id": "message-1",
              "importance": 4,
              "active": true,
              "created_at": "2026-05-11T10:00:00Z",
              "updated_at": "2026-05-11T10:00:00Z",
              "last_accessed_at": "2026-05-11T10:00:00Z"
            }
          ]
          ''', 200);
      }),
    );

    final memories = await api.getMemories(
      memoryType: MemoryType.preference,
      active: true,
    );

    expect(memories, hasLength(1));
    expect(memories.single.id, 'memory-1');
    expect(memories.single.memoryType, MemoryType.preference);
    expect(memories.single.content, 'I prefer direct advice.');
  });

  test('MemoryApi updates a memory', () async {
    final api = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'PATCH');
        expect(request.url.toString(), 'http://rex.test/memory/memory-1');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['content'], 'I prefer blunt advice.');
        expect(body['memory_type'], 'preference');
        expect(body['importance'], 5);
        expect(body['active'], true);
        return http.Response('''
          {
            "id": "memory-1",
            "memory_type": "preference",
            "content": "I prefer blunt advice.",
            "source_conversation_id": null,
            "source_message_id": null,
            "importance": 5,
            "active": true,
            "created_at": "2026-05-11T10:00:00Z",
            "updated_at": "2026-05-11T10:05:00Z",
            "last_accessed_at": "2026-05-11T10:00:00Z"
          }
          ''', 200);
      }),
    );

    final memory = await api.updateMemory(
      'memory-1',
      memoryType: MemoryType.preference,
      content: 'I prefer blunt advice.',
      importance: 5,
      active: true,
    );

    expect(memory.content, 'I prefer blunt advice.');
    expect(memory.importance, 5);
  });

  test('MemoryApi deactivates a memory', () async {
    final api = MemoryApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'DELETE');
        expect(request.url.toString(), 'http://rex.test/memory/memory-1');
        return http.Response('', 204);
      }),
    );

    await api.deactivateMemory('memory-1');
  });
}
