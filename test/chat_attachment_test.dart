import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/chat/domain/chat_attachment.dart';

void main() {
  test('validateChatAttachment accepts supported files under 2MB', () {
    final error = validateChatAttachment(
      fileName: 'notes.md',
      fileSize: maxChatAttachmentBytes,
    );

    expect(error, isNull);
  });

  test('validateChatAttachment rejects unsupported extensions', () {
    final error = validateChatAttachment(fileName: 'photo.png', fileSize: 128);

    expect(error, 'Attach a .txt, .md, or .csv file.');
  });

  test('validateChatAttachment rejects files over 2MB', () {
    final error = validateChatAttachment(
      fileName: 'notes.txt',
      fileSize: maxChatAttachmentBytes + 1,
    );

    expect(error, 'Attachment is too large. Maximum size is 2MB.');
  });

  test('formatAttachmentSize formats bytes for preview', () {
    expect(formatAttachmentSize(512), '512 B');
    expect(formatAttachmentSize(1536), '1.5 KB');
    expect(formatAttachmentSize(2 * 1024 * 1024), '2.0 MB');
  });

  test('validateChatAttachmentBytes rejects non-UTF8 files', () {
    final error = validateChatAttachmentBytes(
      fileName: 'notes.txt',
      fileSize: 2,
      bytes: Uint8List.fromList([0xff, 0xfe]),
    );

    expect(error, 'Attachment must be valid UTF-8 text.');
  });

  test(
    'validateChatAttachmentFile validates XFile metadata and bytes',
    () async {
      final error = await validateChatAttachmentFile(
        XFile.fromData(
          Uint8List.fromList([0xff, 0xfe]),
          name: 'notes.txt',
          path: 'notes.txt',
          length: 2,
        ),
      );

      expect(error, 'Attachment must be valid UTF-8 text.');
    },
  );
}
