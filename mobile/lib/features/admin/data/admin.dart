import '../../../core/api_client.dart';
import '../../cases/data/models.dart' show PageResult;

const roleLabels = {
  'student': 'Student',
  'lecturer': 'Lecturer',
  'authority': 'Relevant Authority',
  'case_admin': 'Administrator',
  'management': 'Faculty Management',
  'system_admin': 'System Administrator',
};

/// Roles that may belong to an authority (server enforces the same rule).
const authorityMemberRoles = {'authority', 'case_admin', 'system_admin'};

class ManagedUser {
  const ManagedUser({
    required this.id,
    required this.username,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.role,
    required this.isActive,
    required this.authorityIds,
    this.department = '',
  });

  final int id;
  final String username;
  final String email;
  final String firstName;
  final String lastName;
  final String role;
  final bool isActive;
  final List<int> authorityIds;
  final String department;

  String get displayName => [firstName, lastName].where((s) => s.isNotEmpty).join(' ').trim().isEmpty
      ? username
      : [firstName, lastName].where((s) => s.isNotEmpty).join(' ');

  factory ManagedUser.fromJson(Map<String, dynamic> j) => ManagedUser(
    id: j['id'] as int,
    username: j['username'] as String,
    email: (j['email'] as String?) ?? '',
    firstName: (j['first_name'] as String?) ?? '',
    lastName: (j['last_name'] as String?) ?? '',
    role: j['role'] as String,
    isActive: j['is_active'] as bool,
    department: (j['department'] as String?) ?? '',
    authorityIds: [for (final a in (j['authority_ids'] as List?) ?? const []) a as int],
  );
}

class ManagedAuthority {
  const ManagedAuthority({
    required this.id,
    required this.name,
    required this.code,
    required this.isActive,
    required this.memberCount,
    this.unit = '',
    this.officerName = '',
    this.email = '',
    this.phone = '',
  });

  final int id;
  final String name;
  final String code;
  final bool isActive;
  final int memberCount;
  final String unit;
  final String officerName;
  final String email;
  final String phone;

  factory ManagedAuthority.fromJson(Map<String, dynamic> j) => ManagedAuthority(
    id: j['id'] as int,
    name: j['name'] as String,
    code: j['code'] as String,
    isActive: j['is_active'] as bool,
    memberCount: (j['member_count'] as int?) ?? 0,
    unit: (j['unit'] as String?) ?? '',
    officerName: (j['officer_name'] as String?) ?? '',
    email: (j['email'] as String?) ?? '',
    phone: (j['phone'] as String?) ?? '',
  );
}

abstract class AdminRepository {
  Future<PageResult<ManagedUser>> users({int page = 1, String search = '', String? role});
  Future<ManagedUser> createUser(Map<String, dynamic> data);
  Future<ManagedUser> updateUser(int id, Map<String, dynamic> changes);
  Future<List<ManagedAuthority>> authorities();
  Future<ManagedAuthority> saveAuthority(int? id, Map<String, dynamic> data);
}

class ApiAdminRepository implements AdminRepository {
  ApiAdminRepository(this._api);
  final ApiClient _api;

  @override
  Future<PageResult<ManagedUser>> users({int page = 1, String search = '', String? role}) async {
    final json =
        await _api.get('manage/users/', query: {
              'page': '$page',
              if (search.trim().isNotEmpty) 'search': search.trim(),
              'role': ?role,
            })
            as Map<String, dynamic>;
    return PageResult(
      count: json['count'] as int,
      hasNext: json['next'] != null,
      items: [for (final u in json['results'] as List) ManagedUser.fromJson(u as Map<String, dynamic>)],
    );
  }

  @override
  Future<ManagedUser> createUser(Map<String, dynamic> data) async =>
      ManagedUser.fromJson(await _api.post('manage/users/', data) as Map<String, dynamic>);

  @override
  Future<ManagedUser> updateUser(int id, Map<String, dynamic> changes) async =>
      ManagedUser.fromJson(await _api.patch('manage/users/$id/', changes) as Map<String, dynamic>);

  @override
  Future<List<ManagedAuthority>> authorities() async => [
    for (final a in (await _api.get('manage/authorities/')) as List) ManagedAuthority.fromJson(a as Map<String, dynamic>),
  ];

  @override
  Future<ManagedAuthority> saveAuthority(int? id, Map<String, dynamic> data) async => ManagedAuthority.fromJson(
    (id == null ? await _api.post('manage/authorities/', data) : await _api.patch('manage/authorities/$id/', data))
        as Map<String, dynamic>,
  );
}
