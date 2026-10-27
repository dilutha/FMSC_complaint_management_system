import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';
import 'package:cross_file/cross_file.dart';

/// Saves bytes into the app's documents directory and returns the path.
Future<String> saveAttachment(String fileName, Uint8List bytes) async {
  final dir = await getApplicationDocumentsDirectory();
  final safeName = fileName.replaceAll(RegExp(r'[\\/:*?"<>|]'), '_');
  final path = '${dir.path}/$safeName';
  await XFile.fromData(bytes, name: safeName).saveTo(path);
  return path;
}
