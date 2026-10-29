import 'package:flutter/foundation.dart';

import '../../../core/api_client.dart';
import '../../cases/data/models.dart' show PageResult;

class AppNotification {
  const AppNotification({
    required this.id,
    required this.eventType,
    required this.title,
    required this.body,
    required this.isRead,
    required this.createdAt,
    this.caseNumber,
    this.targetType,
    this.targetId,
  });

  final int id;
  final String eventType;
  final String title;
  final String body;
  final bool isRead;
  final DateTime createdAt;
  final String? caseNumber;

  /// 'case' or 'suggestion' (navigation contract), with the case id.
  final String? targetType;
  final int? targetId;

  AppNotification copyWith({bool? isRead}) => AppNotification(
    id: id,
    eventType: eventType,
    title: title,
    body: body,
    isRead: isRead ?? this.isRead,
    createdAt: createdAt,
    caseNumber: caseNumber,
    targetType: targetType,
    targetId: targetId,
  );

  factory AppNotification.fromJson(Map<String, dynamic> j) {
    final target = j['target'] as Map<String, dynamic>?;
    return AppNotification(
      id: j['id'] as int,
      eventType: j['event_type'] as String,
      title: j['title'] as String,
      body: (j['body'] as String?) ?? '',
      isRead: j['is_read'] as bool,
      createdAt: DateTime.parse(j['created_at'] as String).toLocal(),
      caseNumber: j['case_number'] as String?,
      targetType: target?['type'] as String?,
      targetId: target?['id'] as int?,
    );
  }
}

abstract class NotificationRepository {
  Future<PageResult<AppNotification>> list({int page = 1, bool unreadOnly = false});
  Future<AppNotification> markRead(int id);
  Future<void> markAllRead();
  Future<int> unreadCount();
}

class ApiNotificationRepository implements NotificationRepository {
  ApiNotificationRepository(this._api);
  final ApiClient _api;

  @override
  Future<PageResult<AppNotification>> list({int page = 1, bool unreadOnly = false}) async {
    final json =
        await _api.get('notifications/', query: {'page': '$page', if (unreadOnly) 'unread': 'true'})
            as Map<String, dynamic>;
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: [for (final e in json['results'] as List) AppNotification.fromJson(e as Map<String, dynamic>)],
    );
  }

  @override
  Future<AppNotification> markRead(int id) async =>
      AppNotification.fromJson(await _api.post('notifications/$id/read/', const {}) as Map<String, dynamic>);

  @override
  Future<void> markAllRead() => _api.post('notifications/read-all/', const {});

  @override
  Future<int> unreadCount() async =>
      ((await _api.get('notifications/unread-count/')) as Map<String, dynamic>)['unread'] as int;
}

/// Unread badge state shared by the navigation bar and the notification centre.
/// Refreshed on sign-in, when the app resumes and after reading notifications.
class UnreadCounter extends ChangeNotifier {
  UnreadCounter(this._repository);
  final NotificationRepository _repository;
  int _count = 0;

  int get count => _count;

  Future<void> refresh() async {
    try {
      set(await _repository.unreadCount());
    } on ApiException {
      // The badge is a hint; a failed refresh keeps the last known value.
    }
  }

  void set(int value) {
    if (value == _count) return;
    _count = value < 0 ? 0 : value;
    notifyListeners();
  }
}
