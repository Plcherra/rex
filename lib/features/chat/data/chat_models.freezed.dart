// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'chat_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$ChatApiMessage {

 String get id;@JsonKey(name: 'conversation_id') String get conversationId; String get role; String get content; DateTime? get timestamp;
/// Create a copy of ChatApiMessage
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ChatApiMessageCopyWith<ChatApiMessage> get copyWith => _$ChatApiMessageCopyWithImpl<ChatApiMessage>(this as ChatApiMessage, _$identity);

  /// Serializes this ChatApiMessage to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ChatApiMessage&&(identical(other.id, id) || other.id == id)&&(identical(other.conversationId, conversationId) || other.conversationId == conversationId)&&(identical(other.role, role) || other.role == role)&&(identical(other.content, content) || other.content == content)&&(identical(other.timestamp, timestamp) || other.timestamp == timestamp));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,conversationId,role,content,timestamp);

@override
String toString() {
  return 'ChatApiMessage(id: $id, conversationId: $conversationId, role: $role, content: $content, timestamp: $timestamp)';
}


}

/// @nodoc
abstract mixin class $ChatApiMessageCopyWith<$Res>  {
  factory $ChatApiMessageCopyWith(ChatApiMessage value, $Res Function(ChatApiMessage) _then) = _$ChatApiMessageCopyWithImpl;
@useResult
$Res call({
 String id,@JsonKey(name: 'conversation_id') String conversationId, String role, String content, DateTime? timestamp
});




}
/// @nodoc
class _$ChatApiMessageCopyWithImpl<$Res>
    implements $ChatApiMessageCopyWith<$Res> {
  _$ChatApiMessageCopyWithImpl(this._self, this._then);

  final ChatApiMessage _self;
  final $Res Function(ChatApiMessage) _then;

/// Create a copy of ChatApiMessage
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? conversationId = null,Object? role = null,Object? content = null,Object? timestamp = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,conversationId: null == conversationId ? _self.conversationId : conversationId // ignore: cast_nullable_to_non_nullable
as String,role: null == role ? _self.role : role // ignore: cast_nullable_to_non_nullable
as String,content: null == content ? _self.content : content // ignore: cast_nullable_to_non_nullable
as String,timestamp: freezed == timestamp ? _self.timestamp : timestamp // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}

}


/// Adds pattern-matching-related methods to [ChatApiMessage].
extension ChatApiMessagePatterns on ChatApiMessage {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _ChatApiMessage value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _ChatApiMessage() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _ChatApiMessage value)  $default,){
final _that = this;
switch (_that) {
case _ChatApiMessage():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _ChatApiMessage value)?  $default,){
final _that = this;
switch (_that) {
case _ChatApiMessage() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id, @JsonKey(name: 'conversation_id')  String conversationId,  String role,  String content,  DateTime? timestamp)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _ChatApiMessage() when $default != null:
return $default(_that.id,_that.conversationId,_that.role,_that.content,_that.timestamp);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id, @JsonKey(name: 'conversation_id')  String conversationId,  String role,  String content,  DateTime? timestamp)  $default,) {final _that = this;
switch (_that) {
case _ChatApiMessage():
return $default(_that.id,_that.conversationId,_that.role,_that.content,_that.timestamp);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id, @JsonKey(name: 'conversation_id')  String conversationId,  String role,  String content,  DateTime? timestamp)?  $default,) {final _that = this;
switch (_that) {
case _ChatApiMessage() when $default != null:
return $default(_that.id,_that.conversationId,_that.role,_that.content,_that.timestamp);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _ChatApiMessage extends ChatApiMessage {
  const _ChatApiMessage({required this.id, @JsonKey(name: 'conversation_id') required this.conversationId, required this.role, required this.content, this.timestamp}): super._();
  factory _ChatApiMessage.fromJson(Map<String, dynamic> json) => _$ChatApiMessageFromJson(json);

@override final  String id;
@override@JsonKey(name: 'conversation_id') final  String conversationId;
@override final  String role;
@override final  String content;
@override final  DateTime? timestamp;

/// Create a copy of ChatApiMessage
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ChatApiMessageCopyWith<_ChatApiMessage> get copyWith => __$ChatApiMessageCopyWithImpl<_ChatApiMessage>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ChatApiMessageToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _ChatApiMessage&&(identical(other.id, id) || other.id == id)&&(identical(other.conversationId, conversationId) || other.conversationId == conversationId)&&(identical(other.role, role) || other.role == role)&&(identical(other.content, content) || other.content == content)&&(identical(other.timestamp, timestamp) || other.timestamp == timestamp));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,conversationId,role,content,timestamp);

@override
String toString() {
  return 'ChatApiMessage(id: $id, conversationId: $conversationId, role: $role, content: $content, timestamp: $timestamp)';
}


}

/// @nodoc
abstract mixin class _$ChatApiMessageCopyWith<$Res> implements $ChatApiMessageCopyWith<$Res> {
  factory _$ChatApiMessageCopyWith(_ChatApiMessage value, $Res Function(_ChatApiMessage) _then) = __$ChatApiMessageCopyWithImpl;
@override @useResult
$Res call({
 String id,@JsonKey(name: 'conversation_id') String conversationId, String role, String content, DateTime? timestamp
});




}
/// @nodoc
class __$ChatApiMessageCopyWithImpl<$Res>
    implements _$ChatApiMessageCopyWith<$Res> {
  __$ChatApiMessageCopyWithImpl(this._self, this._then);

  final _ChatApiMessage _self;
  final $Res Function(_ChatApiMessage) _then;

/// Create a copy of ChatApiMessage
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? conversationId = null,Object? role = null,Object? content = null,Object? timestamp = freezed,}) {
  return _then(_ChatApiMessage(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,conversationId: null == conversationId ? _self.conversationId : conversationId // ignore: cast_nullable_to_non_nullable
as String,role: null == role ? _self.role : role // ignore: cast_nullable_to_non_nullable
as String,content: null == content ? _self.content : content // ignore: cast_nullable_to_non_nullable
as String,timestamp: freezed == timestamp ? _self.timestamp : timestamp // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}


}


/// @nodoc
mixin _$ChatApiResponse {

@JsonKey(name: 'conversation_id') String get conversationId; String get response; List<ChatApiMessage> get messages;@JsonKey(name: 'memory_changes') Map<String, dynamic>? get memoryChanges;
/// Create a copy of ChatApiResponse
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ChatApiResponseCopyWith<ChatApiResponse> get copyWith => _$ChatApiResponseCopyWithImpl<ChatApiResponse>(this as ChatApiResponse, _$identity);

  /// Serializes this ChatApiResponse to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ChatApiResponse&&(identical(other.conversationId, conversationId) || other.conversationId == conversationId)&&(identical(other.response, response) || other.response == response)&&const DeepCollectionEquality().equals(other.messages, messages)&&const DeepCollectionEquality().equals(other.memoryChanges, memoryChanges));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,conversationId,response,const DeepCollectionEquality().hash(messages),const DeepCollectionEquality().hash(memoryChanges));

@override
String toString() {
  return 'ChatApiResponse(conversationId: $conversationId, response: $response, messages: $messages, memoryChanges: $memoryChanges)';
}


}

/// @nodoc
abstract mixin class $ChatApiResponseCopyWith<$Res>  {
  factory $ChatApiResponseCopyWith(ChatApiResponse value, $Res Function(ChatApiResponse) _then) = _$ChatApiResponseCopyWithImpl;
@useResult
$Res call({
@JsonKey(name: 'conversation_id') String conversationId, String response, List<ChatApiMessage> messages,@JsonKey(name: 'memory_changes') Map<String, dynamic>? memoryChanges
});




}
/// @nodoc
class _$ChatApiResponseCopyWithImpl<$Res>
    implements $ChatApiResponseCopyWith<$Res> {
  _$ChatApiResponseCopyWithImpl(this._self, this._then);

  final ChatApiResponse _self;
  final $Res Function(ChatApiResponse) _then;

/// Create a copy of ChatApiResponse
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? conversationId = null,Object? response = null,Object? messages = null,Object? memoryChanges = freezed,}) {
  return _then(_self.copyWith(
conversationId: null == conversationId ? _self.conversationId : conversationId // ignore: cast_nullable_to_non_nullable
as String,response: null == response ? _self.response : response // ignore: cast_nullable_to_non_nullable
as String,messages: null == messages ? _self.messages : messages // ignore: cast_nullable_to_non_nullable
as List<ChatApiMessage>,memoryChanges: freezed == memoryChanges ? _self.memoryChanges : memoryChanges // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>?,
  ));
}

}


/// Adds pattern-matching-related methods to [ChatApiResponse].
extension ChatApiResponsePatterns on ChatApiResponse {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _ChatApiResponse value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _ChatApiResponse() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _ChatApiResponse value)  $default,){
final _that = this;
switch (_that) {
case _ChatApiResponse():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _ChatApiResponse value)?  $default,){
final _that = this;
switch (_that) {
case _ChatApiResponse() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function(@JsonKey(name: 'conversation_id')  String conversationId,  String response,  List<ChatApiMessage> messages, @JsonKey(name: 'memory_changes')  Map<String, dynamic>? memoryChanges)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _ChatApiResponse() when $default != null:
return $default(_that.conversationId,_that.response,_that.messages,_that.memoryChanges);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function(@JsonKey(name: 'conversation_id')  String conversationId,  String response,  List<ChatApiMessage> messages, @JsonKey(name: 'memory_changes')  Map<String, dynamic>? memoryChanges)  $default,) {final _that = this;
switch (_that) {
case _ChatApiResponse():
return $default(_that.conversationId,_that.response,_that.messages,_that.memoryChanges);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function(@JsonKey(name: 'conversation_id')  String conversationId,  String response,  List<ChatApiMessage> messages, @JsonKey(name: 'memory_changes')  Map<String, dynamic>? memoryChanges)?  $default,) {final _that = this;
switch (_that) {
case _ChatApiResponse() when $default != null:
return $default(_that.conversationId,_that.response,_that.messages,_that.memoryChanges);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _ChatApiResponse implements ChatApiResponse {
  const _ChatApiResponse({@JsonKey(name: 'conversation_id') required this.conversationId, required this.response, required final  List<ChatApiMessage> messages, @JsonKey(name: 'memory_changes') final  Map<String, dynamic>? memoryChanges}): _messages = messages,_memoryChanges = memoryChanges;
  factory _ChatApiResponse.fromJson(Map<String, dynamic> json) => _$ChatApiResponseFromJson(json);

@override@JsonKey(name: 'conversation_id') final  String conversationId;
@override final  String response;
 final  List<ChatApiMessage> _messages;
@override List<ChatApiMessage> get messages {
  if (_messages is EqualUnmodifiableListView) return _messages;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_messages);
}

 final  Map<String, dynamic>? _memoryChanges;
@override@JsonKey(name: 'memory_changes') Map<String, dynamic>? get memoryChanges {
  final value = _memoryChanges;
  if (value == null) return null;
  if (_memoryChanges is EqualUnmodifiableMapView) return _memoryChanges;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(value);
}


/// Create a copy of ChatApiResponse
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ChatApiResponseCopyWith<_ChatApiResponse> get copyWith => __$ChatApiResponseCopyWithImpl<_ChatApiResponse>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ChatApiResponseToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _ChatApiResponse&&(identical(other.conversationId, conversationId) || other.conversationId == conversationId)&&(identical(other.response, response) || other.response == response)&&const DeepCollectionEquality().equals(other._messages, _messages)&&const DeepCollectionEquality().equals(other._memoryChanges, _memoryChanges));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,conversationId,response,const DeepCollectionEquality().hash(_messages),const DeepCollectionEquality().hash(_memoryChanges));

@override
String toString() {
  return 'ChatApiResponse(conversationId: $conversationId, response: $response, messages: $messages, memoryChanges: $memoryChanges)';
}


}

/// @nodoc
abstract mixin class _$ChatApiResponseCopyWith<$Res> implements $ChatApiResponseCopyWith<$Res> {
  factory _$ChatApiResponseCopyWith(_ChatApiResponse value, $Res Function(_ChatApiResponse) _then) = __$ChatApiResponseCopyWithImpl;
@override @useResult
$Res call({
@JsonKey(name: 'conversation_id') String conversationId, String response, List<ChatApiMessage> messages,@JsonKey(name: 'memory_changes') Map<String, dynamic>? memoryChanges
});




}
/// @nodoc
class __$ChatApiResponseCopyWithImpl<$Res>
    implements _$ChatApiResponseCopyWith<$Res> {
  __$ChatApiResponseCopyWithImpl(this._self, this._then);

  final _ChatApiResponse _self;
  final $Res Function(_ChatApiResponse) _then;

/// Create a copy of ChatApiResponse
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? conversationId = null,Object? response = null,Object? messages = null,Object? memoryChanges = freezed,}) {
  return _then(_ChatApiResponse(
conversationId: null == conversationId ? _self.conversationId : conversationId // ignore: cast_nullable_to_non_nullable
as String,response: null == response ? _self.response : response // ignore: cast_nullable_to_non_nullable
as String,messages: null == messages ? _self._messages : messages // ignore: cast_nullable_to_non_nullable
as List<ChatApiMessage>,memoryChanges: freezed == memoryChanges ? _self._memoryChanges : memoryChanges // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>?,
  ));
}


}


/// @nodoc
mixin _$Conversation {

 String get id; String? get title; DateTime? get timestamp;@JsonKey(name: 'last_message') ChatApiMessage? get lastMessage;
/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ConversationCopyWith<Conversation> get copyWith => _$ConversationCopyWithImpl<Conversation>(this as Conversation, _$identity);

  /// Serializes this Conversation to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is Conversation&&(identical(other.id, id) || other.id == id)&&(identical(other.title, title) || other.title == title)&&(identical(other.timestamp, timestamp) || other.timestamp == timestamp)&&(identical(other.lastMessage, lastMessage) || other.lastMessage == lastMessage));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,title,timestamp,lastMessage);

@override
String toString() {
  return 'Conversation(id: $id, title: $title, timestamp: $timestamp, lastMessage: $lastMessage)';
}


}

/// @nodoc
abstract mixin class $ConversationCopyWith<$Res>  {
  factory $ConversationCopyWith(Conversation value, $Res Function(Conversation) _then) = _$ConversationCopyWithImpl;
@useResult
$Res call({
 String id, String? title, DateTime? timestamp,@JsonKey(name: 'last_message') ChatApiMessage? lastMessage
});


$ChatApiMessageCopyWith<$Res>? get lastMessage;

}
/// @nodoc
class _$ConversationCopyWithImpl<$Res>
    implements $ConversationCopyWith<$Res> {
  _$ConversationCopyWithImpl(this._self, this._then);

  final Conversation _self;
  final $Res Function(Conversation) _then;

/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? title = freezed,Object? timestamp = freezed,Object? lastMessage = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,title: freezed == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String?,timestamp: freezed == timestamp ? _self.timestamp : timestamp // ignore: cast_nullable_to_non_nullable
as DateTime?,lastMessage: freezed == lastMessage ? _self.lastMessage : lastMessage // ignore: cast_nullable_to_non_nullable
as ChatApiMessage?,
  ));
}
/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$ChatApiMessageCopyWith<$Res>? get lastMessage {
    if (_self.lastMessage == null) {
    return null;
  }

  return $ChatApiMessageCopyWith<$Res>(_self.lastMessage!, (value) {
    return _then(_self.copyWith(lastMessage: value));
  });
}
}


/// Adds pattern-matching-related methods to [Conversation].
extension ConversationPatterns on Conversation {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _Conversation value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _Conversation() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _Conversation value)  $default,){
final _that = this;
switch (_that) {
case _Conversation():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _Conversation value)?  $default,){
final _that = this;
switch (_that) {
case _Conversation() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String? title,  DateTime? timestamp, @JsonKey(name: 'last_message')  ChatApiMessage? lastMessage)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _Conversation() when $default != null:
return $default(_that.id,_that.title,_that.timestamp,_that.lastMessage);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String? title,  DateTime? timestamp, @JsonKey(name: 'last_message')  ChatApiMessage? lastMessage)  $default,) {final _that = this;
switch (_that) {
case _Conversation():
return $default(_that.id,_that.title,_that.timestamp,_that.lastMessage);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String? title,  DateTime? timestamp, @JsonKey(name: 'last_message')  ChatApiMessage? lastMessage)?  $default,) {final _that = this;
switch (_that) {
case _Conversation() when $default != null:
return $default(_that.id,_that.title,_that.timestamp,_that.lastMessage);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _Conversation implements Conversation {
  const _Conversation({required this.id, this.title, this.timestamp, @JsonKey(name: 'last_message') this.lastMessage});
  factory _Conversation.fromJson(Map<String, dynamic> json) => _$ConversationFromJson(json);

@override final  String id;
@override final  String? title;
@override final  DateTime? timestamp;
@override@JsonKey(name: 'last_message') final  ChatApiMessage? lastMessage;

/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ConversationCopyWith<_Conversation> get copyWith => __$ConversationCopyWithImpl<_Conversation>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ConversationToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _Conversation&&(identical(other.id, id) || other.id == id)&&(identical(other.title, title) || other.title == title)&&(identical(other.timestamp, timestamp) || other.timestamp == timestamp)&&(identical(other.lastMessage, lastMessage) || other.lastMessage == lastMessage));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,title,timestamp,lastMessage);

@override
String toString() {
  return 'Conversation(id: $id, title: $title, timestamp: $timestamp, lastMessage: $lastMessage)';
}


}

/// @nodoc
abstract mixin class _$ConversationCopyWith<$Res> implements $ConversationCopyWith<$Res> {
  factory _$ConversationCopyWith(_Conversation value, $Res Function(_Conversation) _then) = __$ConversationCopyWithImpl;
@override @useResult
$Res call({
 String id, String? title, DateTime? timestamp,@JsonKey(name: 'last_message') ChatApiMessage? lastMessage
});


@override $ChatApiMessageCopyWith<$Res>? get lastMessage;

}
/// @nodoc
class __$ConversationCopyWithImpl<$Res>
    implements _$ConversationCopyWith<$Res> {
  __$ConversationCopyWithImpl(this._self, this._then);

  final _Conversation _self;
  final $Res Function(_Conversation) _then;

/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? title = freezed,Object? timestamp = freezed,Object? lastMessage = freezed,}) {
  return _then(_Conversation(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,title: freezed == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String?,timestamp: freezed == timestamp ? _self.timestamp : timestamp // ignore: cast_nullable_to_non_nullable
as DateTime?,lastMessage: freezed == lastMessage ? _self.lastMessage : lastMessage // ignore: cast_nullable_to_non_nullable
as ChatApiMessage?,
  ));
}

/// Create a copy of Conversation
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$ChatApiMessageCopyWith<$Res>? get lastMessage {
    if (_self.lastMessage == null) {
    return null;
  }

  return $ChatApiMessageCopyWith<$Res>(_self.lastMessage!, (value) {
    return _then(_self.copyWith(lastMessage: value));
  });
}
}

// dart format on
