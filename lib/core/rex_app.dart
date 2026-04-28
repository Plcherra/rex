import 'package:flutter/material.dart';

import 'package:rex/core/theme/app_theme.dart';
import 'package:rex/features/chat/presentation/pages/chat_page.dart';

/// Root application widget: theme and initial route only.
class RexApp extends StatelessWidget {
  const RexApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Rex',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const ChatPage(),
    );
  }
}
