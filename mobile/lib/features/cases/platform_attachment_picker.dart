import 'package:file_picker/file_picker.dart';

import '../../core/api_client.dart';

/// Default [AttachmentPicker]: the platform file/gallery picker.
Future<List<UploadFile>> pickAttachmentsFromDevice({required List<String> allowedExtensions}) async {
  final result = await FilePicker.pickFiles(
    allowMultiple: true,
    type: FileType.custom,
    allowedExtensions: allowedExtensions,
    withData: true,
  );
  if (result == null) return const [];
  return [
    for (final f in result.files)
      if (f.bytes != null) UploadFile(name: f.name, bytes: f.bytes!),
  ];
}
