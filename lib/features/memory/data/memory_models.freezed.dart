// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'memory_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$MemoryItem {

 String get id;@JsonKey(name: 'memory_type') MemoryType get memoryType; String get content;@JsonKey(name: 'source_conversation_id') String? get sourceConversationId;@JsonKey(name: 'source_message_id') String? get sourceMessageId; int get importance; bool get active;@JsonKey(name: 'created_at') DateTime? get createdAt;@JsonKey(name: 'updated_at') DateTime? get updatedAt;@JsonKey(name: 'last_accessed_at') DateTime? get lastAccessedAt;
/// Create a copy of MemoryItem
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$MemoryItemCopyWith<MemoryItem> get copyWith => _$MemoryItemCopyWithImpl<MemoryItem>(this as MemoryItem, _$identity);

  /// Serializes this MemoryItem to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is MemoryItem&&(identical(other.id, id) || other.id == id)&&(identical(other.memoryType, memoryType) || other.memoryType == memoryType)&&(identical(other.content, content) || other.content == content)&&(identical(other.sourceConversationId, sourceConversationId) || other.sourceConversationId == sourceConversationId)&&(identical(other.sourceMessageId, sourceMessageId) || other.sourceMessageId == sourceMessageId)&&(identical(other.importance, importance) || other.importance == importance)&&(identical(other.active, active) || other.active == active)&&(identical(other.createdAt, createdAt) || other.createdAt == createdAt)&&(identical(other.updatedAt, updatedAt) || other.updatedAt == updatedAt)&&(identical(other.lastAccessedAt, lastAccessedAt) || other.lastAccessedAt == lastAccessedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,memoryType,content,sourceConversationId,sourceMessageId,importance,active,createdAt,updatedAt,lastAccessedAt);

@override
String toString() {
  return 'MemoryItem(id: $id, memoryType: $memoryType, content: $content, sourceConversationId: $sourceConversationId, sourceMessageId: $sourceMessageId, importance: $importance, active: $active, createdAt: $createdAt, updatedAt: $updatedAt, lastAccessedAt: $lastAccessedAt)';
}


}

/// @nodoc
abstract mixin class $MemoryItemCopyWith<$Res>  {
  factory $MemoryItemCopyWith(MemoryItem value, $Res Function(MemoryItem) _then) = _$MemoryItemCopyWithImpl;
@useResult
$Res call({
 String id,@JsonKey(name: 'memory_type') MemoryType memoryType, String content,@JsonKey(name: 'source_conversation_id') String? sourceConversationId,@JsonKey(name: 'source_message_id') String? sourceMessageId, int importance, bool active,@JsonKey(name: 'created_at') DateTime? createdAt,@JsonKey(name: 'updated_at') DateTime? updatedAt,@JsonKey(name: 'last_accessed_at') DateTime? lastAccessedAt
});




}
/// @nodoc
class _$MemoryItemCopyWithImpl<$Res>
    implements $MemoryItemCopyWith<$Res> {
  _$MemoryItemCopyWithImpl(this._self, this._then);

  final MemoryItem _self;
  final $Res Function(MemoryItem) _then;

/// Create a copy of MemoryItem
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? memoryType = null,Object? content = null,Object? sourceConversationId = freezed,Object? sourceMessageId = freezed,Object? importance = null,Object? active = null,Object? createdAt = freezed,Object? updatedAt = freezed,Object? lastAccessedAt = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,memoryType: null == memoryType ? _self.memoryType : memoryType // ignore: cast_nullable_to_non_nullable
as MemoryType,content: null == content ? _self.content : content // ignore: cast_nullable_to_non_nullable
as String,sourceConversationId: freezed == sourceConversationId ? _self.sourceConversationId : sourceConversationId // ignore: cast_nullable_to_non_nullable
as String?,sourceMessageId: freezed == sourceMessageId ? _self.sourceMessageId : sourceMessageId // ignore: cast_nullable_to_non_nullable
as String?,importance: null == importance ? _self.importance : importance // ignore: cast_nullable_to_non_nullable
as int,active: null == active ? _self.active : active // ignore: cast_nullable_to_non_nullable
as bool,createdAt: freezed == createdAt ? _self.createdAt : createdAt // ignore: cast_nullable_to_non_nullable
as DateTime?,updatedAt: freezed == updatedAt ? _self.updatedAt : updatedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,lastAccessedAt: freezed == lastAccessedAt ? _self.lastAccessedAt : lastAccessedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}

}


/// Adds pattern-matching-related methods to [MemoryItem].
extension MemoryItemPatterns on MemoryItem {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _MemoryItem value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _MemoryItem() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _MemoryItem value)  $default,){
final _that = this;
switch (_that) {
case _MemoryItem():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _MemoryItem value)?  $default,){
final _that = this;
switch (_that) {
case _MemoryItem() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id, @JsonKey(name: 'memory_type')  MemoryType memoryType,  String content, @JsonKey(name: 'source_conversation_id')  String? sourceConversationId, @JsonKey(name: 'source_message_id')  String? sourceMessageId,  int importance,  bool active, @JsonKey(name: 'created_at')  DateTime? createdAt, @JsonKey(name: 'updated_at')  DateTime? updatedAt, @JsonKey(name: 'last_accessed_at')  DateTime? lastAccessedAt)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _MemoryItem() when $default != null:
return $default(_that.id,_that.memoryType,_that.content,_that.sourceConversationId,_that.sourceMessageId,_that.importance,_that.active,_that.createdAt,_that.updatedAt,_that.lastAccessedAt);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id, @JsonKey(name: 'memory_type')  MemoryType memoryType,  String content, @JsonKey(name: 'source_conversation_id')  String? sourceConversationId, @JsonKey(name: 'source_message_id')  String? sourceMessageId,  int importance,  bool active, @JsonKey(name: 'created_at')  DateTime? createdAt, @JsonKey(name: 'updated_at')  DateTime? updatedAt, @JsonKey(name: 'last_accessed_at')  DateTime? lastAccessedAt)  $default,) {final _that = this;
switch (_that) {
case _MemoryItem():
return $default(_that.id,_that.memoryType,_that.content,_that.sourceConversationId,_that.sourceMessageId,_that.importance,_that.active,_that.createdAt,_that.updatedAt,_that.lastAccessedAt);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id, @JsonKey(name: 'memory_type')  MemoryType memoryType,  String content, @JsonKey(name: 'source_conversation_id')  String? sourceConversationId, @JsonKey(name: 'source_message_id')  String? sourceMessageId,  int importance,  bool active, @JsonKey(name: 'created_at')  DateTime? createdAt, @JsonKey(name: 'updated_at')  DateTime? updatedAt, @JsonKey(name: 'last_accessed_at')  DateTime? lastAccessedAt)?  $default,) {final _that = this;
switch (_that) {
case _MemoryItem() when $default != null:
return $default(_that.id,_that.memoryType,_that.content,_that.sourceConversationId,_that.sourceMessageId,_that.importance,_that.active,_that.createdAt,_that.updatedAt,_that.lastAccessedAt);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _MemoryItem implements MemoryItem {
  const _MemoryItem({required this.id, @JsonKey(name: 'memory_type') required this.memoryType, required this.content, @JsonKey(name: 'source_conversation_id') this.sourceConversationId, @JsonKey(name: 'source_message_id') this.sourceMessageId, required this.importance, required this.active, @JsonKey(name: 'created_at') this.createdAt, @JsonKey(name: 'updated_at') this.updatedAt, @JsonKey(name: 'last_accessed_at') this.lastAccessedAt});
  factory _MemoryItem.fromJson(Map<String, dynamic> json) => _$MemoryItemFromJson(json);

@override final  String id;
@override@JsonKey(name: 'memory_type') final  MemoryType memoryType;
@override final  String content;
@override@JsonKey(name: 'source_conversation_id') final  String? sourceConversationId;
@override@JsonKey(name: 'source_message_id') final  String? sourceMessageId;
@override final  int importance;
@override final  bool active;
@override@JsonKey(name: 'created_at') final  DateTime? createdAt;
@override@JsonKey(name: 'updated_at') final  DateTime? updatedAt;
@override@JsonKey(name: 'last_accessed_at') final  DateTime? lastAccessedAt;

/// Create a copy of MemoryItem
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$MemoryItemCopyWith<_MemoryItem> get copyWith => __$MemoryItemCopyWithImpl<_MemoryItem>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$MemoryItemToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _MemoryItem&&(identical(other.id, id) || other.id == id)&&(identical(other.memoryType, memoryType) || other.memoryType == memoryType)&&(identical(other.content, content) || other.content == content)&&(identical(other.sourceConversationId, sourceConversationId) || other.sourceConversationId == sourceConversationId)&&(identical(other.sourceMessageId, sourceMessageId) || other.sourceMessageId == sourceMessageId)&&(identical(other.importance, importance) || other.importance == importance)&&(identical(other.active, active) || other.active == active)&&(identical(other.createdAt, createdAt) || other.createdAt == createdAt)&&(identical(other.updatedAt, updatedAt) || other.updatedAt == updatedAt)&&(identical(other.lastAccessedAt, lastAccessedAt) || other.lastAccessedAt == lastAccessedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,memoryType,content,sourceConversationId,sourceMessageId,importance,active,createdAt,updatedAt,lastAccessedAt);

@override
String toString() {
  return 'MemoryItem(id: $id, memoryType: $memoryType, content: $content, sourceConversationId: $sourceConversationId, sourceMessageId: $sourceMessageId, importance: $importance, active: $active, createdAt: $createdAt, updatedAt: $updatedAt, lastAccessedAt: $lastAccessedAt)';
}


}

/// @nodoc
abstract mixin class _$MemoryItemCopyWith<$Res> implements $MemoryItemCopyWith<$Res> {
  factory _$MemoryItemCopyWith(_MemoryItem value, $Res Function(_MemoryItem) _then) = __$MemoryItemCopyWithImpl;
@override @useResult
$Res call({
 String id,@JsonKey(name: 'memory_type') MemoryType memoryType, String content,@JsonKey(name: 'source_conversation_id') String? sourceConversationId,@JsonKey(name: 'source_message_id') String? sourceMessageId, int importance, bool active,@JsonKey(name: 'created_at') DateTime? createdAt,@JsonKey(name: 'updated_at') DateTime? updatedAt,@JsonKey(name: 'last_accessed_at') DateTime? lastAccessedAt
});




}
/// @nodoc
class __$MemoryItemCopyWithImpl<$Res>
    implements _$MemoryItemCopyWith<$Res> {
  __$MemoryItemCopyWithImpl(this._self, this._then);

  final _MemoryItem _self;
  final $Res Function(_MemoryItem) _then;

/// Create a copy of MemoryItem
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? memoryType = null,Object? content = null,Object? sourceConversationId = freezed,Object? sourceMessageId = freezed,Object? importance = null,Object? active = null,Object? createdAt = freezed,Object? updatedAt = freezed,Object? lastAccessedAt = freezed,}) {
  return _then(_MemoryItem(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,memoryType: null == memoryType ? _self.memoryType : memoryType // ignore: cast_nullable_to_non_nullable
as MemoryType,content: null == content ? _self.content : content // ignore: cast_nullable_to_non_nullable
as String,sourceConversationId: freezed == sourceConversationId ? _self.sourceConversationId : sourceConversationId // ignore: cast_nullable_to_non_nullable
as String?,sourceMessageId: freezed == sourceMessageId ? _self.sourceMessageId : sourceMessageId // ignore: cast_nullable_to_non_nullable
as String?,importance: null == importance ? _self.importance : importance // ignore: cast_nullable_to_non_nullable
as int,active: null == active ? _self.active : active // ignore: cast_nullable_to_non_nullable
as bool,createdAt: freezed == createdAt ? _self.createdAt : createdAt // ignore: cast_nullable_to_non_nullable
as DateTime?,updatedAt: freezed == updatedAt ? _self.updatedAt : updatedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,lastAccessedAt: freezed == lastAccessedAt ? _self.lastAccessedAt : lastAccessedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}


}

// dart format on
