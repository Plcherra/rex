import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/memory/data/memory_api.dart';
import 'package:rex/features/memory/data/memory_models.dart';

final memoryProvider = NotifierProvider<MemoryController, MemoryState>(
  MemoryController.new,
);

class MemoryState {
  const MemoryState({
    this.memories = const [],
    this.people = const [],
    this.rules = const [],
    this.plans = const [],
    this.commitments = const [],
    this.selectedLayer = MemoryLayer.longTerm,
    this.selectedType,
    this.activeOnly = true,
    this.isLoading = false,
    this.isSaving = false,
    this.errorMessage,
  });

  final List<MemoryItem> memories;
  final List<PersonMemoryItem> people;
  final List<RuleMemoryItem> rules;
  final List<PlanMemoryItem> plans;
  final List<CommitmentMemoryItem> commitments;
  final MemoryLayer selectedLayer;
  final MemoryType? selectedType;
  final bool activeOnly;
  final bool isLoading;
  final bool isSaving;
  final String? errorMessage;

  MemoryState copyWith({
    List<MemoryItem>? memories,
    List<PersonMemoryItem>? people,
    List<RuleMemoryItem>? rules,
    List<PlanMemoryItem>? plans,
    List<CommitmentMemoryItem>? commitments,
    MemoryLayer? selectedLayer,
    MemoryType? selectedType,
    bool clearSelectedType = false,
    bool? activeOnly,
    bool? isLoading,
    bool? isSaving,
    String? errorMessage,
    bool clearError = false,
  }) {
    return MemoryState(
      memories: memories ?? this.memories,
      people: people ?? this.people,
      rules: rules ?? this.rules,
      plans: plans ?? this.plans,
      commitments: commitments ?? this.commitments,
      selectedLayer: selectedLayer ?? this.selectedLayer,
      selectedType: clearSelectedType
          ? null
          : selectedType ?? this.selectedType,
      activeOnly: activeOnly ?? this.activeOnly,
      isLoading: isLoading ?? this.isLoading,
      isSaving: isSaving ?? this.isSaving,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }

  bool get isSelectedLayerEmpty {
    switch (selectedLayer) {
      case MemoryLayer.longTerm:
        return memories.isEmpty;
      case MemoryLayer.people:
        return people.isEmpty;
      case MemoryLayer.rules:
        return rules.isEmpty;
      case MemoryLayer.plans:
        return plans.isEmpty;
      case MemoryLayer.commitments:
        return commitments.isEmpty;
    }
  }
}

class MemoryController extends Notifier<MemoryState> {
  @override
  MemoryState build() => const MemoryState();

  Future<void> loadMemories({
    MemoryLayer? layer,
    MemoryType? memoryType,
    bool? activeOnly,
  }) async {
    final nextLayer = layer ?? state.selectedLayer;
    final nextActiveOnly = activeOnly ?? state.activeOnly;
    state = state.copyWith(
      selectedLayer: nextLayer,
      selectedType: memoryType,
      clearSelectedType:
          nextLayer != MemoryLayer.longTerm || memoryType == null,
      activeOnly: nextActiveOnly,
      isLoading: true,
      clearError: true,
    );

    try {
      final api = ref.read(memoryApiProvider);
      switch (nextLayer) {
        case MemoryLayer.longTerm:
          final memories = await api.getMemories(
            memoryType: memoryType,
            active: nextActiveOnly ? true : null,
          );
          state = state.copyWith(
            memories: memories,
            isLoading: false,
            clearError: true,
          );
        case MemoryLayer.people:
          final people = await api.getPeople(
            active: nextActiveOnly ? true : null,
          );
          state = state.copyWith(
            people: people,
            isLoading: false,
            clearError: true,
          );
        case MemoryLayer.rules:
          final rules = await api.getRules(
            active: nextActiveOnly ? true : null,
          );
          state = state.copyWith(
            rules: rules,
            isLoading: false,
            clearError: true,
          );
        case MemoryLayer.plans:
          final plans = await api.getPlans(
            active: nextActiveOnly ? true : null,
          );
          state = state.copyWith(
            plans: plans,
            isLoading: false,
            clearError: true,
          );
        case MemoryLayer.commitments:
          final commitments = await api.getCommitments(
            active: nextActiveOnly ? true : null,
          );
          state = state.copyWith(
            commitments: commitments,
            isLoading: false,
            clearError: true,
          );
      }
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
    }
  }

  Future<bool> updateMemory(
    String memoryId, {
    MemoryType? memoryType,
    String? content,
    int? importance,
    bool? active,
  }) async {
    state = state.copyWith(isSaving: true, clearError: true);

    try {
      final memory = await ref
          .read(memoryApiProvider)
          .updateMemory(
            memoryId,
            memoryType: memoryType,
            content: content,
            importance: importance,
            active: active,
          );
      final updatedMemories = state.memories
          .map((item) => item.id == memoryId ? memory : item)
          .where(_matchesCurrentFilters)
          .toList(growable: false);
      state = state.copyWith(
        memories: updatedMemories,
        isSaving: false,
        clearError: true,
      );
      return true;
    } on Object catch (error) {
      state = state.copyWith(isSaving: false, errorMessage: error.toString());
      return false;
    }
  }

  Future<bool> deactivateMemory(String memoryId) async {
    final previousMemories = state.memories;
    state = state.copyWith(
      memories: state.activeOnly
          ? previousMemories
                .where((memory) => memory.id != memoryId)
                .toList(growable: false)
          : previousMemories
                .map(
                  (memory) => memory.id == memoryId
                      ? memory.copyWith(active: false)
                      : memory,
                )
                .toList(growable: false),
      isSaving: true,
      clearError: true,
    );

    try {
      await ref.read(memoryApiProvider).deactivateMemory(memoryId);
      state = state.copyWith(isSaving: false, clearError: true);
      return true;
    } on Object catch (error) {
      state = state.copyWith(
        memories: previousMemories,
        isSaving: false,
        errorMessage: error.toString(),
      );
      return false;
    }
  }

  bool _matchesCurrentFilters(MemoryItem memory) {
    if (state.activeOnly && !memory.active) {
      return false;
    }
    if (state.selectedType != null && memory.memoryType != state.selectedType) {
      return false;
    }

    return true;
  }
}
