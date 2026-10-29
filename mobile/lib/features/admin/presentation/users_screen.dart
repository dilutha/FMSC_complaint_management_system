import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/paged_list.dart';
import '../../../platform/platform_scope.dart';
import '../data/admin.dart';

/// System administrators: create accounts, change roles and unit membership,
/// activate or deactivate. Accounts are never deleted.
class UsersScreen extends StatefulWidget {
  const UsersScreen({super.key});

  @override
  State<UsersScreen> createState() => _UsersScreenState();
}

class _UsersScreenState extends State<UsersScreen> {
  final _search = TextEditingController();
  String _query = '';
  int _reload = 0;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _edit(ManagedUser? user) async {
    final saved = await showFormSheet<bool>(
      context,
      title: user == null ? 'New account' : 'Edit ${user.displayName}',
      child: UserForm(user: user),
    );
    if (saved == true && mounted) {
      setState(() => _reload++);
      showSuccess(context, user == null ? 'Account created.' : 'Account updated.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = PlatformScope.of(context).admin;
    return Scaffold(
      appBar: AppBar(title: const Text('User accounts')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(null),
        icon: const Icon(Icons.person_add_alt),
        label: const Text('New account'),
        backgroundColor: UsjColors.red,
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(Space.lg),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (v) => setState(() => _query = v),
              decoration: InputDecoration(
                labelText: 'Search by name, username or email',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() {
                          _search.clear();
                          _query = '';
                        }),
                      ),
              ),
            ),
          ),
          Expanded(
            child: PagedList<ManagedUser>(
              reloadKey: (_query, _reload),
              loadingMessage: 'Loading accounts…',
              load: (page) => repo.users(page: page, search: _query),
              empty: const MessageView(icon: Icons.person_search, title: 'No accounts found'),
              itemBuilder: (context, u, _) => ListTile(
                minTileHeight: kMinTouchTarget + 8,
                title: Text(u.displayName),
                subtitle: Text('${roleLabels[u.role] ?? u.role} · ${u.username}'),
                trailing: u.isActive
                    ? const Icon(Icons.chevron_right)
                    : const Chip(label: Text('Inactive'), avatar: Icon(Icons.block, size: 16)),
                onTap: () => _edit(u),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class UserForm extends StatefulWidget {
  const UserForm({super.key, this.user});
  final ManagedUser? user;

  @override
  State<UserForm> createState() => _UserFormState();
}

class _UserFormState extends State<UserForm> {
  final _formKey = GlobalKey<FormState>();
  late final _username = TextEditingController(text: widget.user?.username);
  late final _email = TextEditingController(text: widget.user?.email);
  late final _first = TextEditingController(text: widget.user?.firstName);
  late final _last = TextEditingController(text: widget.user?.lastName);
  final _password = TextEditingController();
  late String _role = widget.user?.role ?? 'student';
  late bool _active = widget.user?.isActive ?? true;
  late final Set<int> _units = {...?widget.user?.authorityIds};
  List<({int id, String name})> _allUnits = const [];
  ApiException? _error;
  bool _busy = false;
  bool _loaded = false;

  bool get _isNew => widget.user == null;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) {
      _loaded = true;
      PlatformScope.of(context).admin.authorities().then((list) {
        if (mounted) setState(() => _allUnits = [for (final a in list) if (a.isActive) (id: a.id, name: a.name)]);
      }, onError: (_) {});
    }
  }

  @override
  void dispose() {
    for (final c in [_username, _email, _first, _last, _password]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final repo = PlatformScope.of(context).admin;
    final data = <String, dynamic>{
      'username': _username.text.trim(),
      'email': _email.text.trim(),
      'first_name': _first.text.trim(),
      'last_name': _last.text.trim(),
      'role': _role,
      'is_active': _active,
      'authority_ids': authorityMemberRoles.contains(_role) ? _units.toList() : <int>[],
      if (_password.text.isNotEmpty) 'password': _password.text,
    };
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      _isNew ? await repo.createUser(data) : await repo.updateUser(widget.user!.id, data);
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(TextEditingController c, String label, String field, {bool required = false, bool obscure = false,
      String? helper, TextInputType? keyboard}) => Padding(
    padding: const EdgeInsets.only(bottom: Space.md),
    child: TextFormField(
      controller: c,
      enabled: !_busy,
      obscureText: obscure,
      keyboardType: keyboard,
      decoration: InputDecoration(labelText: label, helperText: helper, errorText: _error?.fieldError(field)),
      validator: required ? (v) => (v ?? '').trim().isEmpty ? 'Required.' : null : null,
    ),
  );

  @override
  Widget build(BuildContext context) {
    final canJoinUnits = authorityMemberRoles.contains(_role);
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          _field(_username, 'Username', 'username', required: true),
          _field(_email, 'Email', 'email', keyboard: TextInputType.emailAddress),
          Row(
            children: [
              Expanded(child: _field(_first, 'First name', 'first_name')),
              const SizedBox(width: Space.md),
              Expanded(child: _field(_last, 'Last name', 'last_name')),
            ],
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: Space.md),
            child: DropdownButtonFormField<String>(
              initialValue: _role,
              isExpanded: true,
              decoration: InputDecoration(labelText: 'Role', errorText: _error?.fieldError('role')),
              items: [for (final e in roleLabels.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: _busy ? null : (v) => setState(() => _role = v!),
            ),
          ),
          if (canJoinUnits && _allUnits.isNotEmpty) ...[
            Text('Responsible units', style: Theme.of(context).textTheme.titleSmall),
            Text(
              'Members can act on cases assigned to these units.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: UsjColors.textSecondary),
            ),
            const SizedBox(height: Space.sm),
            Wrap(
              spacing: Space.sm,
              runSpacing: Space.sm,
              children: [
                for (final u in _allUnits)
                  FilterChip(
                    label: Text(u.name),
                    selected: _units.contains(u.id),
                    onSelected: _busy ? null : (v) => setState(() => v ? _units.add(u.id) : _units.remove(u.id)),
                  ),
              ],
            ),
            if (_error?.fieldError('authority_ids') != null)
              Text(_error!.fieldError('authority_ids')!, style: const TextStyle(color: UsjColors.error)),
            const SizedBox(height: Space.md),
          ],
          _field(
            _password,
            _isNew ? 'Initial password' : 'Reset password (optional)',
            'password',
            required: _isNew,
            obscure: true,
            helper: _isNew ? 'Share it securely; the user should change it after signing in.' : 'Signs the user out everywhere.',
          ),
          if (!_isNew)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Account active'),
              subtitle: const Text('Inactive accounts cannot sign in.'),
              value: _active,
              onChanged: _busy ? null : (v) => setState(() => _active = v),
            ),
          if (_error?.fieldError('is_active') != null)
            Text(_error!.fieldError('is_active')!, style: const TextStyle(color: UsjColors.error)),
          if (_error != null && _error!.details.isEmpty) Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
          const SizedBox(height: Space.lg),
          FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
        ],
      ),
    );
  }
}
