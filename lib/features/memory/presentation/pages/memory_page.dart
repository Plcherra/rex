import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/memory/application/memory_controller.dart';
import 'package:rex/features/memory/data/memory_models.dart';

class MemoryPage extends ConsumerStatefulWidget {
  const MemoryPage({super.key});

  @override
  ConsumerState<MemoryPage> createState() => _MemoryPageState();
}

class _MemoryPageState extends ConsumerState<MemoryPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(memoryProvider.notifier).loadMemories());
  }

  Future<void> _setTypeFilter(MemoryType? memoryType) async {
    await ref
        .read(memoryProvider.notifier)
        .loadMemories(layer: MemoryLayer.longTerm, memoryType: memoryType);
  }

  Future<void> _setLayer(MemoryLayer layer) async {
    await ref.read(memoryProvider.notifier).loadMemories(layer: layer);
  }

  Future<void> _setActiveOnly(bool activeOnly) async {
    final state = ref.read(memoryProvider);
    await ref
        .read(memoryProvider.notifier)
        .loadMemories(
          layer: state.selectedLayer,
          memoryType: state.selectedLayer == MemoryLayer.longTerm
              ? state.selectedType
              : null,
          activeOnly: activeOnly,
        );
  }

  Future<void> _editMemory(MemoryItem memory) async {
    final result = await showDialog<_MemoryEditResult>(
      context: context,
      builder: (context) => _MemoryEditDialog(memory: memory),
    );
    if (result == null) {
      return;
    }

    final saved = await ref
        .read(memoryProvider.notifier)
        .updateMemory(
          memory.id,
          memoryType: result.memoryType,
          content: result.content,
          importance: result.importance,
          active: result.active,
        );
    if (!mounted) {
      return;
    }

    _showSnackBar(saved ? 'Memory updated' : _currentError());
  }

  Future<void> _deactivateMemory(MemoryItem memory) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Deactivate memory?'),
        content: const Text(
          'Rex will stop using this memory in future conversations.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Deactivate'),
          ),
        ],
      ),
    );

    if (confirmed != true) {
      return;
    }

    final deactivated = await ref
        .read(memoryProvider.notifier)
        .deactivateMemory(memory.id);
    if (!mounted) {
      return;
    }

    _showSnackBar(deactivated ? 'Memory deactivated' : _currentError());
  }

  Future<void> _editPerson(PersonMemoryItem person) async {
    final result = await showDialog<_StructuredEditResult>(
      context: context,
      builder: (context) => _StructuredEditDialog(
        title: 'Edit person',
        primaryLabel: 'Name',
        primaryValue: person.displayName,
        detailLabel: 'Summary',
        detailValue: person.summary,
        extraLabel: 'Relationship',
        extraValue: person.relationship,
        aliasesValue: person.aliases.join(', '),
        importanceLabel: 'Importance',
        importance: person.importance,
        status: person.status,
        active: person.active,
      ),
    );
    if (result == null) {
      return;
    }

    final saved = await ref
        .read(memoryProvider.notifier)
        .updatePerson(
          person.id,
          displayName: result.primary,
          summary: result.detail,
          relationship: result.extra,
          aliases: result.aliases,
          importance: result.importance,
          status: result.status,
          active: result.active,
        );
    if (mounted) {
      _showSnackBar(saved ? 'Person updated' : _currentError());
    }
  }

  Future<void> _editRule(RuleMemoryItem rule) async {
    final result = await showDialog<_StructuredEditResult>(
      context: context,
      builder: (context) => _StructuredEditDialog(
        title: 'Edit rule',
        primaryLabel: 'Title',
        primaryValue: rule.title,
        detailLabel: 'Rule text',
        detailValue: rule.ruleText,
        extraLabel: 'Trigger keywords',
        extraValue: rule.triggerKeywords.join(', '),
        importanceLabel: 'Priority',
        importance: rule.priority,
        status: rule.status,
        active: rule.active,
      ),
    );
    if (result == null) {
      return;
    }

    final saved = await ref
        .read(memoryProvider.notifier)
        .updateRule(
          rule.id,
          title: result.primary,
          ruleText: result.detail,
          triggerKeywords: result.extraList,
          priority: result.importance,
          status: result.status,
          active: result.active,
        );
    if (mounted) {
      _showSnackBar(saved ? 'Rule updated' : _currentError());
    }
  }

  Future<void> _editPlan(PlanMemoryItem plan) async {
    final result = await showDialog<_StructuredEditResult>(
      context: context,
      builder: (context) => _StructuredEditDialog(
        title: 'Edit plan',
        primaryLabel: 'Title',
        primaryValue: plan.title,
        detailLabel: 'Description',
        detailValue: plan.description,
        extraLabel: 'Desired outcome',
        extraValue: plan.desiredOutcome,
        importanceLabel: 'Priority',
        importance: plan.priority,
        status: plan.status,
        active: plan.active,
      ),
    );
    if (result == null) {
      return;
    }

    final saved = await ref
        .read(memoryProvider.notifier)
        .updatePlan(
          plan.id,
          title: result.primary,
          description: result.detail,
          desiredOutcome: result.extra,
          priority: result.importance,
          status: result.status,
          active: result.active,
        );
    if (mounted) {
      _showSnackBar(saved ? 'Plan updated' : _currentError());
    }
  }

  Future<void> _editCommitment(CommitmentMemoryItem commitment) async {
    final result = await showDialog<_StructuredEditResult>(
      context: context,
      builder: (context) => _StructuredEditDialog(
        title: 'Edit commitment',
        primaryLabel: 'Title',
        primaryValue: commitment.title,
        detailLabel: 'Commitment',
        detailValue: commitment.commitmentText,
        importanceLabel: 'Priority',
        importance: commitment.priority,
        status: commitment.status,
        active: commitment.active,
      ),
    );
    if (result == null) {
      return;
    }

    final saved = await ref
        .read(memoryProvider.notifier)
        .updateCommitment(
          commitment.id,
          title: result.primary,
          commitmentText: result.detail,
          priority: result.importance,
          status: result.status,
          active: result.active,
        );
    if (mounted) {
      _showSnackBar(saved ? 'Commitment updated' : _currentError());
    }
  }

  Future<void> _deactivateStructuredMemory(
    MemoryLayer layer,
    String id,
    String label,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Deactivate $label?'),
        content: Text('Rex will stop treating this $label as active context.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Deactivate'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      return;
    }

    final deactivated = await ref
        .read(memoryProvider.notifier)
        .deactivateStructuredMemory(layer, id);
    if (mounted) {
      _showSnackBar(deactivated ? '$label deactivated' : _currentError());
    }
  }

  void _showSnackBar(String message) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  String _currentError() {
    return ref.read(memoryProvider).errorMessage ?? 'Memory action failed.';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(memoryProvider);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Memory'),
        actions: [
          IconButton(
            onPressed: state.isLoading
                ? null
                : () => ref
                      .read(memoryProvider.notifier)
                      .loadMemories(
                        layer: state.selectedLayer,
                        memoryType: state.selectedLayer == MemoryLayer.longTerm
                            ? state.selectedType
                            : null,
                      ),
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh memory',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref
            .read(memoryProvider.notifier)
            .loadMemories(
              layer: state.selectedLayer,
              memoryType: state.selectedLayer == MemoryLayer.longTerm
                  ? state.selectedType
                  : null,
            ),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: MemoryLayer.values
                          .map(
                            (layer) => FilterChip(
                              label: Text(layer.label),
                              selected: state.selectedLayer == layer,
                              onSelected: state.isLoading
                                  ? null
                                  : (_) => _setLayer(layer),
                            ),
                          )
                          .toList(growable: false),
                    ),
                    if (state.selectedLayer == MemoryLayer.longTerm) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          FilterChip(
                            label: const Text('All'),
                            selected: state.selectedType == null,
                            onSelected: state.isLoading
                                ? null
                                : (_) => _setTypeFilter(null),
                          ),
                          ...MemoryType.values.map(
                            (type) => FilterChip(
                              label: Text(type.label),
                              selected: state.selectedType == type,
                              onSelected: state.isLoading
                                  ? null
                                  : (_) => _setTypeFilter(type),
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Active memories only'),
                      value: state.activeOnly,
                      onChanged: state.isLoading ? null : _setActiveOnly,
                    ),
                    if (state.errorMessage != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          state.errorMessage!,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: scheme.error,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            if (state.isLoading && state.isSelectedLayerEmpty)
              const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              )
            else if (state.isSelectedLayerEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: _MemoryEmptyState(
                  layer: state.selectedLayer,
                  activeOnly: state.activeOnly,
                ),
              )
            else
              _MemoryLayerList(
                state: state,
                onEditMemory: _editMemory,
                onDeactivateMemory: _deactivateMemory,
                onEditPerson: _editPerson,
                onEditRule: _editRule,
                onEditPlan: _editPlan,
                onEditCommitment: _editCommitment,
                onDeactivateStructuredMemory: _deactivateStructuredMemory,
              ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
      ),
    );
  }
}

class _MemoryLayerList extends StatelessWidget {
  const _MemoryLayerList({
    required this.state,
    required this.onEditMemory,
    required this.onDeactivateMemory,
    required this.onEditPerson,
    required this.onEditRule,
    required this.onEditPlan,
    required this.onEditCommitment,
    required this.onDeactivateStructuredMemory,
  });

  final MemoryState state;
  final ValueChanged<MemoryItem> onEditMemory;
  final ValueChanged<MemoryItem> onDeactivateMemory;
  final ValueChanged<PersonMemoryItem> onEditPerson;
  final ValueChanged<RuleMemoryItem> onEditRule;
  final ValueChanged<PlanMemoryItem> onEditPlan;
  final ValueChanged<CommitmentMemoryItem> onEditCommitment;
  final void Function(MemoryLayer layer, String id, String label)
  onDeactivateStructuredMemory;

  @override
  Widget build(BuildContext context) {
    switch (state.selectedLayer) {
      case MemoryLayer.longTerm:
        return SliverList.separated(
          itemCount: state.memories.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final memory = state.memories[index];
            return _MemoryTile(
              memory: memory,
              onEdit: () => onEditMemory(memory),
              onDeactivate: memory.active
                  ? () => onDeactivateMemory(memory)
                  : null,
            );
          },
        );
      case MemoryLayer.people:
        return SliverList.separated(
          itemCount: state.people.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final person = state.people[index];
            return _PersonMemoryTile(
              person: person,
              onEdit: () => onEditPerson(person),
              onDeactivate: person.active
                  ? () => onDeactivateStructuredMemory(
                      MemoryLayer.people,
                      person.id,
                      'person',
                    )
                  : null,
            );
          },
        );
      case MemoryLayer.rules:
        return SliverList.separated(
          itemCount: state.rules.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final rule = state.rules[index];
            return _RuleMemoryTile(
              rule: rule,
              onEdit: () => onEditRule(rule),
              onDeactivate: rule.active
                  ? () => onDeactivateStructuredMemory(
                      MemoryLayer.rules,
                      rule.id,
                      'rule',
                    )
                  : null,
            );
          },
        );
      case MemoryLayer.plans:
        return SliverList.separated(
          itemCount: state.plans.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final plan = state.plans[index];
            return _PlanMemoryTile(
              plan: plan,
              onEdit: () => onEditPlan(plan),
              onDeactivate: plan.active
                  ? () => onDeactivateStructuredMemory(
                      MemoryLayer.plans,
                      plan.id,
                      'plan',
                    )
                  : null,
            );
          },
        );
      case MemoryLayer.commitments:
        return SliverList.separated(
          itemCount: state.commitments.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final commitment = state.commitments[index];
            return _CommitmentMemoryTile(
              commitment: commitment,
              onEdit: () => onEditCommitment(commitment),
              onDeactivate: commitment.active
                  ? () => onDeactivateStructuredMemory(
                      MemoryLayer.commitments,
                      commitment.id,
                      'commitment',
                    )
                  : null,
            );
          },
        );
    }
  }
}

class _MemoryTile extends StatelessWidget {
  const _MemoryTile({
    required this.memory,
    required this.onEdit,
    required this.onDeactivate,
  });

  final MemoryItem memory;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: memory.active
            ? scheme.primaryContainer
            : scheme.surfaceContainerHighest,
        foregroundColor: memory.active
            ? scheme.onPrimaryContainer
            : scheme.onSurfaceVariant,
        child: Icon(_iconForType(memory.memoryType), size: 20),
      ),
      title: Text(memory.content),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Wrap(
          spacing: 8,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            _MemoryMetaChip(label: memory.memoryType.label),
            _MemoryMetaChip(label: 'Importance ${memory.importance}'),
            if (!memory.active) const _MemoryMetaChip(label: 'Inactive'),
          ],
        ),
      ),
      trailing: PopupMenuButton<_MemoryAction>(
        tooltip: 'Memory actions',
        onSelected: (action) {
          switch (action) {
            case _MemoryAction.edit:
              onEdit();
            case _MemoryAction.deactivate:
              onDeactivate?.call();
          }
        },
        itemBuilder: (context) => [
          const PopupMenuItem(
            value: _MemoryAction.edit,
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.edit_outlined),
              title: Text('Edit'),
            ),
          ),
          if (onDeactivate != null)
            const PopupMenuItem(
              value: _MemoryAction.deactivate,
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.visibility_off_outlined),
                title: Text('Deactivate'),
              ),
            ),
        ],
      ),
      onTap: onEdit,
      textColor: memory.active ? null : scheme.onSurfaceVariant,
      titleTextStyle: theme.textTheme.bodyLarge?.copyWith(
        color: memory.active ? scheme.onSurface : scheme.onSurfaceVariant,
      ),
    );
  }

  IconData _iconForType(MemoryType type) {
    switch (type) {
      case MemoryType.fact:
        return Icons.badge_outlined;
      case MemoryType.preference:
        return Icons.tune_rounded;
      case MemoryType.event:
        return Icons.event_note_outlined;
    }
  }
}

class _PersonMemoryTile extends StatelessWidget {
  const _PersonMemoryTile({
    required this.person,
    required this.onEdit,
    required this.onDeactivate,
  });

  final PersonMemoryItem person;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    return _StructuredMemoryTile(
      icon: Icons.person_outline_rounded,
      active: person.active,
      title: person.displayName,
      subtitle: person.summary ?? person.relationship ?? 'Person memory',
      chips: [
        if (person.relationship != null)
          _MemoryMetaChip(label: person.relationship!.memoryRecordLabel),
        if (person.aliases.isNotEmpty)
          _MemoryMetaChip(label: 'Also ${person.aliases.join(', ')}'),
        _MemoryMetaChip(label: 'Importance ${person.importance}'),
        _MemoryMetaChip(label: person.status.memoryRecordLabel),
        _MemoryMetaChip(label: 'ID ${_shortId(person.id)}'),
        if (!person.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
      onEdit: onEdit,
      onDeactivate: onDeactivate,
    );
  }
}

class _RuleMemoryTile extends StatelessWidget {
  const _RuleMemoryTile({
    required this.rule,
    required this.onEdit,
    required this.onDeactivate,
  });

  final RuleMemoryItem rule;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    return _StructuredMemoryTile(
      icon: Icons.rule_rounded,
      active: rule.active,
      title: rule.title,
      subtitle: rule.ruleText,
      chips: [
        _MemoryMetaChip(label: rule.ruleType.memoryRecordLabel),
        _MemoryMetaChip(label: rule.status.memoryRecordLabel),
        _MemoryMetaChip(label: 'Priority ${rule.priority}'),
        if (rule.triggerKeywords.isNotEmpty)
          _MemoryMetaChip(label: rule.triggerKeywords.join(', ')),
        if (!rule.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
      onEdit: onEdit,
      onDeactivate: onDeactivate,
    );
  }
}

class _PlanMemoryTile extends StatelessWidget {
  const _PlanMemoryTile({
    required this.plan,
    required this.onEdit,
    required this.onDeactivate,
  });

  final PlanMemoryItem plan;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    return _StructuredMemoryTile(
      icon: Icons.flag_outlined,
      active: plan.active,
      title: plan.title,
      subtitle: plan.desiredOutcome ?? plan.description ?? 'Plan memory',
      chips: [
        _MemoryMetaChip(label: plan.planType.memoryRecordLabel),
        _MemoryMetaChip(label: plan.status.memoryRecordLabel),
        _MemoryMetaChip(label: 'Priority ${plan.priority}'),
        if (plan.targetDate != null)
          _MemoryMetaChip(label: 'Target ${_shortDate(plan.targetDate!)}'),
        if (plan.primaryEntityId != null)
          _MemoryMetaChip(label: 'Person ${_shortId(plan.primaryEntityId!)}'),
        if (!plan.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
      onEdit: onEdit,
      onDeactivate: onDeactivate,
    );
  }
}

class _CommitmentMemoryTile extends StatelessWidget {
  const _CommitmentMemoryTile({
    required this.commitment,
    required this.onEdit,
    required this.onDeactivate,
  });

  final CommitmentMemoryItem commitment;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    return _StructuredMemoryTile(
      icon: Icons.check_circle_outline_rounded,
      active: commitment.active,
      title: commitment.title,
      subtitle: commitment.commitmentText,
      chips: [
        _MemoryMetaChip(label: commitment.commitmentType.memoryRecordLabel),
        _MemoryMetaChip(label: commitment.status.memoryRecordLabel),
        _MemoryMetaChip(label: 'Priority ${commitment.priority}'),
        if (commitment.dueAt != null)
          _MemoryMetaChip(label: 'Due ${_shortDate(commitment.dueAt!)}'),
        if (commitment.planId != null)
          _MemoryMetaChip(label: 'Plan ${_shortId(commitment.planId!)}'),
        if (commitment.entityId != null)
          _MemoryMetaChip(label: 'Person ${_shortId(commitment.entityId!)}'),
        if (!commitment.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
      onEdit: onEdit,
      onDeactivate: onDeactivate,
    );
  }
}

class _StructuredMemoryTile extends StatelessWidget {
  const _StructuredMemoryTile({
    required this.icon,
    required this.active,
    required this.title,
    required this.subtitle,
    required this.chips,
    required this.onEdit,
    required this.onDeactivate,
  });

  final IconData icon;
  final bool active;
  final String title;
  final String subtitle;
  final List<Widget> chips;
  final VoidCallback onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: active
            ? scheme.primaryContainer
            : scheme.surfaceContainerHighest,
        foregroundColor: active
            ? scheme.onPrimaryContainer
            : scheme.onSurfaceVariant,
        child: Icon(icon, size: 20),
      ),
      title: Text(title),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              subtitle,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: active ? scheme.onSurfaceVariant : scheme.outline,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: chips,
            ),
          ],
        ),
      ),
      textColor: active ? null : scheme.onSurfaceVariant,
      titleTextStyle: theme.textTheme.bodyLarge?.copyWith(
        color: active ? scheme.onSurface : scheme.onSurfaceVariant,
      ),
      trailing: PopupMenuButton<_MemoryAction>(
        tooltip: 'Memory actions',
        onSelected: (action) {
          switch (action) {
            case _MemoryAction.edit:
              onEdit();
            case _MemoryAction.deactivate:
              onDeactivate?.call();
          }
        },
        itemBuilder: (context) => [
          const PopupMenuItem(
            value: _MemoryAction.edit,
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.edit_outlined),
              title: Text('Edit'),
            ),
          ),
          if (onDeactivate != null)
            const PopupMenuItem(
              value: _MemoryAction.deactivate,
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.visibility_off_outlined),
                title: Text('Deactivate'),
              ),
            ),
        ],
      ),
      onTap: onEdit,
    );
  }
}

class _MemoryMetaChip extends StatelessWidget {
  const _MemoryMetaChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Text(
          label,
          style: theme.textTheme.labelSmall?.copyWith(
            color: scheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _MemoryEmptyState extends StatelessWidget {
  const _MemoryEmptyState({required this.layer, required this.activeOnly});

  final MemoryLayer layer;
  final bool activeOnly;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.psychology_alt_outlined,
              color: scheme.onSurfaceVariant,
              size: 40,
            ),
            const SizedBox(height: 16),
            Text(_emptyTitle, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              _emptyBody,
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

  String get _emptyTitle {
    switch (layer) {
      case MemoryLayer.longTerm:
        return activeOnly ? 'No active notes yet' : 'No notes found';
      case MemoryLayer.people:
        return activeOnly ? 'No active people yet' : 'No people found';
      case MemoryLayer.rules:
        return activeOnly ? 'No active rules yet' : 'No rules found';
      case MemoryLayer.plans:
        return activeOnly ? 'No active plans yet' : 'No plans found';
      case MemoryLayer.commitments:
        return activeOnly ? 'No open commitments yet' : 'No commitments found';
    }
  }

  String get _emptyBody {
    switch (layer) {
      case MemoryLayer.longTerm:
        return 'Important facts, preferences, and events will appear here.';
      case MemoryLayer.people:
        return 'People Rex knows about will appear as their own layer.';
      case MemoryLayer.rules:
        return 'Personal rules Rex should enforce will appear here.';
      case MemoryLayer.plans:
        return 'Active goals and plans will appear here.';
      case MemoryLayer.commitments:
        return 'Promises, deadlines, and follow-ups will appear here.';
    }
  }
}

String _shortDate(DateTime value) {
  final local = value.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  return '$month/$day/${local.year}';
}

String _shortId(String value) {
  if (value.length <= 8) {
    return value;
  }
  return value.substring(0, 8);
}

class _StructuredEditDialog extends StatefulWidget {
  const _StructuredEditDialog({
    required this.title,
    required this.primaryLabel,
    required this.primaryValue,
    required this.detailLabel,
    required this.importanceLabel,
    required this.importance,
    required this.status,
    required this.active,
    this.detailValue,
    this.extraLabel,
    this.extraValue,
    this.aliasesValue,
  });

  final String title;
  final String primaryLabel;
  final String primaryValue;
  final String detailLabel;
  final String? detailValue;
  final String? extraLabel;
  final String? extraValue;
  final String? aliasesValue;
  final String importanceLabel;
  final int importance;
  final String status;
  final bool active;

  @override
  State<_StructuredEditDialog> createState() => _StructuredEditDialogState();
}

class _StructuredEditDialogState extends State<_StructuredEditDialog> {
  late final TextEditingController _primaryController;
  late final TextEditingController _detailController;
  late final TextEditingController _extraController;
  late final TextEditingController _aliasesController;
  late final TextEditingController _statusController;
  late double _importance;
  late bool _active;

  @override
  void initState() {
    super.initState();
    _primaryController = TextEditingController(text: widget.primaryValue);
    _detailController = TextEditingController(text: widget.detailValue ?? '');
    _extraController = TextEditingController(text: widget.extraValue ?? '');
    _aliasesController = TextEditingController(text: widget.aliasesValue ?? '');
    _statusController = TextEditingController(text: widget.status);
    _importance = widget.importance.toDouble();
    _active = widget.active;
  }

  @override
  void dispose() {
    _primaryController.dispose();
    _detailController.dispose();
    _extraController.dispose();
    _aliasesController.dispose();
    _statusController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _primaryController,
              decoration: InputDecoration(labelText: widget.primaryLabel),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _detailController,
              minLines: 2,
              maxLines: 5,
              decoration: InputDecoration(
                labelText: widget.detailLabel,
                border: const OutlineInputBorder(),
              ),
            ),
            if (widget.extraLabel != null) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _extraController,
                minLines: 1,
                maxLines: 4,
                decoration: InputDecoration(labelText: widget.extraLabel),
              ),
            ],
            if (widget.aliasesValue != null) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _aliasesController,
                decoration: const InputDecoration(
                  labelText: 'Aliases',
                  helperText: 'Comma-separated',
                ),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: _statusController,
              decoration: const InputDecoration(labelText: 'Status'),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Text(widget.importanceLabel),
                Expanded(
                  child: Slider(
                    value: _importance,
                    min: 1,
                    max: 5,
                    divisions: 4,
                    label: _importance.round().toString(),
                    onChanged: (value) => setState(() => _importance = value),
                  ),
                ),
                Text(_importance.round().toString()),
              ],
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Active'),
              value: _active,
              onChanged: (value) => setState(() => _active = value),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }

  void _submit() {
    final primary = _primaryController.text.trim();
    if (primary.isEmpty) {
      return;
    }

    Navigator.of(context).pop(
      _StructuredEditResult(
        primary: primary,
        detail: _nullableText(_detailController.text),
        extra: _nullableText(_extraController.text),
        aliases: _splitCommaText(_aliasesController.text),
        importance: _importance.round(),
        status: _statusController.text.trim(),
        active: _active,
      ),
    );
  }
}

class _MemoryEditDialog extends StatefulWidget {
  const _MemoryEditDialog({required this.memory});

  final MemoryItem memory;

  @override
  State<_MemoryEditDialog> createState() => _MemoryEditDialogState();
}

class _MemoryEditDialogState extends State<_MemoryEditDialog> {
  late final TextEditingController _contentController;
  late MemoryType _memoryType;
  late double _importance;
  late bool _active;

  @override
  void initState() {
    super.initState();
    _contentController = TextEditingController(text: widget.memory.content);
    _memoryType = widget.memory.memoryType;
    _importance = widget.memory.importance.toDouble();
    _active = widget.memory.active;
  }

  @override
  void dispose() {
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit memory'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<MemoryType>(
              initialValue: _memoryType,
              decoration: const InputDecoration(labelText: 'Type'),
              items: MemoryType.values
                  .map(
                    (type) =>
                        DropdownMenuItem(value: type, child: Text(type.label)),
                  )
                  .toList(growable: false),
              onChanged: (value) {
                if (value != null) {
                  setState(() => _memoryType = value);
                }
              },
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _contentController,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Memory',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Importance'),
                Expanded(
                  child: Slider(
                    value: _importance,
                    min: 1,
                    max: 5,
                    divisions: 4,
                    label: _importance.round().toString(),
                    onChanged: (value) => setState(() => _importance = value),
                  ),
                ),
                Text(_importance.round().toString()),
              ],
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Active'),
              value: _active,
              onChanged: (value) => setState(() => _active = value),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }

  void _submit() {
    final content = _contentController.text.trim();
    if (content.isEmpty) {
      return;
    }

    Navigator.of(context).pop(
      _MemoryEditResult(
        memoryType: _memoryType,
        content: content,
        importance: _importance.round(),
        active: _active,
      ),
    );
  }
}

class _MemoryEditResult {
  const _MemoryEditResult({
    required this.memoryType,
    required this.content,
    required this.importance,
    required this.active,
  });

  final MemoryType memoryType;
  final String content;
  final int importance;
  final bool active;
}

enum _MemoryAction { edit, deactivate }

class _StructuredEditResult {
  const _StructuredEditResult({
    required this.primary,
    required this.importance,
    required this.status,
    required this.active,
    this.detail,
    this.extra,
    this.aliases = const [],
  });

  final String primary;
  final String? detail;
  final String? extra;
  final List<String> aliases;
  final int importance;
  final String status;
  final bool active;

  List<String> get extraList => _splitCommaText(extra ?? '');
}

String? _nullableText(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}

List<String> _splitCommaText(String value) {
  return value
      .split(',')
      .map((item) => item.trim())
      .where((item) => item.isNotEmpty)
      .toList(growable: false);
}
