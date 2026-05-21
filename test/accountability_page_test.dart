import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/accountability/data/accountability_api.dart';
import 'package:rex/features/accountability/presentation/pages/accountability_page.dart';

void main() {
  testWidgets('AccountabilityPage hides raw milestones behind internal memory', (
    tester,
  ) async {
    final api = AccountabilityApi(
      baseUrl: 'https://api.example.test',
      client: MockClient((request) async {
        return http.Response(jsonEncode(_overviewPayload()), 200);
      }),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [accountabilityApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: AccountabilityPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Relocate to Europe next year'), findsOneWidget);
    expect(find.text('Move with enough income and savings.'), findsOneWidget);
    expect(find.text(r'$5k monthly revenue target'), findsNothing);
    expect(find.text('Submit first FlowForce offer'), findsOneWidget);
    await tester.ensureVisible(find.text('Internal milestones'));
    await tester.pumpAndSettle();
    expect(find.text('Internal milestones'), findsOneWidget);

    await tester.tap(find.text('Internal milestones'));
    await tester.pumpAndSettle();

    expect(find.text(r'$5k monthly revenue target'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('Duplicate Risks'),
      260,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Duplicate Risks'), findsOneWidget);
    expect(find.text('Relocate to Europe next year duplicate'), findsOneWidget);
  });
}

Map<String, dynamic> _overviewPayload() {
  final plan = {
    'id': 'plan-europe',
    'plan_type': 'personal',
    'title': 'Relocate to Europe next year',
    'description': 'Move with enough income and savings.',
    'desired_outcome': 'Living in Europe sustainably.',
    'priority': 5,
    'status': 'active',
    'active': true,
  };
  final milestone = {
    'id': 'milestone-income',
    'plan_id': 'plan-europe',
    'title': r'$5k monthly revenue target',
    'description': 'Reach stable app/client revenue.',
    'milestone_type': 'goal',
    'priority': 5,
    'status': 'open',
    'active': true,
    'open_commitments': [
      {
        'id': 'commitment-offer',
        'commitment_type': 'work',
        'title': 'FlowForce offer',
        'commitment_text': 'Submit first FlowForce offer',
        'plan_id': 'plan-europe',
        'milestone_id': 'milestone-income',
        'priority': 4,
        'status': 'open',
        'active': true,
      },
    ],
  };
  return {
    'signals': [],
    'rule_risks': [],
    'plan_risks': [],
    'recent_patterns': [],
    'active_rules': [],
    'open_commitments': [],
    'active_plans': [plan],
    'open_milestones': [milestone],
    'plan_hierarchy': [
      {
        'plan': plan,
        'open_milestones': [milestone],
        'open_commitments': [],
        'counts': {'open_milestones': 1, 'open_commitments': 1},
      },
    ],
    'duplicate_warnings': [
      {
        'record_type': 'plan',
        'title': 'Relocate to Europe next year duplicate',
        'record_ids': ['plan-europe', 'plan-copy'],
        'reason': 'multiple_active_records_share_core_wording',
      },
    ],
    'metadata': {
      'active_plan_count': 1,
      'open_milestone_count': 1,
      'open_task_count': 1,
      'duplicate_warning_count': 1,
    },
  };
}
