import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../design/platform_widgets.dart';
import '../../design/theme.dart';
import '../../design/usj_colors.dart';
import '../../design/widgets.dart';
import '../../platform/platform_scope.dart';
import '../admin/presentation/authorities_screen.dart';
import '../admin/presentation/users_screen.dart';
import '../home/home_page.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  Future<void> _confirmSignOut(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will need your password to sign in again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Sign out')),
        ],
      ),
    );
    if (ok == true && context.mounted) await PlatformScope.of(context).session.signOut();
  }

  @override
  Widget build(BuildContext context) {
    final scope = PlatformScope.of(context);
    return ListenableBuilder(
      listenable: scope.session,
      builder: (context, _) {
        final user = scope.session.user;
        if (user == null) return const SizedBox.shrink();
        return Scaffold(
          appBar: AppBar(title: const Text('Profile')),
          body: ListView(
            padding: const EdgeInsets.all(Space.lg),
            children: [
              SectionCard(
                title: user.displayName,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LabeledValue(label: 'Role', value: user.roleLabel),
                    LabeledValue(label: 'Username', value: user.username),
                    if (user.email.isNotEmpty) LabeledValue(label: 'Email', value: user.email),
                    if (user.authorities.isNotEmpty)
                      LabeledValue(label: 'Responsible units', value: user.authorities.map((a) => a.name).join(', ')),
                    LabeledValue(label: 'Department', value: user.department.isEmpty ? '–' : user.department),
                    LabeledValue(label: 'Contact number', value: user.contactNumber.isEmpty ? '–' : user.contactNumber),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Edit contact details'),
                        onPressed: () => showFormSheet<void>(context, title: 'Contact details', child: const _ContactForm()),
                      ),
                    ),
                    Text(
                      'Your name, email and role are managed by the faculty system administrator.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: Space.md),
              Card(
                clipBehavior: Clip.antiAlias,
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.info_outline),
                      title: const Text('About the system'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                        builder: (c) => HomePage(onLogin: () {}, onDashboard: () => Navigator.of(c).pop()),
                      )),
                    ),
                    const Divider(),
                    ListTile(
                      leading: const Icon(Icons.password),
                      title: const Text('Change password'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const ChangePasswordScreen()),
                      ),
                    ),
                    if (user.canManageUsers) ...[
                      const Divider(),
                      ListTile(
                        leading: const Icon(Icons.manage_accounts_outlined),
                        title: const Text('User accounts'),
                        subtitle: const Text('Create accounts, change roles, deactivate'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const UsersScreen())),
                      ),
                    ],
                    if (user.canManageAuthorities) ...[
                      const Divider(),
                      ListTile(
                        leading: const Icon(Icons.apartment_outlined),
                        title: const Text('Responsible authorities'),
                        subtitle: const Text('Add, edit, activate or deactivate units'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () =>
                            Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AuthoritiesScreen())),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: Space.xl),
              OutlinedButton.icon(
                onPressed: () => _confirmSignOut(context),
                icon: const Icon(Icons.logout),
                label: const Text('Sign out'),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ContactForm extends StatefulWidget {
  const _ContactForm();

  @override
  State<_ContactForm> createState() => _ContactFormState();
}

class _ContactFormState extends State<_ContactForm> {
  late final TextEditingController _phone;
  late final TextEditingController _department;
  ApiException? _error;
  bool _busy = false;
  bool _init = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_init) {
      _init = true;
      final user = PlatformScope.of(context).session.user!;
      _phone = TextEditingController(text: user.contactNumber);
      _department = TextEditingController(text: user.department);
    }
  }

  @override
  void dispose() {
    _phone.dispose();
    _department.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final scope = PlatformScope.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final user = await scope.auth.updateContact(contactNumber: _phone.text.trim(), department: _department.text.trim());
      await scope.session.update(user: user);
      if (mounted) {
        Navigator.pop(context);
        showSuccess(context, 'Contact details saved.');
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    mainAxisSize: MainAxisSize.min,
    children: [
      TextField(
        controller: _phone,
        enabled: !_busy,
        keyboardType: TextInputType.phone,
        maxLength: 30,
        decoration: InputDecoration(labelText: 'Contact number', errorText: _error?.fieldError('contact_number')),
      ),
      TextField(
        controller: _department,
        enabled: !_busy,
        maxLength: 120,
        decoration: InputDecoration(labelText: 'Department', errorText: _error?.fieldError('department')),
      ),
      if (_error != null && _error!.details.isEmpty)
        Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
      const SizedBox(height: Space.lg),
      FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
    ],
  );
}

class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  ApiException? _error;
  bool _busy = false;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final scope = PlatformScope.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await scope.auth.changePassword(_current.text, _next.text);
      await scope.session.update(token: result.token, user: result.user);
      if (mounted) {
        Navigator.pop(context);
        showSuccess(context, 'Password changed. Other devices have been signed out.');
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Change password')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(Space.lg),
          children: [
            TextFormField(
              controller: _current,
              obscureText: true,
              enabled: !_busy,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(labelText: 'Current password', errorText: _error?.fieldError('current_password')),
              validator: (v) => (v ?? '').isEmpty ? 'Enter your current password.' : null,
            ),
            const SizedBox(height: Space.md),
            TextFormField(
              controller: _next,
              obscureText: true,
              enabled: !_busy,
              autofillHints: const [AutofillHints.newPassword],
              decoration: InputDecoration(
                labelText: 'New password',
                helperText: 'At least 8 characters. Avoid common words and personal details.',
                errorText: _error?.fieldError('new_password'),
              ),
              validator: (v) => (v ?? '').length < 8 ? 'Use at least 8 characters.' : null,
            ),
            const SizedBox(height: Space.md),
            TextFormField(
              controller: _confirm,
              obscureText: true,
              enabled: !_busy,
              decoration: const InputDecoration(labelText: 'Confirm new password'),
              validator: (v) => v != _next.text ? 'The passwords do not match.' : null,
            ),
            if (_error != null && _error!.details.isEmpty) ...[
              const SizedBox(height: Space.md),
              Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
            ],
            const SizedBox(height: Space.xl),
            FilledButton(onPressed: _busy ? null : _submit, child: Text(_busy ? 'Saving…' : 'Change password')),
          ],
        ),
      ),
    );
  }
}
