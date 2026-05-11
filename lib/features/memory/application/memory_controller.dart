import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/memory/data/memory_api.dart';
import 'package:rex/features/memory/data/memory_models.dart';

final memoryProvider = NotifierProvider<MemoryController, MemoryState>(
  MemoryController.new,
);

class MemoryState {
  const MemoryState({
    this.memories = const [],
    this.selectedType,
    this.activeOnly = true,
    this.isLoading = false,
    this.isSaving = false,
    this.errorMessage,
  });

  final List<MemoryItem> memories;
  final MemoryType? selectedType;
  final bool activeOnly;
  final bool isLoading;
  final bool isSaving;
  final String? errorMessage;

  MemoryState copyWith({
    List<MemoryItem>? memories,
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
      selectedType: clearSelectedType
          ? null
          : selectedType ?? this.selectedType,
      activeOnly: activeOnly ?? this.activeOnly,
      isLoading: isLoading ?? this.isLoading,
      isSaving: isSaving ?? this.isSaving,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

class MemoryController extends Notifier<MemoryState> {
  @override
  MemoryState build() => const MemoryState();

  Future<void> loadMemories({MemoryType? memoryType, bool? activeOnly}) async {
    final nextActiveOnly = activeOnly ?? state.activeOnly;
    state = state.copyWith(
      selectedType: memoryType,
      clearSelectedType: memoryType == null,
      activeOnly: nextActiveOnly,
      isLoading: true,
      clearError: true,
    );

    try {
      final memories = await ref
          .read(memoryApiProvider)
          .getMemories(
            memoryType: memoryType,
            active: nextActiveOnly ? true : null,
          );
      state = state.copyWith(
        memories: memories,
        isLoading: false,
        clearError: true,
      );
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
