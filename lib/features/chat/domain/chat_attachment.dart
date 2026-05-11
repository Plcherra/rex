import 'dart:convert';
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:path/path.dart' as p;

const int maxChatAttachmentBytes = 2 * 1024 * 1024;
const Set<String> allowedChatAttachmentExtensions = {'txt', 'md', 'csv'};

String chatAttachmentName(XFile attachment) {
  if (attachment.name.trim().isNotEmpty) {
    return attachment.name.trim();
  }

  return p.basename(attachment.path);
}

String formatAttachmentSize(int bytes) {
  if (bytes < 1024) {
    return '$bytes B';
  }
  if (bytes < 1024 * 1024) {
    return '${(bytes / 1024).toStringAsFixed(1)} KB';
  }

  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}

String? validateChatAttachment({
  required String fileName,
  required int fileSize,
}) {
  final extension = p.extension(fileName).replaceFirst('.', '').toLowerCase();
  if (!allowedChatAttachmentExtensions.contains(extension)) {
    return 'Attach a .txt, .md, or .csv file.';
  }

  if (fileSize > maxChatAttachmentBytes) {
    return 'Attachment is too large. Maximum size is 2MB.';
  }

  return null;
}

String? validateChatAttachmentBytes({
  required String fileName,
  required int fileSize,
  required Uint8List bytes,
}) {
  final metadataError = validateChatAttachment(
    fileName: fileName,
    fileSize: fileSize,
  );
  if (metadataError != null) {
    return metadataError;
  }

  try {
    utf8.decode(bytes, allowMalformed: false);
  } on FormatException {
    return 'Attachment must be valid UTF-8 text.';
  }

  return null;
}

Future<String?> validateChatAttachmentFile(XFile attachment) async {
  final fileName = chatAttachmentName(attachment);
  late final int fileSize;

  try {
    fileSize = await attachment.length();
  } on Object {
    return 'Could not read selected file.';
  }

  final metadataError = validateChatAttachment(
    fileName: fileName,
    fileSize: fileSize,
  );
  if (metadataError != null) {
    return metadataError;
  }

  try {
    final bytes = await attachment.readAsBytes();
    utf8.decode(bytes, allowMalformed: false);
  } on FormatException {
    return 'Attachment must be valid UTF-8 text.';
  } on Object {
    return 'Could not read selected file.';
  }

  return null;
}
