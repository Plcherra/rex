import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/accountability/data/accountability_models.dart';

class AccountabilityPage extends ConsumerStatefulWidget {
  const AccountabilityPage({super.key});

  @override
  ConsumerState<AccountabilityPage> createState() => _AccountabilityPageState();
}

class _AccountabilityPageState extends ConsumerState<AccountabilityPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(accountabilityProvider.notifier).loadOverview(),
    );
  }

  Future<void> _refresh() {
    return ref.read(accountabilityProvider.notifier).loadOverview();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(accountabilityProvider);
    final overview = state.overview;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Accountability'),
        actions: [
          IconButton(
            onPressed: state.isLoading ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh accountability',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  if (state.errorMessage != null)
                    _ErrorBanner(message: state.errorMessage!),
                  if (state.isLoading && overview == null)
                    const _InitialLoading()
                  else if (overview == null || overview.isEmpty)
                    const _EmptyAccountabilityState()
                  else ...[
                    _OverviewSummary(overview: overview),
                    const SizedBox(height: 20),
                    _SignalSection(signals: overview.signals),
                    const SizedBox(height: 20),
                    _RuleSection(rules: overview.activeRules),
                    const SizedBox(height: 20),
                    _CommitmentSection(
                      commitments: overview.openCommitments
                          .where(
                            (commitment) =>
                                commitment.planId == null &&
                                commitment.milestoneId == null,
                          )
                          .toList(growable: false),
                    ),
                    if (overview.pendingMemoryCandidates.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      _PendingCandidateSection(
                        candidates: overview.pendingMemoryCandidates,
                      ),
                    ],
                    const SizedBox(height: 20),
                    _PlanSection(
                      planHierarchy: overview.planHierarchy,
                      plans: overview.activePlans,
                      milestones: overview.openMilestones,
                      completedMilestones: overview.completedMilestones,
                    ),
                    if (overview.duplicateWarnings.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      _DuplicateWarningSection(
                        warnings: overview.duplicateWarnings,
                      ),
                    ],
                  ],
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OverviewSummary extends StatelessWidget {
  const _OverviewSummary({required this.overview});

  final AccountabilityOverview overview;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: [
        _SummaryPill(
          icon: Icons.warning_amber_rounded,
          label: 'Signals',
          value: overview.signals.length,
        ),
        _SummaryPill(
          icon: Icons.rule_rounded,
          label: 'Rules',
          value: overview.activeRules.length,
        ),
        _SummaryPill(
          icon: Icons.check_circle_outline_rounded,
          label: 'Tasks',
          value: overview.openTaskCount,
        ),
        _SummaryPill(
          icon: Icons.task_alt_rounded,
          label: 'Targets',
          value: overview.openMilestoneCount,
        ),
        if (overview.completedMilestoneCount > 0)
          _SummaryPill(
            icon: Icons.emoji_events_outlined,
            label: 'Won',
            value: overview.completedMilestoneCount,
          ),
        if (overview.pendingMemoryCandidateCount > 0)
          _SummaryPill(
            icon: Icons.pending_actions_rounded,
            label: 'Pending',
            value: overview.pendingMemoryCandidateCount,
          ),
        _SummaryPill(
          icon: Icons.flag_rounded,
          label: 'Plans',
          value: overview.activePlanCount,
        ),
      ],
    );
  }
}

class _SummaryPill extends StatelessWidget {
  const _SummaryPill({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.58),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 17, color: scheme.primary),
            const SizedBox(width: 7),
            Text(
              '$value $label',
              style: theme.textTheme.labelLarge?.copyWith(
                color: scheme.onSurface,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SignalSection extends StatelessWidget {
  const _SignalSection({required this.signals});

  final List<AccountabilitySignal> signals;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Current Signals',
      emptyText: 'No active accountability signals right now.',
      children: signals.map((signal) => _SignalTile(signal: signal)).toList(),
    );
  }
}

class _RuleSection extends StatelessWidget {
  const _RuleSection({required this.rules});

  final List<PersonalRule> rules;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Active Rules',
      emptyText: 'No active personal rules yet.',
      children: rules.map((rule) => _RuleTile(rule: rule)).toList(),
    );
  }
}

class _CommitmentSection extends StatelessWidget {
  const _CommitmentSection({required this.commitments});

  final List<Commitment> commitments;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Open Commitments',
      emptyText: 'No open commitments right now.',
      children: commitments
          .map((commitment) => _CommitmentTile(commitment: commitment))
          .toList(),
    );
  }
}

class _PendingCandidateSection extends StatelessWidget {
  const _PendingCandidateSection({required this.candidates});

  final List<PendingMemoryCandidate> candidates;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Pending Memory',
      emptyText: 'No pending memory changes.',
      children: candidates
          .map((candidate) => _PendingCandidateTile(candidate: candidate))
          .toList(growable: false),
    );
  }
}

class _PlanSection extends StatelessWidget {
  const _PlanSection({
    required this.planHierarchy,
    required this.plans,
    required this.milestones,
    required this.completedMilestones,
  });

  final List<PlanHierarchyItem> planHierarchy;
  final List<PlanRecord> plans;
  final List<PlanMilestone> milestones;
  final List<PlanMilestone> completedMilestones;

  @override
  Widget build(BuildContext context) {
    final planTiles = planHierarchy.isNotEmpty
        ? planHierarchy
              .map((item) => _PlanTile(item: item))
              .toList(growable: false)
        : plans
              .map(
                (plan) => _PlanTile(
                  item: PlanHierarchyItem(
                    plan: plan,
                    openMilestones: milestones
                        .where((milestone) => milestone.planId == plan.id)
                        .toList(growable: false),
                    completedMilestones: completedMilestones
                        .where((milestone) => milestone.planId == plan.id)
                        .toList(growable: false),
                    openCommitments: const [],
                    counts: const {},
                  ),
                ),
              )
              .toList(growable: false);
    final orphanMilestones = milestones
        .where((milestone) => !plans.any((plan) => plan.id == milestone.planId))
        .map((milestone) => _InternalMilestoneRow(milestone: milestone))
        .toList(growable: false);

    return _Section(
      title: 'Plan Progress',
      emptyText: 'No active plans or open milestones yet.',
      children: [
        ...planTiles,
        if (orphanMilestones.isNotEmpty)
          _InternalMemoryTile(
            title: 'Unlinked internal milestones',
            children: orphanMilestones,
          ),
      ],
    );
  }
}

class _DuplicateWarningSection extends StatelessWidget {
  const _DuplicateWarningSection({required this.warnings});

  final List<DuplicateWarning> warnings;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Duplicate Risks',
      emptyText: 'No duplicate risks detected.',
      children: warnings
          .map((warning) => _DuplicateWarningTile(warning: warning))
          .toList(growable: false),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.emptyText,
    required this.children,
  });

  final String title;
  final String emptyText;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        if (children.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              emptyText,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          )
        else
          DecoratedBox(
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(color: scheme.outlineVariant),
                bottom: BorderSide(color: scheme.outlineVariant),
              ),
            ),
            child: Column(
              children: [
                for (var index = 0; index < children.length; index++) ...[
                  children[index],
                  if (index != children.length - 1) const Divider(height: 1),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _SignalTile extends StatelessWidget {
  const _SignalTile({required this.signal});

  final AccountabilitySignal signal;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final accent = _severityColor(scheme, signal.severity);

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 8),
      leading: CircleAvatar(
        backgroundColor: accent.withValues(alpha: 0.16),
        foregroundColor: accent,
        child: Icon(_signalIcon(signal.signalType), size: 20),
      ),
      title: Text(
        signal.title,
        style: theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w700,
        ),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(signal.summary.isEmpty ? signal.reason : signal.summary),
            const SizedBox(height: 8),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: [
                _MetaChip(label: signal.signalType.label),
                _MetaChip(label: signal.severity.label),
                if (signal.sourceRefs.isNotEmpty)
                  _MetaChip(label: _sourceLabel(signal.sourceRefs.first)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RuleTile extends StatelessWidget {
  const _RuleTile({required this.rule});

  final PersonalRule rule;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      leading: const _TileIcon(icon: Icons.rule_rounded),
      title: Text(rule.title),
      subtitle: _RecordSubtitle(
        text: rule.ruleText,
        chips: [
          rule.ruleType.accountabilityLabel,
          'Priority ${rule.priority}',
          rule.enforcementStyle.accountabilityLabel,
        ],
      ),
    );
  }
}

class _CommitmentTile extends StatelessWidget {
  const _CommitmentTile({required this.commitment});

  final Commitment commitment;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      leading: const _TileIcon(icon: Icons.check_circle_outline_rounded),
      title: Text(commitment.title),
      subtitle: _RecordSubtitle(
        text: commitment.commitmentText,
        chips: [
          commitment.commitmentType.accountabilityLabel,
          commitment.status.accountabilityLabel,
          if (commitment.dueAt != null) 'Due ${_shortDate(commitment.dueAt!)}',
        ],
      ),
    );
  }
}

class _PlanTile extends StatelessWidget {
  const _PlanTile({required this.item});

  final PlanHierarchyItem item;

  @override
  Widget build(BuildContext context) {
    final plan = item.plan;
    final milestones = item.openMilestones;
    final completed = item.completedMilestones;
    final details = plan.description ?? plan.desiredOutcome ?? '';
    final tasks = <Commitment>[
      ...item.openCommitments,
      for (final milestone in milestones) ...milestone.openCommitments,
    ];
    final achievementTargets = milestones
        .where((milestone) => milestone.openCommitments.isEmpty)
        .take(3)
        .toList(growable: false);

    return Column(
      children: [
        ListTile(
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 0,
            vertical: 6,
          ),
          leading: const _TileIcon(icon: Icons.flag_rounded),
          title: Text(plan.title),
          trailing: const _PlanActions(),
          subtitle: _RecordSubtitle(
            text: details,
            chips: [
              plan.planType.accountabilityLabel,
              plan.status.accountabilityLabel,
              if (plan.targetDate != null)
                'Target ${_shortDate(plan.targetDate!)}',
            ],
          ),
        ),
        if (tasks.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 44, right: 4, bottom: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: tasks
                  .map((commitment) => _ChecklistRow(commitment: commitment))
                  .toList(growable: false),
            ),
          ),
        if (completed.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 44, right: 4, bottom: 8),
            child: _MilestoneBadgeWrap(milestones: completed),
          ),
        if (achievementTargets.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 44, right: 4, bottom: 8),
            child: _UpcomingTargets(milestones: achievementTargets),
          ),
        if (milestones.length >= 8)
          const Padding(
            padding: EdgeInsets.only(left: 44, right: 4, bottom: 8),
            child: _InlineWarning(
              text: 'This plan has too many raw open milestones.',
            ),
          ),
        if (milestones.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 44, right: 4, bottom: 8),
            child: _InternalMemoryTile(
              title: 'Internal milestones',
              children: milestones
                  .map(
                    (milestone) => _InternalMilestoneRow(milestone: milestone),
                  )
                  .toList(growable: false),
            ),
          ),
      ],
    );
  }
}

class _PlanActions extends StatelessWidget {
  const _PlanActions();

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: 'Plan actions',
      itemBuilder: (context) => const [
        PopupMenuItem(value: 'edit', child: Text('Edit')),
        PopupMenuItem(value: 'archive', child: Text('Archive')),
      ],
      onSelected: (_) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Plan edits go through confirmed memory changes.'),
          ),
        );
      },
    );
  }
}

class _UpcomingTargets extends StatelessWidget {
  const _UpcomingTargets({required this.milestones});

  final List<PlanMilestone> milestones;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Next targets',
          style: theme.textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 7),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: milestones
              .map(
                (milestone) => _MetaChip(
                  label: milestone.targetDate == null
                      ? milestone.title
                      : '${milestone.title} - ${_shortDate(milestone.targetDate!)}',
                ),
              )
              .toList(growable: false),
        ),
      ],
    );
  }
}

class _MilestoneBadgeWrap extends StatelessWidget {
  const _MilestoneBadgeWrap({required this.milestones});

  final List<PlanMilestone> milestones;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Completed milestones',
          style: theme.textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 7),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: milestones
              .map(
                (milestone) => _StatusChip(
                  icon: Icons.emoji_events_outlined,
                  label: milestone.title,
                ),
              )
              .toList(growable: false),
        ),
      ],
    );
  }
}

class _InternalMemoryTile extends StatelessWidget {
  const _InternalMemoryTile({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      title: Text(title),
      subtitle: Text('${children.length} raw records'),
      children: children,
    );
  }
}

class _InternalMilestoneRow extends StatelessWidget {
  const _InternalMilestoneRow({required this.milestone});

  final PlanMilestone milestone;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.subdirectory_arrow_right_rounded,
            size: 18,
            color: scheme.primary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  milestone.title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 5),
                Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: [
                    _MetaChip(
                      label: milestone.milestoneType.accountabilityLabel,
                    ),
                    _MetaChip(label: milestone.status.accountabilityLabel),
                    if (milestone.targetDate != null)
                      _MetaChip(
                        label: 'Due ${_shortDate(milestone.targetDate!)}',
                      ),
                  ],
                ),
                if (milestone.openCommitments.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Column(
                    children: milestone.openCommitments
                        .map(
                          (commitment) => _ChecklistRow(commitment: commitment),
                        )
                        .toList(growable: false),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChecklistRow extends StatelessWidget {
  const _ChecklistRow({required this.commitment});

  final Commitment commitment;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.check_circle_outline_rounded,
            size: 17,
            color: scheme.primary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              commitment.commitmentText.isEmpty
                  ? commitment.title
                  : commitment.commitmentText,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PendingCandidateTile extends StatelessWidget {
  const _PendingCandidateTile({required this.candidate});

  final PendingMemoryCandidate candidate;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      leading: const _TileIcon(icon: Icons.pending_actions_rounded),
      title: Text(candidate.preview),
      subtitle: _RecordSubtitle(
        text: candidate.reason,
        chips: [
          candidate.candidateType.accountabilityLabel,
          candidate.riskLevel.accountabilityLabel,
          candidate.status.accountabilityLabel,
        ],
      ),
    );
  }
}

class _DuplicateWarningTile extends StatelessWidget {
  const _DuplicateWarningTile({required this.warning});

  final DuplicateWarning warning;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      leading: const _TileIcon(icon: Icons.merge_type_rounded),
      title: Text(warning.title),
      subtitle: _RecordSubtitle(
        text:
            'Multiple active ${warning.recordType.accountabilityLabel}s may overlap.',
        chips: [
          warning.recordType.accountabilityLabel,
          '${warning.recordIds.length} records',
        ],
      ),
    );
  }
}

class _InlineWarning extends StatelessWidget {
  const _InlineWarning({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.errorContainer.withValues(alpha: 0.34),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.warning_amber_rounded,
              size: 17,
              color: scheme.onErrorContainer,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onErrorContainer,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecordSubtitle extends StatelessWidget {
  const _RecordSubtitle({required this.text, required this.chips});

  final String text;
  final List<String> chips;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (text.trim().isNotEmpty)
            Text(
              text,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          if (text.trim().isNotEmpty) const SizedBox(height: 8),
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: chips
                .where((chip) => chip.trim().isNotEmpty)
                .map((chip) => _MetaChip(label: chip))
                .toList(growable: false),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: scheme.onPrimaryContainer),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                label,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TileIcon extends StatelessWidget {
  const _TileIcon({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return CircleAvatar(
      backgroundColor: scheme.primaryContainer,
      foregroundColor: scheme.onPrimaryContainer,
      child: Icon(icon, size: 20),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Text(
          label,
          style: theme.textTheme.labelMedium?.copyWith(
            color: scheme.onSurfaceVariant,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _InitialLoading extends StatelessWidget {
  const _InitialLoading();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 320,
      child: Center(child: CircularProgressIndicator()),
    );
  }
}

class _EmptyAccountabilityState extends StatelessWidget {
  const _EmptyAccountabilityState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return SizedBox(
      height: 360,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.fact_check_outlined, size: 40, color: scheme.primary),
            const SizedBox(height: 14),
            Text(
              'Nothing to review yet',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Rules, commitments, plans, and risks will appear here.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.errorContainer,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(
                Icons.error_outline_rounded,
                color: scheme.onErrorContainer,
                size: 18,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onErrorContainer,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

IconData _signalIcon(AccountabilitySignalType type) {
  switch (type) {
    case AccountabilitySignalType.ruleViolation:
      return Icons.rule_rounded;
    case AccountabilitySignalType.missedCommitment:
      return Icons.event_busy_rounded;
    case AccountabilitySignalType.planDrift:
      return Icons.route_rounded;
    case AccountabilitySignalType.repeatedPattern:
      return Icons.repeat_rounded;
    case AccountabilitySignalType.upcomingDeadline:
      return Icons.event_rounded;
    case AccountabilitySignalType.budgetRisk:
      return Icons.savings_rounded;
    case AccountabilitySignalType.positiveFollowThrough:
      return Icons.check_circle_rounded;
    case AccountabilitySignalType.unknown:
      return Icons.info_outline_rounded;
  }
}

Color _severityColor(ColorScheme scheme, AccountabilitySeverity severity) {
  switch (severity) {
    case AccountabilitySeverity.critical:
    case AccountabilitySeverity.high:
      return scheme.error;
    case AccountabilitySeverity.medium:
      return scheme.tertiary;
    case AccountabilitySeverity.low:
    case AccountabilitySeverity.info:
    case AccountabilitySeverity.unknown:
      return scheme.primary;
  }
}

String _sourceLabel(AccountabilitySourceRef source) {
  return source.title?.trim().isNotEmpty == true
      ? source.title!
      : source.sourceType.name.accountabilityLabel;
}

String _shortDate(DateTime dateTime) {
  final local = dateTime.toLocal();
  return '${local.month}/${local.day}/${local.year}';
}
