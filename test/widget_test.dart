import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:rex/core/rex_app.dart';
import 'package:rex/core/theme/app_theme.dart';
import 'package:rex/features/chat/presentation/widgets/chat_input_bar.dart';
import 'package:rex/features/chat/presentation/widgets/chat_message_bubble.dart';

void main() {
  testWidgets('Rex app shows chat shell', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: RexApp()));

    expect(find.text('Rex'), findsWidgets);
    expect(find.textContaining('Rex.'), findsWidgets);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byTooltip('Memory'), findsOneWidget);
    expect(find.byTooltip('Attach file'), findsOneWidget);
    expect(find.text('Help me think through my day.'), findsOneWidget);
  });

  testWidgets('ChatMessageBubble supports polished assistant and user states', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        darkTheme: AppTheme.dark,
        home: const Scaffold(
          body: Column(
            children: [
              ChatMessageBubble(text: 'Use **focus** and `budget`.'),
              ChatMessageBubble(text: 'Got it.', isUser: true),
            ],
          ),
        ),
      ),
    );

    expect(find.byType(ChatMessageBubble), findsNWidgets(2));
    expect(find.byIcon(Icons.auto_awesome_rounded), findsOneWidget);
    expect(find.textContaining('Got it.'), findsOneWidget);
  });

  testWidgets(
    'ChatMessageBubble renders loading indicator without text noise',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(
            body: ChatMessageBubble(text: '', isLoading: true),
          ),
        ),
      );

      expect(find.byType(ChatMessageBubble), findsOneWidget);
      expect(find.text('Thinking...'), findsNothing);
      await tester.pump(const Duration(milliseconds: 120));
    },
  );

  testWidgets('ChatInputBar keeps invalid file visible with friendly error', (
    WidgetTester tester,
  ) async {
    final controller = TextEditingController(text: 'Read this');
    addTearDown(controller.dispose);

    var sent = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatInputBar(
            controller: controller,
            attachmentName: 'bad.csv',
            attachmentSize: 2,
            attachmentError: 'Attachment must be valid UTF-8 text.',
            onSend: () => sent = true,
          ),
        ),
      ),
    );

    expect(find.text('bad.csv'), findsOneWidget);
    expect(find.text('Attachment must be valid UTF-8 text.'), findsOneWidget);

    await tester.tap(find.byTooltip('Send'));
    await tester.pump();

    expect(sent, false);
  });
}
