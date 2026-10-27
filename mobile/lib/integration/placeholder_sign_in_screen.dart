import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../design/theme.dart';
import '../design/usj_colors.dart';
import '../design/widgets.dart';
import 'auth_session.dart';

/// PLACEHOLDER — Member B owns sign-in. This minimal screen exists only so the
/// case module can be exercised end to end against the real API before the
/// shared auth module is merged. Delete it when Member B's login lands.
class PlaceholderSignInScreen extends StatefulWidget {
  const PlaceholderSignInScreen({super.key, required this.api, required this.session});
  final ApiClient api;
  final InMemoryAuthSession session;

  @override
  State<PlaceholderSignInScreen> createState() => _PlaceholderSignInScreenState();
}

class _PlaceholderSignInScreenState extends State<PlaceholderSignInScreen> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (_username.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter your username and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final json =
          await widget.api.post('auth/token/', {'username': _username.text.trim(), 'password': _password.text})
              as Map<String, dynamic>;
      final user = json['user'] as Map<String, dynamic>;
      widget.session.signIn(
        token: json['token'] as String,
        displayName: user['display_name'] as String,
        role: user['role'] as String,
      );
    } on ApiException catch (e) {
      setState(() => _error = e.statusCode == 400 ? 'Incorrect username or password.' : e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(Space.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: UsjLogo(size: 96)),
                    const SizedBox(height: Space.lg),
                    Text(
                      'FMSC Complaint & Suggestion Management',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleLarge,
                    ),
                    const SizedBox(height: Space.xs),
                    Text(
                      'Faculty of Management Studies and Commerce',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium?.copyWith(color: UsjColors.textSecondary),
                    ),
                    const SizedBox(height: Space.xl),
                    TextField(
                      controller: _username,
                      enabled: !_busy,
                      autofillHints: const [AutofillHints.username],
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(labelText: 'Username'),
                    ),
                    const SizedBox(height: Space.md),
                    TextField(
                      controller: _password,
                      enabled: !_busy,
                      obscureText: true,
                      autofillHints: const [AutofillHints.password],
                      onSubmitted: (_) => _signIn(),
                      decoration: InputDecoration(labelText: 'Password', errorText: _error),
                    ),
                    const SizedBox(height: Space.lg),
                    FilledButton(onPressed: _busy ? null : _signIn, child: Text(_busy ? 'Signing in…' : 'Sign in')),
                    const SizedBox(height: Space.md),
                    Text(
                      'Development sign-in. University sign-in is provided by the authentication module.',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
