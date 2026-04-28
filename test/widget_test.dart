import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:rex/core/rex_app.dart';

void main() {
  testWidgets('Rex app shows chat shell', (WidgetTester tester) async {
    await tester.pumpWidget(const RexApp());

    expect(find.text('Rex'), findsOneWidget);
    expect(find.textContaining('Rex.'), findsWidgets);
    expect(find.byType(TextField), findsOneWidget);
  });
}
