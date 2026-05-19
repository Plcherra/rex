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
  });

  final MemoryState state;
  final ValueChanged<MemoryItem> onEditMemory;
  final ValueChanged<MemoryItem> onDeactivateMemory;

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
          itemBuilder: (context, index) =>
              _PersonMemoryTile(person: state.people[index]),
        );
      case MemoryLayer.rules:
        return SliverList.separated(
          itemCount: state.rules.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) =>
              _RuleMemoryTile(rule: state.rules[index]),
        );
      case MemoryLayer.plans:
        return SliverList.separated(
          itemCount: state.plans.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) =>
              _PlanMemoryTile(plan: state.plans[index]),
        );
      case MemoryLayer.commitments:
        return SliverList.separated(
          itemCount: state.commitments.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) =>
              _CommitmentMemoryTile(commitment: state.commitments[index]),
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
  const _PersonMemoryTile({required this.person});

  final PersonMemoryItem person;

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
        if (!person.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
    );
  }
}

class _RuleMemoryTile extends StatelessWidget {
  const _RuleMemoryTile({required this.rule});

  final RuleMemoryItem rule;

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
        if (!rule.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
    );
  }
}

class _PlanMemoryTile extends StatelessWidget {
  const _PlanMemoryTile({required this.plan});

  final PlanMemoryItem plan;

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
        if (!plan.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
    );
  }
}

class _CommitmentMemoryTile extends StatelessWidget {
  const _CommitmentMemoryTile({required this.commitment});

  final CommitmentMemoryItem commitment;

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
        if (!commitment.active) const _MemoryMetaChip(label: 'Inactive'),
      ],
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
  });

  final IconData icon;
  final bool active;
  final String title;
  final String subtitle;
  final List<Widget> chips;

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
