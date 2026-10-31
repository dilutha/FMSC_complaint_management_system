/// Demo accounts created by `python manage.py seed_demo_users`
/// (backend/apps/accounts/management/commands/seed_demo_users.py). Keep the
/// usernames here in step with that command.
///
/// DEVELOPMENT ONLY: every demo account shares this password. It is never a
/// real credential, and production databases never contain these accounts
/// (the seed command refuses to run unless DJANGO_DEBUG=true).
const demoPassword = 'Password@123';

class DemoAccount {
  const DemoAccount({
    required this.username,
    required this.role,
    required this.group,
    required this.landsOn,
    required this.tryThis,
  });

  final String username;
  final String role;

  /// Complainers | Admins | Case Administrators | Resolving Departments | Read-only viewer
  final String group;
  final String landsOn;
  final String tryThis;
}

const demoAccounts = [
  DemoAccount(
    username: 'demo_student',
    role: 'Student',
    group: 'Complainers',
    landsOn: 'Student dashboard',
    tryThis: 'Submit a complaint or a suggestion, then follow its status and messages.',
  ),
  DemoAccount(
    username: 'demo_lecturer',
    role: 'Lecturer',
    group: 'Complainers',
    landsOn: 'Lecturer dashboard',
    tryThis: 'See only your own submissions, including one already resolved by the IT Department.',
  ),
  DemoAccount(
    username: 'demo_non_academic',
    role: 'Non-academic staff',
    group: 'Complainers',
    landsOn: 'Non-academic staff dashboard',
    tryThis: 'Track a complaint assigned to the Maintenance Department.',
  ),
  DemoAccount(
    username: 'demo_system_admin',
    role: 'Admin',
    group: 'Admins',
    landsOn: 'Admin dashboard',
    tryThis: 'Monitor every case faculty-wide and add an admin message (no status changes).',
  ),
  DemoAccount(
    username: 'demo_case_admin',
    role: 'Case Administrator',
    group: 'Case Administrators',
    landsOn: 'Review queue',
    tryThis: 'Review a new case, assign it to a department with a message, and follow its progress.',
  ),
  DemoAccount(
    username: 'demo_it',
    role: 'IT Department',
    group: 'Resolving Departments',
    landsOn: 'IT Department dashboard',
    tryThis: 'See only IT cases; update a status with a message or record a resolution.',
  ),
  DemoAccount(
    username: 'demo_maintenance',
    role: 'Maintenance Department',
    group: 'Resolving Departments',
    landsOn: 'Maintenance dashboard',
    tryThis: 'Work on Maintenance cases only; other departments\' cases are not visible.',
  ),
  DemoAccount(
    username: 'demo_exams',
    role: 'Examination Unit',
    group: 'Resolving Departments',
    landsOn: 'Examination Unit dashboard',
    tryThis: 'Continue the in-progress examination case and resolve it.',
  ),
  DemoAccount(
    username: 'demo_deans_office',
    role: "Dean's Office",
    group: 'Resolving Departments',
    landsOn: "Dean's Office dashboard",
    tryThis: 'Start work on the newly assigned case with a progress message.',
  ),
  DemoAccount(
    username: 'demo_management',
    role: 'Faculty Management',
    group: 'Read-only viewer',
    landsOn: 'Faculty overview',
    tryThis: 'Explore reports, trends and department workload (read-only).',
  ),
];
