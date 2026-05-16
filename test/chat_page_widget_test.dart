import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:rex/core/rex_app.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/presentation/widgets/chat_message_bubble.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/speech_to_text_service.dart';
import 'package:rex/features/voice/data/text_to_speech_service.dart';
import 'package:rex/services/chat_api.dart';

void main() {
  testWidgets('ChatPage renders the empty state and prompt chips', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const ProviderScope(child: RexApp()));

    expect(find.text('Rex'), findsWidgets);
    expect(find.textContaining("I'm Rex."), findsOneWidget);
    expect(find.text('Help me think through my day.'), findsOneWidget);
    expect(find.text('Remember that I prefer direct advice.'), findsOneWidget);
    expect(find.text('What should I focus on next?'), findsOneWidget);
  });

  testWidgets('ChatPage shows a sending state while chat request is pending', (
    WidgetTester tester,
  ) async {
    final responseCompleter = Completer<http.Response>();
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) => responseCompleter.future),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [chatApiProvider.overrideWithValue(api)],
        child: const RexApp(),
      ),
    );

    await tester.enterText(find.byType(TextField), 'Hello Rex');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pump();

    expect(
      find.descendant(
        of: find.byType(ChatMessageBubble),
        matching: find.textContaining('Hello Rex'),
      ),
      findsOneWidget,
    );
    expect(find.byType(ChatMessageBubble), findsNWidgets(2));
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, false);

    responseCompleter.complete(_streamingResponse());
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));
  });

  testWidgets('ChatPage renders streamed assistant response', (
    WidgetTester tester,
  ) async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async => _streamingResponse()),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [chatApiProvider.overrideWithValue(api)],
        child: const RexApp(),
      ),
    );

    await tester.enterText(find.byType(TextField), 'Hello Rex');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      find.descendant(
        of: find.byType(ChatMessageBubble),
        matching: find.textContaining('Hello Rex'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byType(ChatMessageBubble),
        matching: find.textContaining('Rex response'),
      ),
      findsOneWidget,
    );
    expect(find.text('Help me think through my day.'), findsNothing);
  });

  testWidgets('ChatPage opens voice sheet and sends stopped transcript', (
    WidgetTester tester,
  ) async {
    final permissionService = _FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = _FakeSpeechToTextService();
    final textToSpeechService = _FakeTextToSpeechService();
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.body, contains('"message":"Need direct advice"'));
        expect(request.body, contains('"stream":true'));
        return _streamingResponse();
      }),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          cloudVoiceEnabledProvider.overrideWithValue(false),
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
          textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
          voiceAudioSessionServiceProvider.overrideWithValue(
            _FakeVoiceAudioSessionService(),
          ),
          backgroundVoiceServiceProvider.overrideWithValue(
            _FakeBackgroundVoiceService(),
          ),
          chatApiProvider.overrideWithValue(api),
        ],
        child: const RexApp(),
      ),
    );

    await tester.tap(find.byTooltip('Talk to Rex'));
    await tester.pumpAndSettle();

    expect(find.text('Listening'), findsOneWidget);
    expect(permissionService.requestCount, 1);
    expect(speechToTextService.startListeningCount, 1);

    speechToTextService.emitPartialTranscript('Need direct advice');
    await tester.pump();
    expect(find.text('Need direct advice'), findsOneWidget);

    await tester.tap(find.text('Stop'));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(const Duration(milliseconds: 20));
    });
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));

    expect(speechToTextService.stopListeningCount, 1);
    expect(textToSpeechService.spokenText, 'Rex response');
    expect(find.text('Speaking'), findsOneWidget);
    expect(find.textContaining('Rex response'), findsWidgets);
  });

  testWidgets(
    'ChatPage shows streamed error state without dropping user text',
    (WidgetTester tester) async {
      final api = ChatApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          return http.Response(
            '{"detail":"Grok stream failed."}',
            503,
            headers: {'Content-Type': 'application/json'},
          );
        }),
      );

      final container = ProviderContainer(
        overrides: [chatApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(container: container, child: const RexApp()),
      );

      await tester.enterText(find.byType(TextField), 'Help me');
      await tester.pump();
      expect(
        tester
            .widget<IconButton>(
              find.widgetWithIcon(IconButton, Icons.arrow_upward_rounded),
            )
            .onPressed,
        isNotNull,
      );
      await tester.tap(
        find.widgetWithIcon(IconButton, Icons.arrow_upward_rounded),
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(seconds: 2));

      expect(container.read(chatProvider).messages, isNotEmpty);
      expect(container.read(chatProvider).errorMessage, 'Grok stream failed.');
      expect(
        find.descendant(
          of: find.byType(ChatMessageBubble),
          matching: find.textContaining('Help me'),
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Grok stream failed'), findsWidgets);
    },
  );

  testWidgets(
    'ChatPage switches to selected conversation and renders messages',
    (WidgetTester tester) async {
      final conversationApi = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          if (request.url.path == '/conversations') {
            return http.Response('''
[
  {
    "id": "conversation-1",
    "title": "Work stress",
    "timestamp": "2026-05-11T10:00:00Z",
    "last_message": {
      "id": "message-2",
      "conversation_id": "conversation-1",
      "role": "assistant",
      "content": "Saved answer",
      "timestamp": "2026-05-11T10:02:00Z"
    }
  }
]
''', 200);
          }

          if (request.url.path == '/conversations/conversation-1/messages') {
            return http.Response('''
[
  {
    "id": "message-1",
    "conversation_id": "conversation-1",
    "role": "user",
    "content": "Previous question",
    "timestamp": "2026-05-11T10:01:00Z"
  },
  {
    "id": "message-2",
    "conversation_id": "conversation-1",
    "role": "assistant",
    "content": "Saved answer",
    "timestamp": "2026-05-11T10:02:00Z"
  }
]
''', 200);
          }

          return http.Response('Not found', 404);
        }),
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            conversationApiProvider.overrideWithValue(conversationApi),
          ],
          child: const RexApp(),
        ),
      );

      await tester.tap(find.byTooltip('Conversations'));
      await tester.pumpAndSettle();
      expect(find.text('Work stress'), findsOneWidget);
      expect(find.text('Saved answer'), findsOneWidget);

      await tester.tap(find.text('Work stress'));
      await tester.pumpAndSettle();

      expect(find.text('Work stress'), findsOneWidget);
      expect(find.textContaining('Previous question'), findsOneWidget);
      expect(find.textContaining('Saved answer'), findsOneWidget);
    },
  );
}

class _FakeMicrophonePermissionService implements MicrophonePermissionService {
  _FakeMicrophonePermissionService(this.decision);

  final MicrophonePermissionDecision decision;
  var requestCount = 0;

  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  }) async {
    requestCount++;
    return decision;
  }

  @override
  Future<void> openSettings() async {}
}

class _FakeSpeechToTextService implements SpeechToTextService {
  var initializeCount = 0;
  var startListeningCount = 0;
  var stopListeningCount = 0;
  SpeechTranscriptCallback? onPartialTranscript;
  SpeechTranscriptCallback? onFinalTranscript;
  SpeechErrorCallback? onError;

  @override
  Future<bool> initialize({required SpeechErrorCallback onError}) async {
    initializeCount++;
    this.onError = onError;
    return true;
  }

  @override
  Future<void> startListening({
    required SpeechTranscriptCallback onPartialTranscript,
    required SpeechTranscriptCallback onFinalTranscript,
    required SpeechErrorCallback onError,
  }) async {
    startListeningCount++;
    this.onPartialTranscript = onPartialTranscript;
    this.onFinalTranscript = onFinalTranscript;
    this.onError = onError;
  }

  @override
  Future<void> stopListening() async {
    stopListeningCount++;
  }

  @override
  Future<void> cancel() async {}

  void emitPartialTranscript(String transcript) {
    onPartialTranscript?.call(transcript);
  }
}

class _FakeTextToSpeechService implements TextToSpeechService {
  var speakCount = 0;
  String? spokenText;

  @override
  Future<void> speak(
    String text, {
    required TextToSpeechCompleteCallback onComplete,
    required TextToSpeechErrorCallback onError,
  }) async {
    speakCount++;
    spokenText = text;
  }

  @override
  Future<void> stop() async {}

  @override
  Future<void> pause() async {}
}

class _FakeVoiceAudioSessionService implements VoiceAudioSessionService {
  @override
  Future<void> configureForVoiceTurn() async {}

  @override
  Future<void> setActive(bool active) async {}

  @override
  StreamSubscription<void> listenForNoisyAudio(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    return const Stream<void>.empty().listen((_) {});
  }

  @override
  StreamSubscription<AudioInterruptionEvent> listenForInterruptions(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    return const Stream<AudioInterruptionEvent>.empty().listen((_) {});
  }
}

class _FakeBackgroundVoiceService implements BackgroundVoiceService {
  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}
}

http.Response _streamingResponse() {
  return http.Response(
    '''
event: conversation
data: {"conversation_id":"conversation-1"}

event: token
data: {"token":"Rex "}

event: token
data: {"token":"response"}

event: done
data: {"conversation_id":"conversation-1","response":"Rex response","messages":[]}

''',
    200,
    headers: {'Content-Type': 'text/event-stream'},
  );
}
