/// The signed-in user, as returned by GET /auth/me/ and POST /auth/token/.
///
/// [capabilities] only decide which navigation entries are shown. Every
/// action is re-checked by the server.
class CurrentUser {
  const CurrentUser({
    required this.id,
    required this.username,
    required this.displayName,
    required this.role,
    required this.roleLabel,
    this.firstName = '',
    this.lastName = '',
    this.email = '',
    this.department = '',
    this.contactNumber = '',
    this.capabilities = const {},
    this.authorities = const [],
  });

  final int id;
  final String username;
  final String displayName;
  final String firstName;
  final String lastName;
  final String email;
  final String role;
  final String roleLabel;
  final String department;
  final String contactNumber;
  final Set<String> capabilities;
  final List<({int id, String name})> authorities;

  bool can(String capability) => capabilities.contains(capability);
  bool get canViewDashboard => can('view_dashboard');
  bool get canEvaluateSuggestions => can('evaluate_suggestions');
  bool get canManageUsers => can('manage_users');
  bool get canManageAuthorities => can('manage_authorities');
  bool get handlesCases => can('handle_assigned_cases');

  /// Staff who work with suggestions (deciders, responsible units, management).
  bool get seesSuggestionQueue => canEvaluateSuggestions || handlesCases || canViewDashboard;

  factory CurrentUser.fromJson(Map<String, dynamic> j) => CurrentUser(
    id: j['id'] as int,
    username: j['username'] as String,
    displayName: (j['display_name'] as String?) ?? j['username'] as String,
    firstName: (j['first_name'] as String?) ?? '',
    lastName: (j['last_name'] as String?) ?? '',
    email: (j['email'] as String?) ?? '',
    role: j['role'] as String,
    roleLabel: (j['role_label'] as String?) ?? j['role'] as String,
    department: (j['department'] as String?) ?? '',
    contactNumber: (j['contact_number'] as String?) ?? '',
    capabilities: {for (final c in (j['capabilities'] as List?) ?? const []) c as String},
    authorities: [
      for (final a in (j['authorities'] as List?) ?? const [])
        (id: (a as Map<String, dynamic>)['id'] as int, name: a['name'] as String),
    ],
  );
}
