import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/accountability/data/accountability_api.dart';
import 'package:rex/features/accountability/data/accountability_models.dart';

final accountabilityProvider =
    NotifierProvider<AccountabilityController, AccountabilityState>(
      AccountabilityController.new,
    );

class AccountabilityState {
  const AccountabilityState({
    this.overview,
    this.isLoading = false,
    this.errorMessage,
  });

  final AccountabilityOverview? overview;
  final bool isLoading;
  final String? errorMessage;

  AccountabilityState copyWith({
    AccountabilityOverview? overview,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return AccountabilityState(
      overview: overview ?? this.overview,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

class AccountabilityController extends Notifier<AccountabilityState> {
  @override
  AccountabilityState build() => const AccountabilityState();

  Future<void> loadOverview() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final overview = await ref.read(accountabilityApiProvider).getOverview();
      state = state.copyWith(
        overview: overview,
        isLoading: false,
        clearError: true,
      );
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
    }
  }
}
