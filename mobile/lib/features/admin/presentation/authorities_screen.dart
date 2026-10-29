import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../../design/platform_widgets.dart';
import '../../../design/theme.dart';
import '../../../design/usj_colors.dart';
import '../../../design/widgets.dart';
import '../../../platform/platform_scope.dart';
import '../data/admin.dart';

/// Responsible authorities (Maintenance Division, IT Unit, ...). Units with
/// case history are deactivated rather than deleted.
class AuthoritiesScreen extends StatefulWidget {
  const AuthoritiesScreen({super.key});

  @override
  State<AuthoritiesScreen> createState() => _AuthoritiesScreenState();
}

class _AuthoritiesScreenState extends State<AuthoritiesScreen> {
  List<ManagedAuthority>? _items;
  ApiException? _error;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started) {
      _started = true;
      _load();
    }
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final items = await PlatformScope.of(context).admin.authorities();
      if (mounted) setState(() => _items = items);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _edit(ManagedAuthority? a) async {
    final saved = await showFormSheet<bool>(
      context,
      title: a == null ? 'New authority' : 'Edit ${a.name}',
      child: _AuthorityForm(authority: a),
    );
    if (saved == true && mounted) {
      showSuccess(context, 'Authority saved.');
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Responsible authorities')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(null),
        icon: const Icon(Icons.add),
        label: const Text('New authority'),
        backgroundColor: UsjColors.red,
        foregroundColor: Colors.white,
      ),
      body: () {
        if (_error != null && _items == null) return MessageView.error(message: _error!.message, onRetry: _load);
        final items = _items;
        if (items == null) return const LoadingView(message: 'Loading authorities…');
        if (items.isEmpty) return const MessageView(icon: Icons.apartment_outlined, title: 'No authorities yet');
        return RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            padding: const EdgeInsets.only(bottom: 96),
            itemCount: items.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final a = items[i];
              return ListTile(
                minTileHeight: kMinTouchTarget + 8,
                title: Text(a.name),
                subtitle: Text([
                  if (a.unit.isNotEmpty) a.unit,
                  '${a.memberCount} member${a.memberCount == 1 ? '' : 's'}',
                ].join(' · ')),
                trailing: a.isActive
                    ? const Icon(Icons.chevron_right)
                    : const Chip(label: Text('Inactive'), avatar: Icon(Icons.block, size: 16)),
                onTap: () => _edit(a),
              );
            },
          ),
        );
      }(),
    );
  }
}

class _AuthorityForm extends StatefulWidget {
  const _AuthorityForm({this.authority});
  final ManagedAuthority? authority;

  @override
  State<_AuthorityForm> createState() => _AuthorityFormState();
}

class _AuthorityFormState extends State<_AuthorityForm> {
  final _formKey = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.authority?.name);
  late final _code = TextEditingController(text: widget.authority?.code);
  late final _unit = TextEditingController(text: widget.authority?.unit);
  late final _officer = TextEditingController(text: widget.authority?.officerName);
  late final _email = TextEditingController(text: widget.authority?.email);
  late final _phone = TextEditingController(text: widget.authority?.phone);
  late bool _active = widget.authority?.isActive ?? true;
  ApiException? _error;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_name, _code, _unit, _officer, _email, _phone]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await PlatformScope.of(context).admin.saveAuthority(widget.authority?.id, {
        'name': _name.text.trim(),
        'code': _code.text.trim(),
        'unit': _unit.text.trim(),
        'officer_name': _officer.text.trim(),
        'email': _email.text.trim(),
        'phone': _phone.text.trim(),
        'is_active': _active,
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(TextEditingController c, String label, String field, {bool required = false, String? helper}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: Space.md),
        child: TextFormField(
          controller: c,
          enabled: !_busy,
          decoration: InputDecoration(labelText: label, helperText: helper, errorText: _error?.fieldError(field)),
          validator: required ? (v) => (v ?? '').trim().isEmpty ? 'Required.' : null : null,
        ),
      );

  @override
  Widget build(BuildContext context) => Form(
    key: _formKey,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        _field(_name, 'Name', 'name', required: true),
        _field(_code, 'Short code', 'code', required: true, helper: 'Lowercase letters, numbers and hyphens.'),
        _field(_unit, 'Faculty division or department', 'unit'),
        _field(_officer, 'Responsible officer', 'officer_name'),
        _field(_email, 'Email', 'email'),
        _field(_phone, 'Phone', 'phone'),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Active'),
          subtitle: const Text('Inactive authorities cannot receive new cases.'),
          value: _active,
          onChanged: _busy ? null : (v) => setState(() => _active = v),
        ),
        if (_error != null && _error!.details.isEmpty) Text(_error!.message, style: const TextStyle(color: UsjColors.error)),
        const SizedBox(height: Space.lg),
        FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
      ],
    ),
  );
}
